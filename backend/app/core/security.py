"""密码哈希与 JWT token 工具。

- 密码用 bcrypt 哈希，verify 时自动处理 salt
- JWT 使用 HS256，payload 里放 ``sub``(user_id) 和 ``username``
- token 过期时间由 ``settings.auth_access_token_expire_minutes`` 控制
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re

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
    """校验本地 API JWT；非法字段统一作为认证失败，不让整数转换异常流入 API。"""
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[settings.auth_algorithm],
            options={"require_sub": True, "require_exp": True},
        )
        subject = payload["sub"]
        # users.id 是 PostgreSQL Integer；拒绝负数、超范围值和非规范数字串。
        if not isinstance(subject, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", subject) or int(subject) > 2_147_483_647:
            raise JWTError("token sub 格式无效")
        expires = payload["exp"]
        if type(expires) not in (int, float) or not math.isfinite(expires) or expires <= 0:
            raise JWTError("token exp 格式无效")
        return payload
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise JWTError("token 字段无效") from error


def create_mcp_access_token(
    user_id: int,
    username: str,
    scopes: list[str] | None = None,
) -> str:
    """签发只面向 JobPilot MCP Server 的短期 token。

    MCP token 与网页 API token 分离，并绑定 issuer、audience 和 scope，避免一个 token
    被拿到其它资源服务器复用。当前私有部署由已登录用户显式领取，不实现 OAuth 授权码流。
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.mcp_token_expire_minutes,
    )
    granted_scopes = scopes or ["jobpilot:read"]
    payload = {
        "sub": str(user_id),
        "username": username,
        "iss": settings.mcp_server_issuer_url,
        "aud": settings.mcp_server_public_url,
        "scope": " ".join(granted_scopes),
        "client_id": f"jobpilot-user-{user_id}",
        "exp": expire,
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def decode_mcp_access_token(token: str) -> dict:
    """验证 MCP token 的签名、发行者、受众和必需读权限。"""
    payload = jwt.decode(
        token,
        settings.auth_secret_key,
        algorithms=[settings.auth_algorithm],
        audience=settings.mcp_server_public_url,
        issuer=settings.mcp_server_issuer_url,
    )
    if payload.get("sub") is None:
        raise JWTError("MCP token 缺少 sub 字段")
    scopes = str(payload.get("scope") or "").split()
    if "jobpilot:read" not in scopes:
        raise JWTError("MCP token 缺少 jobpilot:read scope")
    return payload
