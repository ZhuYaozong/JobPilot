"""独立的 HTTP Reranker 客户端。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import httpx

from app.rag.types import RetrievalHit


class RerankerError(RuntimeError):
    """Reranker 配置、网络或响应格式异常。"""


class HttpReranker:
    """调用常见 ``POST /rerank`` 协议并映射回原候选。"""

    def __init__(
        self,
        *,
        base_url: str | None,
        api_key: str | None,
        model_name: str | None,
        timeout_seconds: float,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    async def rerank(
        self,
        query: str,
        hits: list[RetrievalHit],
        *,
        top_k: int,
    ) -> list[RetrievalHit]:
        if not hits:
            return []
        if not self.base_url or not self.model_name:
            raise RerankerError(
                "Reranker endpoint is not configured. Set RERANKER_BASE_URL "
                "and RERANKER_MODEL_NAME.",
            )

        payload = {
            "model": self.model_name,
            "query": query,
            "documents": [hit.content for hit in hits],
            "top_n": min(top_k, len(hits)),
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/rerank",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RerankerError(f"Reranker request failed: {exc}") from exc

        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            raise RerankerError("Reranker response missing results list")
        parsed = self._parse_results(results, len(hits))
        if not parsed:
            raise RerankerError("Reranker response contains no valid results")

        scores = [score for _, score in parsed]
        low, high = min(scores), max(scores)
        output: list[RetrievalHit] = []
        for rank, (index, score) in enumerate(parsed[:top_k], start=1):
            relevance = (
                (score - low) / (high - low)
                if high > low
                else max(0.0, min(1.0, score))
            )
            output.append(
                replace(
                    hits[index],
                    score=score,
                    relevance=relevance,
                    distance=2.0 * (1.0 - relevance),
                    rank=rank,
                    source=f"{hits[index].source}+rerank",
                ),
            )
        return output

    @staticmethod
    def _parse_results(
        results: list[Any],
        candidate_count: int,
    ) -> list[tuple[int, float]]:
        parsed: list[tuple[int, float]] = []
        seen: set[int] = set()
        for item in results:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            score = item.get("relevance_score", item.get("score"))
            if (
                isinstance(index, int)
                and 0 <= index < candidate_count
                and index not in seen
                and isinstance(score, (int, float))
            ):
                parsed.append((index, float(score)))
                seen.add(index)
        parsed.sort(key=lambda item: (-item[1], item[0]))
        return parsed
