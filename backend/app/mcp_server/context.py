"""MCP 请求身份解析和数据库上下文创建。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.auth.middleware.auth_context import get_access_token
from sqlalchemy import select

from app.agent.tool_adapter import ToolContext
from app.mcp_server.db import MCPAsyncSessionLocal
from app.models.user import User


class MCPAuthenticationError(PermissionError):
    """MCP 请求未认证或用户已失效。"""


@asynccontextmanager
async def authenticated_tool_context():
    """为一次入站 MCP 调用创建独立数据库会话和只读身份上下文。"""
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        raise MCPAuthenticationError("缺少有效的 MCP access token")
    try:
        user_id = int(access_token.subject)
    except ValueError as exc:
        raise MCPAuthenticationError("MCP token subject 无效") from exc

    async with MCPAsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if user is None or not user.is_active:
            raise MCPAuthenticationError("用户不存在或已停用")
        yield ToolContext(
            db=db,
            current_user=user,
            agent_run_id=None,
            source="mcp",
            client_id=access_token.client_id,
        )
