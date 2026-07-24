"""MCP 服务器配置和 SSRF 基础策略测试。"""

import asyncio

import pytest

from app.agent.tool_catalog import build_request_tool_catalog
from app.core.config import settings
from app.mcp.client_manager import MCPServerUnavailableError
from app.mcp.config import MCPConfigError, MCPRemoteServerConfig, load_mcp_server_configs


def test_mcp_config_loads_enabled_allowlisted_servers(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mcp_enabled", True)
    monkeypatch.setattr(
        settings,
        "mcp_servers_json",
        (
            '[{"id":"jobs","url":"http://127.0.0.1:9100/mcp",'
            '"allowed_tools":["search_jobs","search_jobs","get_job_detail"]}]'
        ),
    )
    configs = load_mcp_server_configs()
    assert len(configs) == 1
    assert configs[0].allowed_tools == ["search_jobs", "get_job_detail"]
    assert configs[0].technical_prefix == "mcp__jobs__"


def test_mcp_config_rejects_non_local_plain_http() -> None:
    with pytest.raises(ValueError, match="只允许 localhost"):
        MCPRemoteServerConfig(
            id="jobs",
            url="http://example.com/mcp",
            allowed_tools=["search_jobs"],
        )


def test_mcp_config_rejects_duplicate_ids(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mcp_enabled", True)
    monkeypatch.setattr(
        settings,
        "mcp_servers_json",
        (
            '[{"id":"jobs","url":"http://127.0.0.1:9100/mcp",'
            '"allowed_tools":["a"]},{"id":"jobs","url":"http://localhost:9200/mcp",'
            '"allowed_tools":["b"]}]'
        ),
    )
    with pytest.raises(MCPConfigError, match="不能重复"):
        load_mcp_server_configs()


def test_unavailable_remote_server_degrades_to_local_catalog(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mcp_enabled", True)
    monkeypatch.setattr(
        settings,
        "mcp_servers_json",
        (
            '[{"id":"jobs","url":"http://127.0.0.1:9100/mcp",'
            '"allowed_tools":["search_jobs"]}]'
        ),
    )

    class UnavailableManager:
        async def list_tools(self, config):
            raise MCPServerUnavailableError("offline")

    monkeypatch.setattr(
        "app.agent.tool_catalog.get_mcp_client_manager",
        lambda: UnavailableManager(),
    )
    catalog = asyncio.run(build_request_tool_catalog())
    assert catalog.has("list_user_jobs")
    assert not catalog.has("mcp__jobs__search_jobs")
    assert any("mcp_server_unavailable" in notice for notice in catalog.notices)
