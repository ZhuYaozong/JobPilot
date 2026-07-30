"""Streamable HTTP MCP 客户端、发现缓存与错误边界。"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, Tool

from app.core.config import settings
from app.mcp.config import MCPRemoteServerConfig


class MCPClientError(RuntimeError):
    """远程 MCP 调用的稳定错误基类。"""

    error_class = "mcp_client_error"


class MCPServerUnavailableError(MCPClientError):
    error_class = "mcp_server_unavailable"


class MCPCallTimeoutError(MCPClientError):
    error_class = "mcp_timeout"


class MCPToolNotAllowedError(MCPClientError):
    error_class = "mcp_tool_not_allowed"


@dataclass
class _DiscoveryEntry:
    tools: list[Tool]
    expires_at: float


class MCPClientManager:
    """按调用创建协议会话，并对 tools/list 做短期缓存。

    MCP Server 数量和调用频率在当前产品阶段都很小；按操作建立会话能避免跨请求共享
    有状态 session 的并发问题。工具发现使用 TTL 缓存，减少每轮 Assistant 的握手开销。
    """

    def __init__(self) -> None:
        self._discovery_cache: dict[str, _DiscoveryEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def list_tools(
        self,
        config: MCPRemoteServerConfig,
        *,
        force_refresh: bool = False,
    ) -> list[Tool]:
        now = monotonic()
        cached = self._discovery_cache.get(config.id)
        if cached and cached.expires_at > now and not force_refresh:
            return list(cached.tools)

        lock = self._locks.setdefault(config.id, asyncio.Lock())
        async with lock:
            now = monotonic()
            cached = self._discovery_cache.get(config.id)
            if cached and cached.expires_at > now and not force_refresh:
                return list(cached.tools)
            tools = await self._fetch_all_tools(config)
            self._discovery_cache[config.id] = _DiscoveryEntry(
                tools=tools,
                expires_at=now + settings.mcp_discovery_cache_seconds,
            )
            return list(tools)

    async def call_tool(
        self,
        config: MCPRemoteServerConfig,
        tool_name: str,
        arguments: dict,
    ) -> CallToolResult:
        if tool_name not in config.allowed_tools:
            raise MCPToolNotAllowedError(
                f"工具 {tool_name!r} 不在服务器 {config.id!r} 的白名单中",
            )
        try:
            async with asyncio.timeout(config.call_timeout):
                async with self._open_session(config) as session:
                    return await session.call_tool(
                        tool_name,
                        arguments,
                        read_timeout_seconds=timedelta(seconds=config.call_timeout),
                    )
        except TimeoutError as exc:
            raise MCPCallTimeoutError(
                f"MCP 工具 {config.id}/{tool_name} 调用超时",
            ) from exc
        except MCPClientError:
            raise
        except Exception as exc:  # noqa: BLE001 — SDK/网络异常统一收敛，禁止泄漏 token。
            raise MCPServerUnavailableError(
                f"MCP 工具 {config.id}/{tool_name} 当前不可用: {type(exc).__name__}",
            ) from exc

    async def _fetch_all_tools(self, config: MCPRemoteServerConfig) -> list[Tool]:
        try:
            async with asyncio.timeout(config.discovery_timeout):
                async with self._open_session(config) as session:
                    tools: list[Tool] = []
                    cursor: str | None = None
                    while True:
                        page = await session.list_tools(cursor=cursor)
                        tools.extend(page.tools)
                        cursor = page.nextCursor
                        if not cursor:
                            break
                    return tools
        except TimeoutError as exc:
            raise MCPCallTimeoutError(
                f"MCP Server {config.id} 工具发现超时",
            ) from exc
        except MCPClientError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MCPServerUnavailableError(
                f"MCP Server {config.id} 无法完成工具发现: {type(exc).__name__}",
            ) from exc

    def _open_session(self, config: MCPRemoteServerConfig):
        """构造同时管理 HTTP transport 和 ClientSession 的异步上下文。"""
        return _MCPSessionContext(config)


class _MCPSessionContext:
    """把 SDK 的两个嵌套上下文封装成一个，确保异常时完整关闭。"""

    def __init__(self, config: MCPRemoteServerConfig) -> None:
        self._config = config
        self._transport_context = None
        self._session_context = None

    async def __aenter__(self) -> ClientSession:
        headers: dict[str, str] = {}
        if self._config.auth_token_env:
            token = os.getenv(self._config.auth_token_env)
            if not token:
                raise MCPServerUnavailableError(
                    f"MCP Server {self._config.id} 缺少认证环境变量",
                )
            headers["Authorization"] = f"Bearer {token}"

        try:
            self._transport_context = streamablehttp_client(
                self._config.url,
                headers=headers or None,
                timeout=self._config.call_timeout,
                sse_read_timeout=self._config.call_timeout,
            )
            read_stream, write_stream, _ = await self._transport_context.__aenter__()
            self._session_context = ClientSession(read_stream, write_stream)
            session = await self._session_context.__aenter__()
            await session.initialize()
            return session
        except Exception:
            # __aenter__ 失败时 Python 不会自动调用 __aexit__，这里必须主动关闭已经
            # 打开的 transport/session，避免失败重连逐渐泄漏连接。
            await self._close(*sys.exc_info())
            raise

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._close(exc_type, exc, tb)

    async def _close(self, exc_type, exc, tb) -> None:
        if self._session_context is not None:
            with suppress(Exception):
                await self._session_context.__aexit__(exc_type, exc, tb)
            self._session_context = None
        if self._transport_context is not None:
            with suppress(Exception):
                await self._transport_context.__aexit__(exc_type, exc, tb)
            self._transport_context = None


_manager = MCPClientManager()


def get_mcp_client_manager() -> MCPClientManager:
    return _manager
