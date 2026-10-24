"""新增外部身份唯一映射；不更新或认领历史用户。

Revision ID: f29b6a70d183
Revises: e8f3a1c9d204
"""
import sqlalchemy as sa
from alembic import op

revision = "f29b6a70d183"
down_revision = "e8f3a1c9d204"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_external_identity_issuer_subject"),
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])


def downgrade():
    # 禁止自动丢弃已有身份关联；上线后需单独备份与受控回滚流程。
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM external_identities)")).scalar():
        raise RuntimeError("外部身份表非空，禁止自动降级；请先执行受控备份和迁移")
    op.drop_index("ix_external_identities_user_id", table_name="external_identities")
    op.drop_table("external_identities")
