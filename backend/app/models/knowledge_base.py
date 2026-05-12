from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeBase(Base):
    """A user-owned collection of documents.

    The user creates one or more KBs (e.g. "公司资料", "项目素材",
    "面试资料"), uploads documents into each, and selects which to use as
    context in the AI assistant. ACL is by ``user_id`` only — no team /
    sharing in this slice.
    """

    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    # "active" / "archived"; archived KBs hidden from default lists but
    # documents stay searchable until the user explicitly deletes.
    status: Mapped[str] = mapped_column(String(50), server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
