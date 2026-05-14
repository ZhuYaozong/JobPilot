"""OpenAI 兼容的 embeddings 客户端。

这是 JobPilot 的向量化适配层，专门服务知识库索引和
``search_knowledge`` 工具。它故意独立于聊天 LLM client，这样部署时可以
用不同供应商分别承载生成模型和 embedding 模型。

和 :class:`app.llm.client.LLMClient` 分开实现，是为了让部署可以通过
``embedding_*`` 环境变量把向量请求路由到另一个供应商。例如聊天生成走本地
Llama，而 embedding 走更擅长中文语义的 OpenAI 兼容服务。

每个 ``embedding_*`` 配置都会在调用时回退到对应的 ``llm_*`` 配置。单供应商
部署只需要配置 ``LLM_BASE_URL`` 和 ``LLM_API_KEY``，再按需覆盖
``EMBEDDING_MODEL_NAME`` 即可。

这里不依赖 langchain，只是一个很薄的 httpx wrapper，按 OpenAI
``/v1/embeddings`` JSON 形状收发数据。
"""

from typing import Any

import httpx

from app.core.config import settings


# embedding 端点通常比生成端点快，但自建或兼容接口可能抖动，所以保留独立超时。
# 向量批量请求通常很快，但自建端点和国内兼容服务可能有连接抖动或冷启动。
EMBEDDING_CONNECT_TIMEOUT_SECONDS = 10.0
EMBEDDING_READ_TIMEOUT_SECONDS = 60.0

# 批量大小留出余量，避免兼容服务没有完全实现 OpenAI 上限时被打爆。
# OpenAI text-embedding-3 每次最多 2048 条输入；这里压到 256，兼容更保守的自建服务。
MAX_BATCH = 256


class EmbeddingConfigError(Exception):
    """Embedding 端点缺配置时抛出。

    知识库索引路径会把它转成用户可理解的失败状态：文档保持 ``status=failed``，
    错误写入 ``error_detail``，用户修正环境变量后可以在 UI 里点击“重新索引”。
    """


class EmbeddingClientError(Exception):
    """远端、网络或响应格式错误时抛出。"""


class EmbeddingClient:
    """OpenAI 兼容的 embeddings client，实际请求路径是 ``POST /embeddings``。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        # 优先使用显式 embedding 配置；没配时复用 LLM 配置，降低单供应商部署门槛。
        # 不在构造函数立刻报错，方便空输入短路和测试覆盖。
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

        空输入直接返回空列表，调用方不需要为“零 chunk 文档”单独写分支。
        """
        if not texts:
            return []

        # 这里不在构造函数里失败，方便测试或调用方用空输入短路。
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

        # 分批请求后按顺序拼回，保证 chunk_index 与 embedding 结果一一对应。
        # OpenAI 兼容协议要求 data 顺序与 input 顺序一致；如果供应商不遵守，后面的
        # 检索溯源就会把 chunk 和向量错配。
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
                    # pgvector 列是固定维度，维度漂移必须尽早失败，不能写入脏向量。
                    if len(vec) != self._dimensions:
                        raise EmbeddingClientError(
                            f"Embedding dim mismatch: got {len(vec)} expected "
                            f"{self._dimensions}. Update EMBEDDING_DIMENSIONS "
                            "+ rerun migrations to switch models.",
                        )
                    results.append([float(x) for x in vec])

        return results
