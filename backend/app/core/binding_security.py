"""绑定凭据只在当前调用内使用，校验异常不包含原始输入。"""
from dataclasses import dataclass
from hashlib import sha256
import secrets

import anyio
from fastapi import HTTPException
from jose import JWTError

from app.core.security import decode_access_token, verify_password

# 单进程限制 CPU 密集的 bcrypt 并发；持久限流由数据库另行保证。
_password_limiter = anyio.CapacityLimiter(4)


@dataclass(frozen=True, repr=False)
class LocalBindingCredential:
    user_id: int
    token_digest: str
    expires_at: float


def digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def bearer(value: str | None) -> str:
    scheme, separator, token = (value or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not token or len(token) > 16384 or any(c.isspace() for c in token):
        raise HTTPException(401, "绑定认证失败")
    return token


def local_credential(value: str | None) -> LocalBindingCredential:
    token = bearer(value)
    try:
        payload = decode_access_token(token)
        return LocalBindingCredential(int(payload["sub"]), digest(token), payload["exp"])
    except JWTError:
        raise HTTPException(401, "绑定认证失败") from None


async def check_password(password: str, hashed: str | None):
    if hashed is None or not 1 <= len(password.encode("utf-8")) <= 72:
        raise HTTPException(401, "绑定认证失败")
    try:
        valid = await anyio.to_thread.run_sync(verify_password, password, hashed, limiter=_password_limiter)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(401, "绑定认证失败")


def challenge_secret() -> str:
    return secrets.token_urlsafe(32)
