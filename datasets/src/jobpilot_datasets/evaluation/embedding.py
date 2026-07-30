"""实验用 OpenAI-compatible Embedding 客户端。"""

from __future__ import annotations

from typing import Protocol

import httpx

from jobpilot_datasets.config import ProviderConfig
from jobpilot_datasets.providers.base import (
    ProviderConfigurationError,
    ProviderRequestError,
)


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def close(self) -> None: ...


class OpenAIEmbeddingProvider:
    """复用 Provider 配置调用 ``POST /embeddings``。"""

    def __init__(self, config: ProviderConfig) -> None:
        if not config.base_url.strip() or not config.model.strip():
            raise ProviderConfigurationError("Embedding Provider 缺少 base_url 或 model")
        self.config = config
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        try:
            response = await self._client.post(
                f"{self.config.base_url.rstrip('/')}/embeddings",
                headers=headers,
                json={"model": self.config.model, "input": texts},
            )
            response.raise_for_status()
            body = response.json()
            data = body["data"]
            ordered = sorted(data, key=lambda item: item.get("index", 0))
            vectors = [item["embedding"] for item in ordered]
            if len(vectors) != len(texts) or any(not vector for vector in vectors):
                raise ValueError("embedding 数量或内容异常")
            return [[float(value) for value in vector] for vector in vectors]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderRequestError(f"Embedding 请求失败: {exc}") from exc

    async def close(self) -> None:
        await self._client.aclose()
