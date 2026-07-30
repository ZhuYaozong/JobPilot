"""向量与 BM25 召回的加权 RRF 融合。"""

from __future__ import annotations

import logging
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.embedding_client import EmbeddingClientError, EmbeddingConfigError
from app.rag.base import Retriever
from app.rag.types import RetrievalHit, RetrievalRequest


logger = logging.getLogger(__name__)


class HybridRetriever:
    """按 chunk 去重并融合两路排名，避免直接混合异构分数。"""

    def __init__(
        self,
        vector_retriever: Retriever,
        bm25_retriever: Retriever,
        *,
        rrf_k: int = 60,
        vector_weight: float = 1.0,
        bm25_weight: float = 1.0,
        vector_fail_open: bool = True,
    ) -> None:
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.vector_fail_open = vector_fail_open

    async def retrieve(
        self,
        request: RetrievalRequest,
        db: AsyncSession,
    ) -> list[RetrievalHit]:
        # AsyncSession 不允许并发执行 SQL，因此两路召回有意串行。
        try:
            vector_hits = await self.vector_retriever.retrieve(request, db)
        except (EmbeddingConfigError, EmbeddingClientError) as exc:
            if not self.vector_fail_open:
                raise
            logger.warning(
                "Hybrid vector recall degraded to BM25: %s",
                type(exc).__name__,
            )
            vector_hits = []
        bm25_hits = await self.bm25_retriever.retrieve(request, db)

        scores: dict[int, float] = {}
        representatives: dict[int, RetrievalHit] = {}
        for hits, weight in (
            (vector_hits, self.vector_weight),
            (bm25_hits, self.bm25_weight),
        ):
            for rank, hit in enumerate(hits, start=1):
                scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + (
                    weight / (self.rrf_k + rank)
                )
                representatives.setdefault(hit.chunk_id, hit)

        ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
        ordered = ordered[:request.candidate_k]
        max_score = scores[ordered[0]] if ordered else 1.0
        return [
            replace(
                representatives[chunk_id],
                score=scores[chunk_id],
                relevance=scores[chunk_id] / max(max_score, 1e-12),
                distance=2.0 * (1.0 - scores[chunk_id] / max(max_score, 1e-12)),
                rank=rank,
                source="hybrid",
            )
            for rank, chunk_id in enumerate(ordered, start=1)
        ]
