"""Embedding 与 Reranker 的进程内生命周期管理。"""

import gc
from dataclasses import dataclass
from threading import Lock, RLock

import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel, FlagReranker

from services.rag_models.config import RagModelSettings


class ModelsNotReadyError(RuntimeError):
    """推理请求到达时模型尚未完成加载。"""


@dataclass(frozen=True)
class EmbeddingInferenceResult:
    """向量结果及准确的输入 token 用量。"""

    vectors: list[list[float]]
    prompt_tokens: int


@dataclass(frozen=True)
class RerankScore:
    """Reranker 分数及其对应的原始候选索引。"""

    index: int
    relevance_score: float


@dataclass(frozen=True)
class RerankInferenceResult:
    """完成稳定降序排序后的 Top-N 结果。"""

    results: list[RerankScore]


class ModelRuntime:
    """以单例方式加载、预热并释放两个本地模型。"""

    def __init__(self, settings: RagModelSettings) -> None:
        self.settings = settings
        self._embedder: BGEM3FlagModel | None = None
        self._reranker: FlagReranker | None = None
        self._last_error: str | None = None
        self._lifecycle_lock = RLock()
        # 两个接口共用一张消费级 GPU，先串行化前向计算来控制峰值显存。
        self.inference_lock = Lock()

    @property
    def is_loaded(self) -> bool:
        """两个模型都完成预热后才视为就绪。"""

        return self._embedder is not None and self._reranker is not None

    @property
    def last_error(self) -> str | None:
        """返回最近一次加载失败的简短原因。"""

        return self._last_error

    def load(self) -> None:
        """构造并预热两个模型，失败时回滚所有临时资源。"""

        with self._lifecycle_lock:
            if self.is_loaded:
                return

            self._last_error = None
            embedder = None
            reranker = None

            try:
                self._validate_configured_device()
                embedder = BGEM3FlagModel(
                    self.settings.embedding_model,
                    use_fp16=self.settings.use_fp16,
                    devices=self.settings.device,
                    batch_size=self.settings.embedding_batch_size,
                    query_max_length=self.settings.embedding_max_length,
                    passage_max_length=self.settings.embedding_max_length,
                    return_dense=True,
                    return_sparse=False,
                    return_colbert_vecs=False,
                )
                reranker = FlagReranker(
                    self.settings.reranker_model,
                    use_fp16=self.settings.use_fp16,
                    devices=self.settings.device,
                    batch_size=self.settings.reranker_batch_size,
                    max_length=self.settings.reranker_max_length,
                    normalize=self.settings.reranker_normalize_scores,
                )

                self._warm_up_and_validate(embedder, reranker)
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                del embedder
                del reranker
                self._clear_accelerator_cache()
                raise

            # 只有两个模型都通过预热和设备校验后，才向接口层发布实例。
            self._embedder = embedder
            self._reranker = reranker

    def unload(self) -> None:
        """释放模型引用、Python 对象和 CUDA 缓存。"""

        with self._lifecycle_lock:
            embedder = self._embedder
            reranker = self._reranker
            self._embedder = None
            self._reranker = None
            del embedder
            del reranker
            self._clear_accelerator_cache()

    def embed(self, texts: list[str]) -> EmbeddingInferenceResult:
        """将一批文本编码为 1024 维 dense 向量。"""

        with self.inference_lock:
            embedder = self._embedder
            if embedder is None or self._reranker is None:
                raise ModelsNotReadyError("Embedding 与 Reranker 尚未完成加载")

            # usage 必须来自真实 tokenizer；字符数不能代表子词 token 数。
            tokenized = embedder.tokenizer(
                texts,
                add_special_tokens=True,
                truncation=True,
                max_length=self.settings.embedding_max_length,
                padding=False,
            )
            prompt_tokens = sum(len(token_ids) for token_ids in tokenized["input_ids"])

            embedding_output = embedder.encode(
                texts,
                batch_size=self.settings.embedding_batch_size,
                max_length=self.settings.embedding_max_length,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            dense_vectors = np.asarray(
                embedding_output["dense_vecs"],
                dtype=np.float32,
            )
            expected_shape = (len(texts), self.settings.embedding_dimensions)
            if dense_vectors.shape != expected_shape:
                raise RuntimeError(
                    f"Embedding 返回错误维度：{dense_vectors.shape}，"
                    f"期望 {expected_shape}"
                )
            if not np.isfinite(dense_vectors).all():
                raise RuntimeError("Embedding 结果包含非有限值")

            return EmbeddingInferenceResult(
                vectors=dense_vectors.tolist(),
                prompt_tokens=prompt_tokens,
            )

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> RerankInferenceResult:
        """对候选文档评分，并保留每篇文档的原始索引。"""

        with self.inference_lock:
            reranker = self._reranker
            if self._embedder is None or reranker is None:
                raise ModelsNotReadyError("Embedding 与 Reranker 尚未完成加载")

            sentence_pairs = [(query, document) for document in documents]
            raw_scores = reranker.compute_score(
                sentence_pairs,
                batch_size=self.settings.reranker_batch_size,
                max_length=self.settings.reranker_max_length,
            )
            scores = np.atleast_1d(np.asarray(raw_scores, dtype=np.float32))
            if scores.shape != (len(documents),):
                raise RuntimeError(
                    f"Reranker 返回错误数量：{scores.shape}，"
                    f"期望 {(len(documents),)}"
                )
            if not np.isfinite(scores).all():
                raise RuntimeError("Reranker 结果包含非有限值")

            # index 作为第二排序键，使相同分数保持原始候选顺序。
            ranked_indices = sorted(
                range(len(documents)),
                key=lambda index: (-float(scores[index]), index),
            )[:top_n]
            return RerankInferenceResult(
                results=[
                    RerankScore(
                        index=index,
                        relevance_score=float(scores[index]),
                    )
                    for index in ranked_indices
                ]
            )

    def _validate_configured_device(self) -> None:
        """在加载权重前尽早发现 CUDA 配置错误。"""

        configured_device = torch.device(self.settings.device)
        if configured_device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("配置要求使用 CUDA，但当前 PyTorch 无法访问 CUDA")

    def _warm_up_and_validate(
        self,
        embedder: BGEM3FlagModel,
        reranker: FlagReranker,
    ) -> None:
        """执行最小推理，触发 FlagEmbedding 的延迟设备迁移。"""

        embedding_output = embedder.encode(
            ["JobPilot 本地向量模型预热"],
            batch_size=1,
            max_length=min(64, self.settings.embedding_max_length),
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense_vectors = np.asarray(embedding_output["dense_vecs"])
        if dense_vectors.shape != (1, self.settings.embedding_dimensions):
            raise RuntimeError(f"Embedding 预热返回错误维度：{dense_vectors.shape}")
        if not np.isfinite(dense_vectors).all():
            raise RuntimeError("Embedding 预热结果包含非有限值")

        reranker_scores = np.asarray(
            reranker.compute_score(
                [("JobPilot", "求职领域智能助手")],
                batch_size=1,
                max_length=min(64, self.settings.reranker_max_length),
            )
        )
        if not np.isfinite(reranker_scores).all():
            raise RuntimeError("Reranker 预热结果包含非有限值")

        expected_device_type = torch.device(self.settings.device).type
        embedding_device = next(embedder.model.parameters()).device
        reranker_device = next(reranker.model.parameters()).device
        if embedding_device.type != expected_device_type:
            raise RuntimeError(f"Embedding 实际设备错误：{embedding_device}")
        if reranker_device.type != expected_device_type:
            raise RuntimeError(f"Reranker 实际设备错误：{reranker_device}")

    @staticmethod
    def _clear_accelerator_cache() -> None:
        """回收 Python 对象，并归还 PyTorch 未使用的 CUDA 缓存。"""

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
