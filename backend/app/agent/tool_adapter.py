"""Agent 工具适配层。

Agent 不直接调用业务 service，而是通过这个适配层统一完成参数校验、
ToolCallLog 追踪、错误分类和用户作用域上下文传递。这样 workflow 只关心
``ok`` / error_class / data 的稳定契约。

每个 ``BaseTool`` 子类只包装一个业务能力，例如匹配分析、求职信生成或知识库检索。
它把底层 service 的细节收敛成 Agent 统一接口，主要保证四件事：

- 先用 Pydantic 校验模型给出的工具参数。
- 工具执行前后都写入 ToolCallLog，记录状态、耗时、错误分类和结果。
- 业务错误不抛异常，而是返回 ``ok=false``，让模型把问题解释给用户或换参数重试。
- 参数校验错误抛 ``ToolValidationError``，交给 LangGraph 的 decide repair 机制。
- 系统错误抛 ``ToolSystemError``，例如数据库、LLM、网络或未知异常，调用方应把
  AgentRun 标记为 failed。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_call_log import ToolCallLog
from app.models.user import User


class ToolValidationError(Exception):
    """模型给出的工具参数未通过 Pydantic schema。

    这是模型可修复的错误：workflow 会把校验失败写入工具历史，让模型重新产出
    符合 schema 的工具参数。
    """

    def __init__(self, tool_name: str, validation_error: ValidationError) -> None:
        super().__init__(
            f"Tool '{tool_name}' arguments failed validation: {validation_error}",
        )
        self.tool_name = tool_name
        self.validation_error = validation_error


class ToolSystemError(Exception):
    """非业务失败，例如数据库、LLM 配置、网络或未知异常。

    这类错误通常不是模型换一组参数就能解决的，所以会中断本轮 workflow，
    由调用方把 AgentRun 标记为 failed。
    """

    def __init__(self, tool_name: str, error_class: str, detail: str) -> None:
        super().__init__(f"Tool '{tool_name}' system error ({error_class}): {detail}")
        self.tool_name = tool_name
        self.error_class = error_class
        self.detail = detail


@dataclass
class ToolContext:
    """每次工具调用共享的上下文。

    ``db`` 是底层业务 service 使用的同一个 AsyncSession。
    ``current_user`` 是已通过依赖解析的当前用户，所有工具必须以它作为权限边界。
    ``agent_run_id`` 会写入每条 ToolCallLog，后续才能复原完整工具链路。
    """

    db: AsyncSession
    current_user: User
    agent_run_id: int


class BaseTool(ABC):
    """所有具体工具的抽象基类。

    子类只需要声明 ``name``、``description``、``args_schema`` 并实现 ``_execute``。
    公共的 ``invoke`` 模板方法负责参数校验、日志、耗时统计和错误分类，避免每个工具
    重复实现同一套安全边界。
    """

    name: ClassVar[str]
    description: ClassVar[str]
    args_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    async def _execute(self, args: BaseModel, ctx: ToolContext) -> dict[str, Any]:
        """执行具体工具逻辑，并返回统一结果形状。

        - 成功：``{"ok": True, "data": {...}}``
        - 业务错误：``{"ok": False, "error_class": str,
          "message_for_llm": str, "user_facing_detail": str}``

        系统错误应主动抛 ``ToolSystemError``；未捕获异常会由 ``invoke`` 统一转换成
        ``ToolSystemError``，保证 workflow 不需要理解每个工具的内部异常类型。
        """

    async def invoke(
        self,
        raw_args: dict[str, Any],
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # Tool Adapter 是工具调用唯一入口，顺序固定为 refresh → 校验 → 记日志 → 执行 → 收尾。
        # ReAct 循环里，上一次工具调用可能在 _finalize_log 中 rollback 共享 session，
        # 这会让 current_user 等 ORM 实例过期。若后面同步访问 .id，SQLAlchemy 可能触发
        # lazy load 并在 async 上下文外抛 MissingGreenlet。这里先 refresh，确保后续同步
        # 属性读取都只读内存。
        await ctx.db.refresh(ctx.current_user)

        # 参数校验失败也要落 ToolCallLog，方便后续追踪模型给错了什么。
        # 这一步发生在真正执行业务前；失败时仍然写 failed 日志，给 repair 和排查留痕。
        try:
            args = self.args_schema.model_validate(raw_args)
        except ValidationError as exc:
            await self._persist_validation_failure(ctx, raw_args, exc)
            raise ToolValidationError(self.name, exc) from exc

        # 先写 running 日志再执行，保证工具中途崩溃也有可见运行痕迹。
        # running 日志先 commit，即使 _execute 中途崩溃，也能在数据库里看到这次尝试。
        log = ToolCallLog(
            user_id=ctx.current_user.id,
            agent_run_id=ctx.agent_run_id,
            tool_name=self.name,
            status="running",
            arguments_json=args.model_dump(mode="json"),
        )
        ctx.db.add(log)
        await ctx.db.commit()
        await ctx.db.refresh(log)
        log_id = log.id

        started = perf_counter()
        try:
            result = await self._execute(args, ctx)
        except ToolSystemError as exc:
            # 系统错会继续抛给 workflow，让 AgentRun 进入 failed。
            await self._finalize_log(
                ctx,
                log_id,
                status="failed",
                started=started,
                error_class=exc.error_class,
                error_detail=exc.detail,
            )
            raise
        except Exception as exc:  # noqa: BLE001 — 未知异常统一转换成系统错，避免泄漏实现细节。
            await self._finalize_log(
                ctx,
                log_id,
                status="failed",
                started=started,
                error_class="unexpected_error",
                error_detail=f"{type(exc).__name__}: {exc}",
            )
            raise ToolSystemError(self.name, "unexpected_error", str(exc)) from exc

        ok = bool(result.get("ok"))
        if ok:
            # 成功时只把 data 写入 result_json，避免重复记录 ok/message 包装字段。
            await self._finalize_log(
                ctx,
                log_id,
                status="success",
                started=started,
                result_json=result.get("data"),
            )
        else:
            # 业务错不抛异常，留给模型决定如何向用户解释或是否换参数重试。
            await self._finalize_log(
                ctx,
                log_id,
                status="failed",
                started=started,
                error_class=result.get("error_class") or "business_error",
                error_detail=result.get("user_facing_detail") or result.get("message_for_llm"),
            )
        return result

    async def _persist_validation_failure(
        self,
        ctx: ToolContext,
        raw_args: dict[str, Any],
        exc: ValidationError,
    ) -> None:
        # schema 阶段失败没有真实执行耗时，latency 固定为 0。
        # Pydantic 失败发生在业务执行前，日志直接进入 failed，不会出现 running 中间态。
        now = datetime.now(timezone.utc)
        log = ToolCallLog(
            user_id=ctx.current_user.id,
            agent_run_id=ctx.agent_run_id,
            tool_name=self.name,
            status="failed",
            arguments_json=raw_args,
            error_class="validation_error",
            error_detail=str(exc),
            finished_at=now,
            latency_ms=0,
        )
        ctx.db.add(log)
        await ctx.db.commit()

    async def _finalize_log(
        self,
        ctx: ToolContext,
        log_id: int,
        *,
        status: str,
        started: float,
        result_json: dict[str, Any] | None = None,
        error_class: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        # 无论工具执行成功还是失败，最终都在这里关闭 running 日志。
        # 如果 _execute 在 DML 中途抛错，session 可能处于不可提交状态；先 rollback，
        # 再用新的事务更新日志，能避免“业务失败连日志都写不进去”的二次故障。
        try:
            await ctx.db.rollback()
        except Exception:  # noqa: BLE001 — best effort
            pass

        # rollback 后旧 log 实例可能过期，重新读取一遍，避免 expired-instance 或 stale-state。
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
