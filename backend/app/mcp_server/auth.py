"""JobPilot MCP Resource Server 的 bearer token 验证。"""

from __future__ import annotations

from jose import JWTError
from sqlalchemy import select

from mcp.server.auth.provider import AccessToken, TokenVerifier

from app.core.security import decode_mcp_access_token
from app.mcp_server.db import MCPAsyncSessionLocal
from app.models.user import User


class JobPilotTokenVerifier(TokenVerifier):
    """验证 JobPilot 签发的 MCP 专用 JWT，并确认用户仍然有效。"""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_mcp_access_token(token)
            user_id = int(payload["sub"])
        except (JWTError, KeyError, TypeError, ValueError):
            return None

        async with MCPAsyncSessionLocal() as db:
            user = (
                await db.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
            if user is None or not user.is_active:
                return None

        scopes = str(payload.get("scope") or "").split()
        expires_at = payload.get("exp")
        return AccessToken(
            token=token,
            client_id=str(payload.get("client_id") or f"jobpilot-user-{user_id}"),
            subject=str(user_id),
            scopes=scopes,
            expires_at=int(expires_at) if expires_at is not None else None,
            resource=str(payload.get("aud") or ""),
            claims={
                "username": payload.get("username"),
                "user_id": user_id,
            },
        )
