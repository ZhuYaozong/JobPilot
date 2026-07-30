"""JobPilot 的 MCP 客户端基础设施。"""

from app.mcp.config import MCPRemoteServerConfig, load_mcp_server_configs

__all__ = ["MCPRemoteServerConfig", "load_mcp_server_configs"]
