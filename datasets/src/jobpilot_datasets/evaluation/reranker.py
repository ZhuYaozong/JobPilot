"""实验候选集的独立 Reranker。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

import httpx

from jobpilot_datasets.config import ProviderConfig
from jobpilot_datasets.evaluation.retrieval import SearchResult
from jobpilot_datasets.providers.base import (
    ProviderConfigurationError,
    ProviderRequestError,
)


class RerankingProvider(Protocol):
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        *,
        top_k: int,
    ) -> list[SearchResult]: ...

    async def close(self) -> None: ...


class HttpRerankingProvider:
    """调用 ``POST /rerank``；实验失败会显式记为 case error。"""

    def __init__(self, config: ProviderConfig) -> None:
        if not config.base_url.strip() or not config.model.strip():
            raise ProviderConfigurationError("Reranker Provider 缺少 base_url 或 model")
        self.config = config
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        *,
        top_k: int,
    ) -> list[SearchResult]:
        if not results:
            return []
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        try:
            response = await self._client.post(
                f"{self.config.base_url.rstrip('/')}/rerank",
                headers=headers,
                json={
                    "model": self.config.model,
                    "query": query,
                    "documents": [item.chunk.text for item in results],
                    "top_n": min(top_k, len(results)),
                },
            )
            response.raise_for_status()
            body = response.json()
            parsed = self._parse(body.get("results"), len(results))
        except (httpx.HTTPError, AttributeError, ValueError) as exc:
            raise ProviderRequestError(f"Reranker 请求失败: {exc}") from exc
        if not parsed:
            raise ProviderRequestError("Reranker 未返回有效结果")
        return [
            replace(
                results[index],
                score=score,
                rank=rank,
                retrieval_source=f"{results[index].retrieval_source}+rerank",
            )
            for rank, (index, score) in enumerate(parsed[:top_k], start=1)
        ]

    @staticmethod
    def _parse(value: Any, count: int) -> list[tuple[int, float]]:
        if not isinstance(value, list):
            return []
        parsed: list[tuple[int, float]] = []
        seen: set[int] = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            score = item.get("relevance_score", item.get("score"))
            if (
                isinstance(index, int)
                and 0 <= index < count
                and index not in seen
                and isinstance(score, (int, float))
            ):
                parsed.append((index, float(score)))
                seen.add(index)
        return sorted(parsed, key=lambda item: (-item[1], item[0]))

    async def close(self) -> None:
        await self._client.aclose()
