"""OpenAI-compatible embeddings client.

中文说明：这是 JobPilot 的向量化适配层，专门服务知识库索引和
``search_knowledge`` 工具。它故意独立于聊天 LLM client，这样部署时可以
用不同供应商分别承载生成模型和 embedding 模型。

Kept deliberately separate from :class:`app.llm.client.LLMClient` so a
deployment can route embeddings to a different provider (e.g. chat from a
local Llama, embeddings from OpenAI for higher Chinese quality) by setting
``embedding_*`` env vars without touching the chat config.

Each ``embedding_*`` setting falls back to its ``llm_*`` counterpart at call
time, so a single-provider setup is zero-config: just point ``LLM_BASE_URL``
+ ``LLM_API_KEY`` at the provider and override ``EMBEDDING_MODEL_NAME``.

We do not import or depend on langchain — this is a thin httpx wrapper that
matches the OpenAI ``/v1/embeddings`` JSON shape and nothing else.
"""

from typing import Any

import httpx

from app.core.config import settings


# 中文说明：embedding 端点通常比生成端点快，但自建或兼容接口可能抖动，所以保留独立超时。
# Per-call timeout; embeddings are usually << 1s even for large batches,
# but Chinese-locale providers and self-hosted endpoints can be slower.
EMBEDDING_CONNECT_TIMEOUT_SECONDS = 10.0
EMBEDDING_READ_TIMEOUT_SECONDS = 60.0

# 中文说明：批量大小留出余量，避免兼容服务没有完全实现 OpenAI 上限时被打爆。
# OpenAI caps text-embedding-3 at 2048 inputs per call. Keep some margin so
# we don't accidentally tip a self-hosted clone with a smaller cap.
MAX_BATCH = 256


class EmbeddingConfigError(Exception):
    """Embedding 端点缺配置时抛出。

    Surfaces as a friendly error in the knowledge-indexing path: the document
    stays in status=failed with this message in ``error_detail``, and the
    user can fix env + click "重新索引" from the UI.
    """


class EmbeddingClientError(Exception):
    """远端、网络或响应格式错误时抛出。"""


class EmbeddingClient:
    """OpenAI-compatible embeddings client (``POST /embeddings``)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        # 中文说明：优先使用显式 embedding 配置；没配时复用 LLM 配置，降低单供应商部署门槛。
        # Lazy fallback: prefer explicit embedding settings, then mirror the
        # chat-completion endpoint. None at call time → EmbeddingConfigError.
        self._base_url = base_url or settings.embedding_base_url or settings.llm_base_url
        self._api_key = api_key or settings.embedding_api_key or settings.llm_api_key
        self._model_name = (
            model_name or settings.embedding_model_name
        )
        self._dimensions = dimensions or settings.embedding_dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """将一批文本转成向量，并保持返回顺序与输入顺序一致。

        Empty input → returns empty list immediately so callers don't have
        to special-case zero-chunk documents.
        """
        if not texts:
            return []

        # 中文说明：这里不在构造函数里失败，方便测试或调用方用空输入短路。
        if (
            not self._base_url
            or not self._api_key
            or not self._model_name
        ):
            raise EmbeddingConfigError(
                "Embedding endpoint is not configured. "
                "Set EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL_NAME "
                "(or share with LLM_*).",
            )

        url = f"{self._base_url.rstrip('/')}/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        timeout = httpx.Timeout(
            EMBEDDING_READ_TIMEOUT_SECONDS,
            connect=EMBEDDING_CONNECT_TIMEOUT_SECONDS,
        )

        # 中文说明：分批请求后按顺序拼回，保证 chunk_index 与 embedding 结果一一对应。
        # Slice into MAX_BATCH-sized requests and concatenate. OpenAI returns
        # results in input order so concatenation preserves alignment.
        results: list[list[float]] = []
        async with httpx.AsyncClient(timeout=timeout) as client:
            for start in range(0, len(texts), MAX_BATCH):
                batch = texts[start:start + MAX_BATCH]
                payload: dict[str, Any] = {
                    "model": self._model_name,
                    "input": batch,
                    "dimensions": self._dimensions,
                }
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except httpx.HTTPError as exc:
                    raise EmbeddingClientError(
                        f"Embedding request failed: {exc}",
                    ) from exc

                if response.status_code >= 400:
                    raise EmbeddingClientError(
                        f"Embedding request returned {response.status_code}: "
                        f"{response.text[:200]}",
                    )

                try:
                    body = response.json()
                except ValueError as exc:
                    raise EmbeddingClientError(
                        "Embedding response is not valid JSON",
                    ) from exc

                data = body.get("data") if isinstance(body, dict) else None
                if not isinstance(data, list) or len(data) != len(batch):
                    raise EmbeddingClientError(
                        "Embedding response payload shape unexpected",
                    )

                for item in data:
                    vec = item.get("embedding") if isinstance(item, dict) else None
                    if not isinstance(vec, list) or not vec:
                        raise EmbeddingClientError(
                            "Embedding response missing vector",
                        )
                    # 中文说明：pgvector 列是固定维度，维度漂移必须尽早失败，不能写入脏向量。
                    if len(vec) != self._dimensions:
                        raise EmbeddingClientError(
                            f"Embedding dim mismatch: got {len(vec)} expected "
                            f"{self._dimensions}. Update EMBEDDING_DIMENSIONS "
                            "+ rerun migrations to switch models.",
                        )
                    results.append([float(x) for x in vec])

        return results
