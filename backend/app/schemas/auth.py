"""认证相关的请求/响应 schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册请求。"""
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = None
    display_name: str | None = None


class LoginRequest(BaseModel):
    """登录请求。"""
    username: str
    password: str


class UserPublic(BaseModel):
    """用户公开信息（不含密码 hash）。"""
    id: int
    username: str
    display_name: str
    email: str | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """登录/注册成功后返回的 token + 用户信息。"""
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
