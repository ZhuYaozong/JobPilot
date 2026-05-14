"""``/api/v1/knowledge`` 的 Pydantic schema。

这里有三类资源：
- KnowledgeBase：知识库容器。
- KnowledgeDocument：知识库里的单份文档。
- KnowledgeChunk：只读预览对象，用户不能直接创建 chunk。

命名风格和 resume / job schema 保持一致，便于前端按相同方式组织 API 类型。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------- 知识库 --------------------------------------------------------


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
    # 便捷计数：侧栏展示“N 份资料”时不需要为每个知识库再发一次请求。
    # 该字段由 service 层查询时填充，不是数据库列。
    document_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseRead(KnowledgeBaseListItem):
    pass


# ---------- 文档 ----------------------------------------------------------


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
