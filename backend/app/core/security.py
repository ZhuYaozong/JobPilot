"""密码哈希与 JWT token 工具。

- 密码用 bcrypt 哈希，verify 时自动处理 salt
- JWT 使用 HS256，payload 里放 ``sub``(user_id) 和 ``username``
- token 过期时间由 ``settings.auth_access_token_expire_minutes`` 控制
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    """明文 → bcrypt hash。"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文是否匹配 bcrypt hash。"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, username: str) -> str:
    """生成 JWT access token。

    payload:
    - sub: user_id（主键，不可变）
    - username: 用于调试/日志，不做认证依据
    - exp: 过期时间戳
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.auth_access_token_expire_minutes,
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def decode_access_token(token: str) -> dict:
    """解码并验证 JWT token，返回 payload dict。

    失败时抛 ``JWTError``（过期、签名错、格式错等）。
    """
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[settings.auth_algorithm],
        )
        if payload.get("sub") is None:
            raise JWTError("token 缺少 sub 字段")
        return payload
    except JWTError:
        raise
