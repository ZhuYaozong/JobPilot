"""HTTP Reranker 与失败降级测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.rag.reranker import HttpReranker, RerankerError
from app.rag.service import RetrievalService
from app.rag.types import RetrievalHit


def _hit(chunk_id: int, relevance: float) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        document_id=chunk_id,
        document_title=f"doc-{chunk_id}",
        knowledge_base_id=1,
        source_type="manual",
        chunk_index=0,
        char_start=0,
        char_end=10,
        content=f"content-{chunk_id}",
        score=relevance,
        relevance=relevance,
        distance=2 * (1 - relevance),
        rank=chunk_id,
        source="hybrid",
    )


@respx.mock
def test_http_reranker_reorders_candidates() -> None:
    route = respx.post("https://rerank.example/v1/rerank").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.95},
                    {"index": 0, "relevance_score": 0.4},
                ],
            },
        ),
    )
    reranker = HttpReranker(
        base_url="https://rerank.example/v1",
        api_key="secret",
        model_name="reranker-v1",
        timeout_seconds=5,
    )

    hits = asyncio.run(
        reranker.rerank("query", [_hit(1, 0.9), _hit(2, 0.8)], top_k=2),
    )

    assert [hit.chunk_id for hit in hits] == [2, 1]
    assert hits[0].source == "hybrid+rerank"
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer secret"


class _StaticRetriever:
    async def retrieve(self, request, db):  # noqa: ANN001, ANN202
        return [_hit(1, 0.9)]


class _FailingReranker:
    async def rerank(self, query, hits, *, top_k):  # noqa: ANN001, ANN202
        raise RerankerError("temporary failure")


def test_retrieval_service_keeps_recall_order_when_reranker_fails() -> None:
    service = RetrievalService(
        _StaticRetriever(),
        candidate_multiplier=3,
        reranker=_FailingReranker(),
        reranker_fail_open=True,
    )

    hits = asyncio.run(
        service.search(
            AsyncMock(),
            query="q",
            user_id=1,
            knowledge_base_id=None,
            top_k=1,
        ),
    )

    assert hits[0]["chunk_id"] == 1
