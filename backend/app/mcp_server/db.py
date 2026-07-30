"""MCP Server 专用数据库会话。

独立 MCP 进程通常只有一个事件循环，但测试客户端和嵌入式部署可能跨事件循环驱动
ASGI。NullPool 保证认证与工具请求不复用绑定到旧事件循环的 asyncpg 连接。
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


mcp_engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    poolclass=NullPool,
)

MCPAsyncSessionLocal = async_sessionmaker[
    AsyncSession
](
    bind=mcp_engine,
    expire_on_commit=False,
)
