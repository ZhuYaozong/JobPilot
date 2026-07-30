"""数据工程配置模型与加载逻辑。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^{}]*))?\}")


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PathsConfig(StrictConfigModel):
    """所有输出路径均相对于 config.yaml 所在目录。"""

    output_root: Path = Path(".")
    lora_dir: Path = Path("lora")
    rag_documents_dir: Path = Path("rag/documents")
    evaluation_dir: Path = Path("evaluation")
    reports_dir: Path = Path("reports")
    work_dir: Path = Path(".work")
    prompts_dir: Path = Path("prompts")
    schemas_dir: Path = Path("schemas")


class ProviderConfig(StrictConfigModel):
    """模型 Provider 配置；密钥不会进入配置指纹或日志。"""

    kind: Literal["openai_compatible", "qwen_local", "fake"]
    model: str = ""
    base_url: str = ""
    api_key: str = Field(default="", repr=False, exclude=True)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1)
    timeout_seconds: float = Field(default=180, gt=0)
    max_retries: int = Field(default=3, ge=0, le=20)
    concurrency: int = Field(default=1, ge=1, le=64)
    send_seed: bool = True
    json_mode: bool = False
    extra_body: dict[str, Any] = Field(default_factory=dict)
    # Embedding Provider 专用字段；BGE-M3 固定输出 1024 维，通常无需把维度发给服务。
    dimensions: int | None = Field(default=None, ge=1, exclude=True)
    send_dimensions: bool = Field(default=False, exclude=True)

    # qwen_local 专用字段；OpenAI-compatible Provider 会忽略。
    device: str = "auto"
    dtype: str = "auto"
    trust_remote_code: bool = False


class GenerationConfig(StrictConfigModel):
    provider: str = "generator"
    batch_size: int = Field(default=6, ge=1, le=50)
    max_attempts_per_item: int = Field(default=5, ge=1, le=20)
    response_max_chars: int = Field(default=100_000, ge=1000)


class LoraConfig(StrictConfigModel):
    splits: dict[Literal["train", "val", "test"], int]
    task_types: list[str]
    answer_min_chars: int = Field(default=100, ge=1)
    answer_max_chars: int = Field(default=300, ge=1)
    instruction_min_chars: int = Field(default=8, ge=1)
    instruction_max_chars: int = Field(default=180, ge=1)
    difficulty_levels: list[str]
    scenarios: list[str]
    topic_catalog: dict[str, list[str]]

    @model_validator(mode="after")
    def validate_catalog(self) -> "LoraConfig":
        if self.answer_min_chars > self.answer_max_chars:
            raise ValueError("lora.answer_min_chars 不能大于 answer_max_chars")
        if self.instruction_min_chars > self.instruction_max_chars:
            raise ValueError("instruction_min_chars 不能大于 instruction_max_chars")
        if not self.task_types or not self.difficulty_levels or not self.scenarios:
            raise ValueError("LoRA 任务类型、难度和场景不能为空")
        missing = set(self.task_types) - set(self.topic_catalog)
        if missing:
            raise ValueError(f"LoRA topic_catalog 缺少任务类型: {sorted(missing)}")
        for split, count in self.splits.items():
            if count <= 0:
                raise ValueError(f"LoRA {split} 数量必须大于 0")
            if count % len(self.task_types) != 0:
                raise ValueError(f"LoRA {split} 数量必须能被任务类型数量整除")
        return self


class RagDocumentsConfig(StrictConfigModel):
    total: int = Field(default=50, ge=1)
    batch_size: int = Field(default=1, ge=1, le=10)
    min_chars: int = Field(default=1000, ge=1)
    max_chars: int = Field(default=3000, ge=1)
    domains: list[str]
    topic_catalog: dict[str, list[str]]

    @model_validator(mode="after")
    def validate_catalog(self) -> "RagDocumentsConfig":
        if self.min_chars > self.max_chars:
            raise ValueError("rag_documents.min_chars 不能大于 max_chars")
        if not self.domains:
            raise ValueError("RAG 文档领域不能为空")
        missing = set(self.domains) - set(self.topic_catalog)
        if missing:
            raise ValueError(f"RAG topic_catalog 缺少领域: {sorted(missing)}")
        return self


class RagEvaluationConfig(StrictConfigModel):
    total: int = Field(default=200, ge=1)
    batch_size: int = Field(default=4, ge=1, le=20)
    answer_min_chars: int = Field(default=40, ge=1)
    answer_max_chars: int = Field(default=300, ge=1)
    excerpt_min_chars: int = Field(default=15, ge=1)
    excerpt_max_chars: int = Field(default=300, ge=1)
    max_source_chars_per_batch: int = Field(default=12_000, ge=1000)
    include_generated_documents: bool = True
    include_external_documents: bool = True


class LoraEvaluationConfig(StrictConfigModel):
    total: int = Field(default=500, ge=1)
    batch_size: int = Field(default=6, ge=1, le=50)
    scenarios: list[str]

    @model_validator(mode="after")
    def validate_scenarios(self) -> "LoraEvaluationConfig":
        if not self.scenarios:
            raise ValueError("LoRA evaluation 场景不能为空")
        return self


class DeduplicationConfig(StrictConfigModel):
    fuzzy_threshold: float = Field(default=92.0, ge=0, le=100)
    simhash_max_distance: int = Field(default=8, ge=0, le=64)
    ngram_size: int = Field(default=3, ge=1, le=8)


class QualityConfig(StrictConfigModel):
    minimum_engineering_signal_groups: int = Field(default=2, ge=0, le=10)
    fail_on_warning: bool = False


class ExternalDocumentsConfig(StrictConfigModel):
    allowed_extensions: list[str]
    minimum_chars: int = Field(default=100, ge=1)


class RetrieverConfig(StrictConfigModel):
    # kind 作为旧配置的默认策略保留；新配置优先由 variant.retrieval_strategy 指定。
    kind: Literal["vector", "bm25", "hybrid"] = "bm25"
    top_k: int = Field(default=5, ge=1, le=100)
    chunk_size: int = Field(default=600, ge=100)
    chunk_overlap: int = Field(default=100, ge=0)
    candidate_multiplier: int = Field(default=3, ge=1, le=20)
    bm25_k1: float = Field(default=1.5, gt=0)
    bm25_b: float = Field(default=0.75, ge=0, le=1)
    hybrid_rrf_k: int = Field(default=60, ge=1)
    vector_weight: float = Field(default=1.0, gt=0)
    bm25_weight: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def validate_overlap(self) -> "RetrieverConfig":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")
        return self


class ExperimentVariantConfig(StrictConfigModel):
    name: str
    provider: str
    use_rag: bool = False
    retrieval_strategy: Literal["none", "vector", "bm25", "hybrid"] | None = None
    reranker_enabled: bool = False

    def resolved_strategy(self, default: str) -> str:
        """兼容旧 use_rag：旧配置仍按全局 retriever.kind 执行。"""
        if self.retrieval_strategy is not None:
            return self.retrieval_strategy
        return default if self.use_rag else "none"


class ExperimentsConfig(StrictConfigModel):
    evaluation_file: Path = Path("evaluation/rag_test.jsonl")
    retriever: RetrieverConfig = Field(default_factory=RetrieverConfig)
    concurrency: int = Field(default=4, ge=1, le=64)
    judge_provider: str | None = None
    embedding_provider: str | None = None
    reranker_provider: str | None = None
    variants: list[ExperimentVariantConfig]

    @model_validator(mode="after")
    def validate_variants(self) -> "ExperimentsConfig":
        names = [item.name for item in self.variants]
        if len(names) != len(set(names)):
            raise ValueError("实验 variant.name 不能重复")
        return self


class AppConfig(StrictConfigModel):
    """数据工程根配置。"""

    version: int = 1
    seed: int = 20260723
    paths: PathsConfig
    providers: dict[str, ProviderConfig]
    generation: GenerationConfig
    lora: LoraConfig
    rag_documents: RagDocumentsConfig
    rag_evaluation: RagEvaluationConfig
    lora_evaluation: LoraEvaluationConfig
    deduplication: DeduplicationConfig
    quality: QualityConfig
    external_documents: ExternalDocumentsConfig
    experiments: ExperimentsConfig
    config_path: Path = Field(default=Path("config.yaml"), exclude=True)

    @model_validator(mode="after")
    def validate_provider_references(self) -> "AppConfig":
        references = {self.generation.provider}
        references.update(item.provider for item in self.experiments.variants)
        if self.experiments.judge_provider:
            references.add(self.experiments.judge_provider)
        if self.experiments.embedding_provider:
            references.add(self.experiments.embedding_provider)
        if self.experiments.reranker_provider:
            references.add(self.experiments.reranker_provider)
        missing = references - set(self.providers)
        if missing:
            raise ValueError(f"配置引用了不存在的 Provider: {sorted(missing)}")
        return self

    @property
    def base_dir(self) -> Path:
        return self.config_path.parent.resolve()

    def resolve_path(self, path: Path) -> Path:
        """把配置中的相对路径固定到 config.yaml 目录。"""
        if path.is_absolute():
            return path.resolve()
        return (self.base_dir / self.paths.output_root / path).resolve()

    @property
    def fingerprint(self) -> str:
        """生成不含密钥、实验模型配置和 config_path 的生产配置指纹。"""
        payload = self.model_dump(mode="json", exclude={"config_path"})
        generation_provider = self.generation.provider
        provider_payload = payload.get("providers", {}).get(generation_provider, {})
        provider_payload.pop("api_key", None)
        payload["providers"] = {generation_provider: provider_payload}
        payload.pop("experiments", None)
        for provider in payload.get("providers", {}).values():
            provider.pop("api_key", None)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _expand_environment(value: Any) -> Any:
    """递归展开 ${NAME} 和 ${NAME:-default}，支持默认值继续引用环境变量。"""
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if not isinstance(value, str):
        return value

    result = value
    # 嵌套默认值最多展开十轮，避免异常配置造成无限循环。
    for _ in range(10):
        match = _ENV_PATTERN.search(result)
        if match is None:
            break
        name, default = match.groups()
        replacement = os.environ.get(name, default or "")
        result = result[: match.start()] + replacement + result[match.end() :]
    return result


def load_config(path: str | Path) -> AppConfig:
    """读取 YAML、展开环境变量并完成 Pydantic 校验。"""
    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    if not isinstance(raw, dict):
        raise ValueError("配置文件根节点必须是对象")
    expanded = _expand_environment(raw)
    expanded["config_path"] = config_path
    return AppConfig.model_validate(expanded)
