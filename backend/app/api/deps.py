"""FastAPI 依赖注入公共定义。

认证策略(双模):
1. 请求头带 ``Authorization: Bearer <jwt>`` → JWT 认证(优先)
2. local/test 显式开启开发认证且提供非空 ``X-User-Name`` → 受限开发账号
3. 两者都没有 → 401
"""

from typing import Annotated
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, Query
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.delegated_security import VerifiedExternalIdentity
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.user_scope_service import (
    get_or_create_user_by_username,
)

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100
DEFAULT_LIST_OFFSET = 0

ListLimit = Annotated[
    int,
    Query(
        ge=1,
        le=MAX_LIST_LIMIT,
        description="返回最近优先记录的最大数量。",
    ),
]
ListOffset = Annotated[
    int,
    Query(
        ge=0,
        description="最近优先排序后的零基偏移量。",
    ),
]

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
) -> User:
    """有认证头就严格验证；仅无认证头时允许显式开发身份。"""
    # 路径 1: JWT Bearer token
    if authorization is not None:
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token or any(char.isspace() for char in token):
            raise HTTPException(401, "认证头格式无效")
        try:
            payload = decode_access_token(token)
        except JWTError:
            raise HTTPException(401, "token 无效或已过期")
        user_id = int(payload["sub"])
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(401, "用户不存在")
        if not user.is_active:
            raise HTTPException(403, "账号已被禁用")
        return user

    # 路径 2: dev 模式 X-User-Name header
    if settings.auth_dev_mode and settings.app_env in {"local", "test"}:
        if not x_user_name or not x_user_name.strip():
            raise HTTPException(401, "开发认证必须显式提供 X-User-Name")
        return await get_or_create_user_by_username(
            db,
            requested_username=x_user_name,
        )

    raise HTTPException(401, "未认证:请提供 Authorization: Bearer <token>")


CurrentUserDep = Annotated[User, Depends(get_current_user)]



@lru_cache
def get_delegated_verifier():
    from app.core.delegated_security import DelegatedTokenVerifier
    return DelegatedTokenVerifier(settings)


@dataclass(frozen=True)
class DelegatedUserContext:
    # 身份由验证器创建，本地 user 由映射事务解析，不使用请求自报 ID。
    identity: "VerifiedExternalIdentity"
    user: User


async def get_delegated_context(
    db: DbSession,
    verifier=Depends(get_delegated_verifier),
    authorization: Annotated[str | None, Header()] = None,
) -> DelegatedUserContext:
    from app.core.delegated_security import unauthorized
    from app.services.external_identity_service import resolve_external_user
    if not verifier.config.delegated_auth_enabled:
        raise HTTPException(404, "受托身份入口未启用")
    scheme, separator, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not token or any(char.isspace() for char in token):
        raise unauthorized()
    identity = await verifier.verify(token)
    user = await resolve_external_user(db, identity)
    return DelegatedUserContext(identity, user)


DelegatedIdentityDep = Annotated[DelegatedUserContext, Depends(get_delegated_context)]
