from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeBase(Base):
    """用户拥有的一组知识库文档。

    用户可以创建多个 KB，例如“公司资料”“项目素材”“面试资料”，再在 Assistant 里选择
    某一个作为上下文。当前切片只按 ``user_id`` 做权限隔离，没有团队共享模型。
    """

    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    # ``active`` / ``archived``：归档库默认列表隐藏，但文档仍保留，直到用户显式删除。
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
