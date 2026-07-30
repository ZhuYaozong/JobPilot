"""无需数据库扩展、兼顾中英文的 BM25 召回。"""

from __future__ import annotations

import math
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.rag.types import RetrievalHit, RetrievalRequest


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """英文按词、中文按单字和双字切分，避免依赖外部分词扩展。"""
    tokens: list[str] = []
    for match in _TOKEN_PATTERN.findall(text.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", match):
            tokens.extend(match)
            tokens.extend(match[index:index + 2] for index in range(len(match) - 1))
        else:
            tokens.append(match)
    return tokens


class BM25Retriever:
    """在已经过 ACL 过滤的用户 chunks 上计算 BM25。"""

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

    async def retrieve(
        self,
        request: RetrievalRequest,
        db: AsyncSession,
    ) -> list[RetrievalHit]:
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
            )
            .join(
                KnowledgeDocument,
                KnowledgeChunk.document_id == KnowledgeDocument.id,
            )
            .where(
                KnowledgeChunk.user_id == request.user_id,
                KnowledgeDocument.status == "ready",
            )
        )
        if request.knowledge_base_id is not None:
            stmt = stmt.where(
                KnowledgeDocument.knowledge_base_id == request.knowledge_base_id,
            )
        rows = (await db.execute(stmt)).all()
        if not rows:
            return []

        frequencies = [Counter(tokenize(row.content)) for row in rows]
        lengths = [sum(counter.values()) for counter in frequencies]
        average_length = sum(lengths) / len(lengths)
        document_frequency: Counter[str] = Counter()
        for counter in frequencies:
            document_frequency.update(counter.keys())
        total = len(rows)
        idf = {
            term: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }
        query_terms = Counter(tokenize(request.query))

        scored: list[tuple[int, float]] = []
        for index, counter in enumerate(frequencies):
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = counter.get(term, 0)
                if frequency == 0:
                    continue
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * lengths[index] / max(average_length, 1)
                )
                score += (
                    idf.get(term, 0.0)
                    * frequency
                    * (self.k1 + 1)
                    / denominator
                    * query_frequency
                )
            if score > 0:
                scored.append((index, score))
        scored.sort(key=lambda item: (-item[1], rows[item[0]].id))
        selected = scored[:request.candidate_k]
        max_score = selected[0][1] if selected else 1.0

        hits: list[RetrievalHit] = []
        for rank, (index, score) in enumerate(selected, start=1):
            row = rows[index]
            relevance = max(0.0, min(1.0, score / max(max_score, 1e-12)))
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
                    score=score,
                    relevance=relevance,
                    distance=2.0 * (1.0 - relevance),
                    rank=rank,
                    source="bm25",
                ),
            )
        return hits
