"""请求级统一工具目录：同时承载本地工具和远程 MCP 工具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.agent.tool_adapter import ToolContext
from app.agent.tools import TOOL_REGISTRY
from app.mcp.client_manager import MCPClientError, get_mcp_client_manager
from app.mcp.config import MCPConfigError, load_mcp_server_configs
from app.mcp.tool_provider import MCPToolProvider


ToolSource = Literal["local", "mcp"]


@dataclass(frozen=True)
class ToolDescriptor:
    """供 Prompt 和执行器共同使用的稳定工具元数据。"""

    name: str
    description: str
    input_schema: dict[str, Any]
    source: ToolSource
    title: str | None = None
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] = field(default_factory=dict)
    server_id: str | None = None
    original_name: str | None = None


class ToolCatalog:
    def __init__(self) -> None:
        self._descriptors: dict[str, ToolDescriptor] = {}
        self._mcp_bindings: dict[str, tuple[MCPToolProvider, str]] = {}
        self.notices: list[str] = []

    @classmethod
    def local_only(cls) -> "ToolCatalog":
        catalog = cls()
        for name, tool_cls in TOOL_REGISTRY.items():
            catalog._descriptors[name] = ToolDescriptor(
                name=name,
                description=tool_cls.description,
                input_schema=tool_cls.args_schema.model_json_schema(),
                source="local",
                annotations=_local_tool_annotations(name),
            )
        return catalog

    @property
    def descriptors(self) -> list[ToolDescriptor]:
        return list(self._descriptors.values())

    def has(self, name: str) -> bool:
        return name in self._descriptors

    async def invoke(
        self,
        name: str,
        raw_args: dict[str, Any],
        ctx: ToolContext,
    ) -> dict[str, Any]:
        local_cls = TOOL_REGISTRY.get(name)
        if local_cls is not None:
            return await local_cls().invoke(raw_args, ctx)

        binding = self._mcp_bindings.get(name)
        if binding is None:
            return {
                "ok": False,
                "error_class": "tool_not_found",
                "message_for_llm": "请求的工具不存在或当前不可用。",
                "user_facing_detail": "请求的工具当前不可用。",
            }
        provider, original_name = binding
        return await provider.invoke(original_name, raw_args, ctx)

    def add_mcp_provider(self, provider: MCPToolProvider) -> None:
        for original_name, tool in provider.tools.items():
            technical_name = f"mcp__{provider.config.id}__{original_name}"
            if technical_name in self._descriptors:
                self.notices.append(f"忽略重复工具名 {technical_name}")
                continue
            annotations = (
                tool.annotations.model_dump(by_alias=True, exclude_none=True)
                if tool.annotations is not None
                else {}
            )
            self._descriptors[technical_name] = ToolDescriptor(
                name=technical_name,
                title=tool.title,
                description=(
                    f"[外部 MCP/{provider.config.category}] "
                    f"{tool.description or original_name}"
                ),
                input_schema=tool.inputSchema,
                output_schema=tool.outputSchema,
                annotations=annotations,
                source="mcp",
                server_id=provider.config.id,
                original_name=original_name,
            )
            self._mcp_bindings[technical_name] = (provider, original_name)


async def build_request_tool_catalog() -> ToolCatalog:
    """构建当前 Assistant 请求可见的工具集合；单个外部服务失败时安全降级。"""
    catalog = ToolCatalog.local_only()
    try:
        configs = load_mcp_server_configs()
    except MCPConfigError as exc:
        catalog.notices.append(f"MCP 配置不可用: {exc}")
        return catalog

    manager = get_mcp_client_manager()
    for config in configs:
        try:
            tools = await manager.list_tools(config)
        except MCPClientError as exc:
            catalog.notices.append(
                f"外部 MCP Server {config.id} 当前不可用({exc.error_class})",
            )
            continue
        provider = MCPToolProvider(config, manager, tools)
        catalog.add_mcp_provider(provider)
    return catalog


def _local_tool_annotations(name: str) -> dict[str, Any]:
    """给现有工具补基础风险元数据；它是 UI 提示，不代替权限检查。"""
    read_only = name.startswith(("list_", "read_", "search_"))
    destructive = name == "update_application_stage"
    return {
        "readOnlyHint": read_only,
        "destructiveHint": destructive,
        "idempotentHint": read_only,
        "openWorldHint": name in {"draft_job"},
    }
