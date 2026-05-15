"""为 users 表添加认证字段

修订 ID: c7e2a1f34b89
上一修订: b71f4c8a92e1
创建时间: 2026-05-15 12:00:00.000000

给 users 表加 email / hashed_password / is_active 三列,支持
注册登录认证。全部 nullable 或有默认值,不影响已有数据。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic 使用的修订标识。
revision: str = "c7e2a1f34b89"
down_revision: Union[str, Sequence[str], None] = "b71f4c8a92e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 schema:添加认证字段。"""
    op.add_column(
        "users",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """回退 schema:移除认证字段。"""
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "is_active")
    op.drop_column("users", "hashed_password")
    op.drop_column("users", "email")
