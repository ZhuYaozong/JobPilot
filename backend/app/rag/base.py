"""Retriever 与 Reranker 的抽象接口。"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.types import RetrievalHit, RetrievalRequest


class Retriever(Protocol):
    """所有召回策略必须实现的异步接口。"""

    async def retrieve(
        self,
        request: RetrievalRequest,
        db: AsyncSession,
    ) -> list[RetrievalHit]: ...


class Reranker(Protocol):
    """独立于召回实现的候选重排接口。"""

    async def rerank(
        self,
        query: str,
        hits: list[RetrievalHit],
        *,
        top_k: int,
    ) -> list[RetrievalHit]: ...
