"""把动态 MCP Tool 适配到 JobPilot 的工具结果和审计契约。"""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from mcp.types import Tool

from app.agent.tool_adapter import ToolContext
from app.mcp.client_manager import MCPClientError, MCPClientManager
from app.mcp.config import MCPRemoteServerConfig
from app.mcp.result_mapper import map_mcp_tool_result
from app.models.tool_call_log import ToolCallLog


class MCPToolProvider:
    """一个远程 MCP Server 的白名单工具适配器。"""

    def __init__(
        self,
        config: MCPRemoteServerConfig,
        manager: MCPClientManager,
        tools: list[Tool],
    ) -> None:
        self.config = config
        self.manager = manager
        self.tools = {
            tool.name: tool
            for tool in tools
            if tool.name in config.allowed_tools
        }

    async def invoke(
        self,
        original_tool_name: str,
        raw_args: dict[str, Any],
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 前一个工具的日志收尾可能 rollback 共享 session，先刷新用户对象，避免同步读取
        # 已过期的 .id 时触发 MissingGreenlet。
        await ctx.db.refresh(ctx.current_user)
        tool = self.tools.get(original_tool_name)
        if tool is None:
            return {
                "ok": False,
                "error_class": "mcp_tool_not_found",
                "message_for_llm": "配置的外部工具当前不存在，请向用户说明该能力暂不可用。",
                "user_facing_detail": "外部工具当前不存在。",
            }

        validation_error = _validate_arguments(tool, raw_args)
        if validation_error:
            await self._persist_finished_log(
                ctx,
                original_tool_name,
                raw_args,
                started=perf_counter(),
                status="failed",
                error_class="validation_error",
                error_detail=validation_error,
            )
            return {
                "ok": False,
                "error_class": "tool_args_invalid",
                "message_for_llm": (
                    f"外部工具参数不符合 JSON Schema: {validation_error}。"
                    "请使用真实字段重新组织参数，缺少用户信息时直接追问。"
                ),
                "user_facing_detail": "外部工具参数未通过校验。",
            }

        technical_name = f"mcp__{self.config.id}__{original_tool_name}"
        log = ToolCallLog(
            user_id=ctx.current_user.id,
            agent_run_id=ctx.agent_run_id,
            source=ctx.source,
            client_id=ctx.client_id,
            tool_name=technical_name,
            status="running",
            arguments_json=raw_args,
        )
        ctx.db.add(log)
        await ctx.db.commit()
        await ctx.db.refresh(log)
        started = perf_counter()
        try:
            sdk_result = await self.manager.call_tool(
                self.config,
                original_tool_name,
                raw_args,
            )
            result = map_mcp_tool_result(
                sdk_result,
                server_id=self.config.id,
                tool_name=original_tool_name,
                max_chars=self.config.result_limit,
            )
        except MCPClientError as exc:
            await self._finalize_existing_log(
                ctx,
                log.id,
                started=started,
                status="failed",
                error_class=exc.error_class,
                error_detail=str(exc),
            )
            return {
                "ok": False,
                "error_class": exc.error_class,
                "message_for_llm": (
                    "外部 MCP 服务当前不可用。请向用户简洁说明可以稍后重试，"
                    "不要猜测或伪造搜索结果。"
                ),
                "user_facing_detail": "外部 MCP 服务当前不可用。",
            }

        if result["ok"]:
            await self._finalize_existing_log(
                ctx,
                log.id,
                started=started,
                status="success",
                result_json=result["data"],
            )
        else:
            await self._finalize_existing_log(
                ctx,
                log.id,
                started=started,
                status="failed",
                result_json=result.get("data"),
                error_class=result.get("error_class"),
                error_detail=result.get("user_facing_detail"),
            )
        return result

    async def _persist_finished_log(
        self,
        ctx: ToolContext,
        tool_name: str,
        raw_args: dict[str, Any],
        *,
        started: float,
        status: str,
        error_class: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        ctx.db.add(
            ToolCallLog(
                user_id=ctx.current_user.id,
                agent_run_id=ctx.agent_run_id,
                source=ctx.source,
                client_id=ctx.client_id,
                tool_name=f"mcp__{self.config.id}__{tool_name}",
                status=status,
                arguments_json=raw_args,
                error_class=error_class,
                error_detail=error_detail,
                finished_at=now,
                latency_ms=int((perf_counter() - started) * 1000),
            ),
        )
        await ctx.db.commit()

    async def _finalize_existing_log(
        self,
        ctx: ToolContext,
        log_id: int,
        *,
        started: float,
        status: str,
        result_json: dict[str, Any] | None = None,
        error_class: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        try:
            await ctx.db.rollback()
        except Exception:  # noqa: BLE001
            pass
        log = await ctx.db.get(ToolCallLog, log_id)
        if log is None:
            return
        log.status = status
        log.result_json = result_json
        log.error_class = error_class
        log.error_detail = error_detail
        log.finished_at = datetime.now(timezone.utc)
        log.latency_ms = int((perf_counter() - started) * 1000)
        await ctx.db.commit()


def _validate_arguments(tool: Tool, raw_args: dict[str, Any]) -> str | None:
    try:
        Draft202012Validator.check_schema(tool.inputSchema)
        Draft202012Validator(tool.inputSchema).validate(raw_args)
    except SchemaError:
        return "远程服务器提供了无效的 inputSchema"
    except ValidationError as exc:
        return exc.message
    return None
