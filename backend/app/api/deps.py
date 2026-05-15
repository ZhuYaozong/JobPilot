"""FastAPI 依赖注入公共定义。

认证策略(双模):
1. 请求头带 ``Authorization: Bearer <jwt>`` → JWT 认证(优先)
2. ``settings.auth_dev_mode=True`` 且请求头带 ``X-User-Name`` → dev 模式自动建用户
3. 两者都没有 → 401
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.user_scope_service import (
    DEFAULT_DEMO_USERNAME,
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
    """双模认证:JWT 优先,dev 模式 fallback X-User-Name header。"""
    # 路径 1: JWT Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
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
    if settings.auth_dev_mode:
        return await get_or_create_user_by_username(
            db,
            requested_username=x_user_name or DEFAULT_DEMO_USERNAME,
        )

    raise HTTPException(401, "未认证:请提供 Authorization: Bearer <token>")


CurrentUserDep = Annotated[User, Depends(get_current_user)]
