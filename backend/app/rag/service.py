"""对 Agent 屏蔽召回、融合、重排和 Context 构造细节。"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.base import Reranker, Retriever
from app.rag.context import ContextBuilder
from app.rag.reranker import RerankerError
from app.rag.types import RetrievalRequest


logger = logging.getLogger(__name__)


class RetrievalService:
    """生产 RAG 检索编排服务。"""

    def __init__(
        self,
        retriever: Retriever,
        *,
        candidate_multiplier: int,
        reranker: Reranker | None = None,
        reranker_fail_open: bool = True,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.retriever = retriever
        self.candidate_multiplier = candidate_multiplier
        self.reranker = reranker
        self.reranker_fail_open = reranker_fail_open
        self.context_builder = context_builder or ContextBuilder()

    async def search(
        self,
        db: AsyncSession,
        *,
        query: str,
        user_id: int,
        knowledge_base_id: int | None,
        top_k: int,
    ) -> list[dict[str, object]]:
        candidate_k = min(100, max(top_k, top_k * self.candidate_multiplier))
        request = RetrievalRequest(
            query=query,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            candidate_k=candidate_k,
        )
        hits = await self.retriever.retrieve(request, db)
        if self.reranker is not None:
            try:
                hits = await self.reranker.rerank(query, hits, top_k=top_k)
            except RerankerError as exc:
                if not self.reranker_fail_open:
                    raise
                logger.warning(
                    "Reranker unavailable; preserving recall order: %s",
                    type(exc).__name__,
                )
        return self.context_builder.build_hits(hits, top_k=top_k)
