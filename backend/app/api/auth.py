"""注册 / 登录 / 获取当前用户信息。

- ``/api/auth/register`` — 用户名+密码注册,返回 JWT token
- ``/api/auth/login`` — 用户名+密码登录,返回 JWT token
- ``/api/auth/me`` — 验证 token 有效性,返回当前用户信息
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUserDep, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services.user_scope_service import normalize_username

from sqlalchemy import select

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: DbSession):
    """注册新用户。用户名全局唯一,email 可选但若填写也必须唯一。"""
    username = normalize_username(body.username)

    # 检查用户名是否已被注册(含 dev 模式自动创建的用户)
    existing = await db.execute(
        select(User).where(User.username == username),
    )
    existing_user = existing.scalar_one_or_none()

    if existing_user is not None:
        # 已有同名用户且有密码 → 真正的重复注册
        if existing_user.hashed_password is not None:
            raise HTTPException(409, "用户名已被注册")
        # 已有同名用户但无密码 → dev 模式创建的空壳,升级为正式用户
        existing_user.hashed_password = hash_password(body.password)
        existing_user.is_active = True
        if body.email:
            existing_user.email = body.email
        if body.display_name:
            existing_user.display_name = body.display_name
        await db.commit()
        await db.refresh(existing_user)
        token = create_access_token(existing_user.id, existing_user.username)
        return TokenResponse(
            access_token=token,
            user=UserPublic.model_validate(existing_user),
        )

    # email 唯一性检查
    if body.email:
        email_exists = await db.execute(
            select(User.id).where(User.email == body.email),
        )
        if email_exists.scalar_one_or_none() is not None:
            raise HTTPException(409, "该邮箱已被注册")

    user = User(
        username=username,
        display_name=body.display_name or username.replace("-", " ").replace("_", " ").title(),
        email=body.email,
        hashed_password=hash_password(body.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user=UserPublic.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession):
    """用户名+密码登录,返回 JWT token。"""
    username = normalize_username(body.username)
    result = await db.execute(
        select(User).where(User.username == username),
    )
    user = result.scalar_one_or_none()

    if user is None or user.hashed_password is None:
        raise HTTPException(401, "用户名或密码错误")

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "用户名或密码错误")

    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")

    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: CurrentUserDep):
    """获取当前认证用户的公开信息。验证 token 是否有效。"""
    return UserPublic.model_validate(current_user)
