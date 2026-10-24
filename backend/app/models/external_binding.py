"""绑定挑战、尝试限流与成功审计；不保存任何明文凭据。"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExternalBindingChallenge(Base):
    __tablename__ = "external_binding_challenges"
    __table_args__ = (
        CheckConstraint("status IN ('pending','succeeded','conflict')", name="ck_binding_challenge_status"),
        CheckConstraint("(status = 'succeeded') = (mapping_id IS NOT NULL)", name="ck_binding_challenge_mapping"),
        CheckConstraint("expires_at > created_at", name="ck_binding_challenge_expiry"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    local_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    client_id: Mapped[str] = mapped_column(String(255))
    session_id: Mapped[str] = mapped_column(String(512))
    local_token_digest: Mapped[str] = mapped_column(String(64))
    secret_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    mapping_id: Mapped[int | None] = mapped_column(ForeignKey("external_identities.id", ondelete="RESTRICT"))


class ExternalBindingAudit(Base):
    __tablename__ = "external_binding_audits"
    __table_args__ = (
        UniqueConstraint("challenge_id", name="uq_binding_audit_challenge"),
        CheckConstraint("action IN ('bind','already_bound')", name="ck_binding_audit_action"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("external_binding_challenges.id", ondelete="RESTRICT"))
    mapping_id: Mapped[int] = mapped_column(ForeignKey("external_identities.id", ondelete="RESTRICT"))
    local_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    client_id: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExternalBindingAttempt(Base):
    __tablename__ = "external_binding_attempts"
    __table_args__ = (
        Index("ix_binding_attempt_window", "local_user_id", "kind", "created_at"),
        CheckConstraint("kind IN ('create','confirm')", name="ck_binding_attempt_kind"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    local_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(16))
    request_id: Mapped[UUID] = mapped_column(default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
