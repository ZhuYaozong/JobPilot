"""Pydantic schemas for /api/v1/knowledge.

Three resource families:
- KnowledgeBase  (container)
- KnowledgeDocument  (a single uploaded doc inside a KB)
- KnowledgeChunk  (preview-only — full list returned by document detail
  endpoint in 7'c2; chunks are not user-creatable directly)

The naming mirrors the existing resume / job schema modules so the API
shape stays consistent.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------- Knowledge base ------------------------------------------------


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: str = "active"


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None


class KnowledgeBaseListItem(BaseModel):
    id: int
    name: str
    description: str | None
    status: str
    # Convenience counter so the sidebar can show "N 份资料" without an
    # extra round trip per KB. Populated by the service layer at read time.
    document_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseRead(KnowledgeBaseListItem):
    pass


# ---------- Document ------------------------------------------------------


class KnowledgeDocumentListItem(BaseModel):
    id: int
    knowledge_base_id: int
    title: str
    source_type: str
    source_url: str | None
    chunk_count: int
    status: str
    error_detail: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentRead(KnowledgeDocumentListItem):
    raw_text: str
    extra_metadata: dict[str, Any] | None


class KnowledgeChunkPreview(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    extra_metadata: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
