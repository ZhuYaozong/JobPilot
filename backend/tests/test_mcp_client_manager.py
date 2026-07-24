"""MCP Client Manager 的发现缓存、调用和白名单测试。"""

import asyncio

import pytest
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from app.mcp.client_manager import (
    MCPCallTimeoutError,
    MCPClientManager,
    MCPToolNotAllowedError,
)
from app.mcp.config import MCPRemoteServerConfig


class _FakeSession:
    def __init__(self) -> None:
        self.list_count = 0
        self.call_count = 0

    async def list_tools(self, cursor=None):
        self.list_count += 1
        return ListToolsResult(
            tools=[
                Tool(
                    name="search_jobs",
                    description="搜索岗位",
                    inputSchema={"type": "object"},
                ),
            ],
        )

    async def call_tool(self, name, arguments, read_timeout_seconds=None):
        self.call_count += 1
        return CallToolResult(
            content=[TextContent(type="text", text=f"{name}:{arguments['query']}")],
        )


class _FakeContext:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return None


def _config(**overrides) -> MCPRemoteServerConfig:
    values = {
        "id": "jobs",
        "url": "http://127.0.0.1:9100/mcp",
        "allowed_tools": ["search_jobs"],
    }
    values.update(overrides)
    return MCPRemoteServerConfig(**values)


def test_discovery_uses_ttl_cache(monkeypatch) -> None:
    manager = MCPClientManager()
    session = _FakeSession()
    monkeypatch.setattr(manager, "_open_session", lambda config: _FakeContext(session))

    async def scenario():
        first = await manager.list_tools(_config())
        second = await manager.list_tools(_config())
        assert first[0].name == "search_jobs"
        assert second[0].name == "search_jobs"

    asyncio.run(scenario())
    assert session.list_count == 1


def test_call_enforces_allowlist(monkeypatch) -> None:
    manager = MCPClientManager()
    session = _FakeSession()
    monkeypatch.setattr(manager, "_open_session", lambda config: _FakeContext(session))

    async def scenario():
        result = await manager.call_tool(
            _config(),
            "search_jobs",
            {"query": "Python"},
        )
        assert result.content[0].text == "search_jobs:Python"
        with pytest.raises(MCPToolNotAllowedError):
            await manager.call_tool(_config(), "delete_everything", {})

    asyncio.run(scenario())
    assert session.call_count == 1


def test_discovery_timeout_is_classified(monkeypatch) -> None:
    class SlowSession(_FakeSession):
        async def list_tools(self, cursor=None):
            await asyncio.sleep(0.05)
            return await super().list_tools(cursor)

    manager = MCPClientManager()
    monkeypatch.setattr(
        manager,
        "_open_session",
        lambda config: _FakeContext(SlowSession()),
    )

    async def scenario():
        with pytest.raises(MCPCallTimeoutError):
            await manager.list_tools(
                _config(discovery_timeout_seconds=0.01),
                force_refresh=True,
            )

    asyncio.run(scenario())
