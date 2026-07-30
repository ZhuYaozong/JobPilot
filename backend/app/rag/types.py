"""检索层内部使用的稳定数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """一次限定在当前用户知识空间内的检索请求。"""

    query: str
    user_id: int
    knowledge_base_id: int | None
    top_k: int
    candidate_k: int


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """Retriever 之间传递的统一命中结果。"""

    chunk_id: int
    document_id: int
    document_title: str
    knowledge_base_id: int
    source_type: str
    chunk_index: int
    char_start: int
    char_end: int
    content: str
    score: float
    relevance: float
    distance: float
    rank: int
    source: str
