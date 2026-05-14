from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

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
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
) -> User:
    return await get_or_create_user_by_username(
        db,
        requested_username=x_user_name or DEFAULT_DEMO_USERNAME,
    )


CurrentUserDep = Annotated[User, Depends(get_current_user)]
