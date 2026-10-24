"""新增有证明绑定的挑战、限流、审计与每发行者单身份约束。

Revision ID: a41c98d72b60
Revises: f29b6a70d183
"""
from alembic import op
import sqlalchemy as sa

revision = "a41c98d72b60"
down_revision = "f29b6a70d183"
branch_labels = None
depends_on = None


def upgrade():
    # 绝不猜测哪一条存量关联应保留；冲突时整次迁移失败。
    duplicate = op.get_bind().execute(sa.text("SELECT 1 FROM external_identities GROUP BY issuer,user_id HAVING count(*) > 1 LIMIT 1")).first()
    if duplicate:
        raise RuntimeError("存在同一发行者下重复的账号映射，请先完成受控审查")
    op.create_unique_constraint("uq_external_identity_issuer_user", "external_identities", ["issuer", "user_id"])
    op.create_table("external_binding_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("local_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False), sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False), sa.Column("session_id", sa.String(512), nullable=False),
        sa.Column("local_token_digest", sa.String(64), nullable=False), sa.Column("secret_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("mapping_id", sa.Integer(), sa.ForeignKey("external_identities.id", ondelete="RESTRICT")),
        sa.CheckConstraint("status IN ('pending','succeeded','conflict')", name="ck_binding_challenge_status"),
        sa.CheckConstraint("(status = 'succeeded') = (mapping_id IS NOT NULL)", name="ck_binding_challenge_mapping"),
        sa.CheckConstraint("expires_at > created_at", name="ck_binding_challenge_expiry"))
    op.create_table("external_binding_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("challenge_id", sa.Uuid(), sa.ForeignKey("external_binding_challenges.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mapping_id", sa.Integer(), sa.ForeignKey("external_identities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("local_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False), sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False), sa.Column("action", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("challenge_id", name="uq_binding_audit_challenge"),
        sa.CheckConstraint("action IN ('bind','already_bound')", name="ck_binding_audit_action"))
    op.create_table("external_binding_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("local_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False), sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('create','confirm')", name="ck_binding_attempt_kind"))
    op.create_index("ix_binding_attempt_window", "external_binding_attempts", ["local_user_id", "kind", "created_at"])


def downgrade():
    # 即便挑战仅过期也承载安全证据，不能自动删表降级。
    for table in ("external_binding_audits", "external_binding_challenges", "external_binding_attempts", "external_identities"):
        if op.get_bind().execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("绑定相关数据非空，禁止自动降级")
    op.drop_index("ix_binding_attempt_window", table_name="external_binding_attempts")
    op.drop_table("external_binding_attempts")
    op.drop_table("external_binding_audits")
    op.drop_table("external_binding_challenges")
    op.drop_constraint("uq_external_identity_issuer_user", "external_identities", type_="unique")
