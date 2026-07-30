"""Retriever 抽象、BM25 与 Hybrid 融合的确定性测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.embedding_client import EmbeddingConfigError
from app.rag.bm25 import BM25Retriever, tokenize
from app.rag.hybrid import HybridRetriever
from app.rag.types import RetrievalHit, RetrievalRequest


def _hit(chunk_id: int, *, rank: int, source: str) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        document_id=chunk_id,
        document_title=f"doc-{chunk_id}",
        knowledge_base_id=1,
        source_type="manual",
        chunk_index=0,
        char_start=0,
        char_end=10,
        content=f"chunk {chunk_id}",
        score=1.0,
        relevance=1.0,
        distance=0.0,
        rank=rank,
        source=source,
    )


def _request(candidate_k: int = 5) -> RetrievalRequest:
    return RetrievalRequest(
        query="混合 RAG 检索",
        user_id=7,
        knowledge_base_id=3,
        top_k=2,
        candidate_k=candidate_k,
    )


class _StaticRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits

    async def retrieve(self, request, db):  # noqa: ANN001, ANN202
        return self.hits


class _FailingVectorRetriever:
    async def retrieve(self, request, db):  # noqa: ANN001, ANN202
        raise EmbeddingConfigError("missing")


def test_tokenize_supports_chinese_bigrams_and_english_words() -> None:
    tokens = tokenize("Hybrid 混合检索 RAG_v2")
    assert "hybrid" in tokens
    assert "混合" in tokens
    assert "检索" in tokens
    assert "rag_v2" in tokens


def test_bm25_retriever_ranks_matching_chunk_first() -> None:
    rows = [
        SimpleNamespace(
            id=1,
            document_id=11,
            chunk_index=0,
            content="JobPilot 使用混合检索和 RRF 融合排序",
            char_start=0,
            char_end=25,
            title="RAG",
            knowledge_base_id=3,
            source_type="manual",
        ),
        SimpleNamespace(
            id=2,
            document_id=12,
            chunk_index=0,
            content="前端主题色与布局设置",
            char_start=0,
            char_end=12,
            title="UI",
            knowledge_base_id=3,
            source_type="manual",
        ),
    ]
    execute_result = MagicMock()
    execute_result.all.return_value = rows
    db = AsyncMock()
    db.execute.return_value = execute_result

    hits = asyncio.run(BM25Retriever().retrieve(_request(), db))

    assert [hit.chunk_id for hit in hits] == [1]
    assert hits[0].source == "bm25"
    assert hits[0].relevance == 1.0


def test_hybrid_uses_weighted_rrf_and_deduplicates_chunks() -> None:
    vector = _StaticRetriever([_hit(1, rank=1, source="vector"), _hit(2, rank=2, source="vector")])
    bm25 = _StaticRetriever([_hit(2, rank=1, source="bm25"), _hit(3, rank=2, source="bm25")])
    hybrid = HybridRetriever(vector, bm25, rrf_k=10)

    hits = asyncio.run(hybrid.retrieve(_request(candidate_k=3), AsyncMock()))

    assert [hit.chunk_id for hit in hits] == [2, 1, 3]
    assert len({hit.chunk_id for hit in hits}) == 3
    assert all(hit.source == "hybrid" for hit in hits)


def test_hybrid_can_fall_back_to_bm25_when_embedding_is_unavailable() -> None:
    hybrid = HybridRetriever(
        _FailingVectorRetriever(),
        _StaticRetriever([_hit(4, rank=1, source="bm25")]),
        vector_fail_open=True,
    )

    hits = asyncio.run(hybrid.retrieve(_request(), AsyncMock()))

    assert [hit.chunk_id for hit in hits] == [4]
