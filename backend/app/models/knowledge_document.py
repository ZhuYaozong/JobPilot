from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeDocument(Base):
    """知识库中的单份文档。

    文档同时保存原始文本和冗余 ``user_id``。原始文本用于重新切片和详情展示；
    ``user_id`` 让 chunks 表可以直接按用户过滤，不必每次 join 回文档表。``status``
    驱动索引状态机：

        pending -> parsing -> ready
                          \\-> failed
    """

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512))
    # 来源类型：pdf / docx / markdown / text / manual，其中 manual 表示用户粘贴输入。
    source_type: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    raw_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    chunk_count: Mapped[int] = mapped_column(Integer, server_default="0")
    # 初始为 pending，索引流程会推进到 parsing / ready / failed。
    status: Mapped[str] = mapped_column(String(50), server_default="pending")
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
