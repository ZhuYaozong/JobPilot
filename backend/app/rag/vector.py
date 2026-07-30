"""基于 pgvector 的向量召回实现。"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.embedding_client import EmbeddingClient
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.rag.types import RetrievalHit, RetrievalRequest


class EmptyQueryEmbeddingError(RuntimeError):
    """Embedding 服务异常返回空向量列表。"""


class VectorRetriever:
    """保持原 search_knowledge cosine distance 语义的 Retriever。"""

    def __init__(
        self,
        embedding_client_factory: Callable[[], EmbeddingClient] = EmbeddingClient,
    ) -> None:
        self._embedding_client_factory = embedding_client_factory

    async def retrieve(
        self,
        request: RetrievalRequest,
        db: AsyncSession,
    ) -> list[RetrievalHit]:
        vectors = await self._embedding_client_factory().embed([request.query])
        if not vectors:
            raise EmptyQueryEmbeddingError("embedding API returned no vectors")

        distance_expr = KnowledgeChunk.embedding.cosine_distance(vectors[0])
        stmt = (
            select(
                KnowledgeChunk.id,
                KnowledgeChunk.document_id,
                KnowledgeChunk.chunk_index,
                KnowledgeChunk.content,
                KnowledgeChunk.char_start,
                KnowledgeChunk.char_end,
                KnowledgeDocument.title,
                KnowledgeDocument.knowledge_base_id,
                KnowledgeDocument.source_type,
                distance_expr.label("distance"),
            )
            .join(
                KnowledgeDocument,
                KnowledgeChunk.document_id == KnowledgeDocument.id,
            )
            .where(
                KnowledgeChunk.user_id == request.user_id,
                KnowledgeChunk.embedding.is_not(None),
            )
        )
        if request.knowledge_base_id is not None:
            stmt = stmt.where(
                KnowledgeDocument.knowledge_base_id == request.knowledge_base_id,
            )
        rows = (
            await db.execute(
                stmt.order_by(distance_expr).limit(request.candidate_k),
            )
        ).all()

        hits: list[RetrievalHit] = []
        for rank, row in enumerate(rows, start=1):
            distance = float(row.distance)
            relevance = max(0.0, min(1.0, 1.0 - distance / 2.0))
            hits.append(
                RetrievalHit(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    document_title=row.title,
                    knowledge_base_id=row.knowledge_base_id,
                    source_type=row.source_type,
                    chunk_index=row.chunk_index,
                    char_start=row.char_start,
                    char_end=row.char_end,
                    content=row.content,
                    score=-distance,
                    relevance=relevance,
                    distance=distance,
                    rank=rank,
                    source="vector",
                ),
            )
        return hits
