"""把内部检索结果映射成兼容的 Agent 工具上下文。"""

from __future__ import annotations

from typing import Any

from app.rag.types import RetrievalHit


MAX_CONTENT_PREVIEW_CHARS = 600


class ContextBuilder:
    """保持旧 ``search_knowledge`` hits JSON 结构。"""

    def build_hits(
        self,
        hits: list[RetrievalHit],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": hit.chunk_id,
                "document_id": hit.document_id,
                "document_title": hit.document_title,
                "knowledge_base_id": hit.knowledge_base_id,
                "source_type": hit.source_type,
                "chunk_index": hit.chunk_index,
                "char_start": hit.char_start,
                "char_end": hit.char_end,
                "content": trim_content(hit.content, MAX_CONTENT_PREVIEW_CHARS),
                "distance": float(hit.distance),
                "relevance": float(hit.relevance),
            }
            for hit in hits[:top_k]
        ]


def trim_content(text: str, max_chars: int) -> str:
    """优先在空白边界裁剪，中文无空格时退化为字符截断。"""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    if last_space > max_chars - 80:
        cut = cut[:last_space]
    return cut + "…"
