"""在独立短事务中解析外部身份；并发唯一冲突只回滚本次开户。"""
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.delegated_security import VerifiedExternalIdentity
from app.models.external_identity import ExternalIdentity
from app.models.user import User


async def resolve_external_user(db: AsyncSession, identity: VerifiedExternalIdentity) -> User:
    # 只接受验证层构建的身份，调用方必须使用尚未开启事务的新 session。
    statement = select(ExternalIdentity).where(ExternalIdentity.issuer == identity.issuer, ExternalIdentity.subject == identity.subject)
    async with db.begin():
        mapping = (await db.execute(statement)).scalar_one_or_none()
        if mapping is None:
            try:
                async with db.begin_nested():
                    user = User(username="ext_" + uuid4().hex, display_name="外部用户", is_active=True, is_test_user=False, email=None, hashed_password=None)
                    db.add(user)
                    await db.flush()
                    mapping = ExternalIdentity(issuer=identity.issuer, subject=identity.subject, user_id=user.id)
                    db.add(mapping)
                    await db.flush()
            except IntegrityError as error:
                # PostgreSQL 唯一约束保证竞争者提交后才能报告冲突。
                cause = error.orig
                constraint = getattr(getattr(cause, "__cause__", None), "constraint_name", None)
                if constraint != "uq_external_identity_issuer_subject":
                    raise
                mapping = (await db.execute(statement)).scalar_one()
        user = await db.get(User, mapping.user_id)
        if user is None or not user.is_active:
            raise HTTPException(403, "账号已被禁用")
        return user
