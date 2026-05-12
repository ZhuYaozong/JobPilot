"""Tool adapter layer.

Each `BaseTool` subclass wraps one piece of business capability (a service
function) so the LangGraph agent layer can call it with a uniform interface:

- Pydantic validation on the LLM-supplied arguments
- ToolCallLog persisted before and after the call (status, latency, error class)
- Three-way error contract:
    * Business error (invalid resource, precondition not met): returned as
      ``{"ok": False, "error_class": ..., "message_for_llm": ...}``. The LLM
      can react and try again or surface the issue to the user.
    * Validation error (LLM-supplied args fail Pydantic): raised as
      ``ToolValidationError``. LangGraph triggers a single repair attempt.
    * System error (DB/LLM/network/unexpected): raised as ``ToolSystemError``.
      LangGraph marks the AgentRun as failed.
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
    """LLM-supplied arguments did not pass the tool's Pydantic schema.

    LangGraph should re-prompt the LLM with the validation error attached.
    """

    def __init__(self, tool_name: str, validation_error: ValidationError) -> None:
        super().__init__(
            f"Tool '{tool_name}' arguments failed validation: {validation_error}",
        )
        self.tool_name = tool_name
        self.validation_error = validation_error


class ToolSystemError(Exception):
    """Non-business failure (DB unavailable, LLM config missing, unexpected exc).

    LangGraph should mark the AgentRun as failed; retrying with the same args
    will not help.
    """

    def __init__(self, tool_name: str, error_class: str, detail: str) -> None:
        super().__init__(f"Tool '{tool_name}' system error ({error_class}): {detail}")
        self.tool_name = tool_name
        self.error_class = error_class
        self.detail = detail


@dataclass
class ToolContext:
    """Per-call context that the agent layer threads into every tool.

    `db` is the same AsyncSession the tool's underlying service will use.
    `agent_run_id` links every ToolCallLog row back to its AgentRun so we can
    reconstruct full traces later.
    """

    db: AsyncSession
    current_user: User
    agent_run_id: int


class BaseTool(ABC):
    """Abstract base for every concrete tool.

    Subclasses set the three class vars and implement ``_execute``; the
    template ``invoke`` method handles validation, logging, timing, and error
    classification.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    args_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    async def _execute(self, args: BaseModel, ctx: ToolContext) -> dict[str, Any]:
        """Run the tool's real work. Return shape:

        - Success: ``{"ok": True, "data": {...}}``
        - Business error: ``{"ok": False, "error_class": str,
          "message_for_llm": str, "user_facing_detail": str}``

        System errors should raise ``ToolSystemError``; uncaught exceptions
        are converted to ``ToolSystemError`` automatically by ``invoke``.
        """

    async def invoke(
        self,
        raw_args: dict[str, Any],
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # In the ReAct loop a previous tool call's ``_finalize_log`` rolled
        # the shared session back, which expires every attached ORM instance
        # including ``ctx.current_user``. A subsequent sync ``.id`` access
        # would then trigger a lazy load and raise MissingGreenlet. Refresh
        # eagerly so all attributes are loaded before any sync access below.
        await ctx.db.refresh(ctx.current_user)

        # 1. Pydantic validation. We persist a failed ToolCallLog before
        #    raising so LangGraph's repair attempt has an audit trail.
        try:
            args = self.args_schema.model_validate(raw_args)
        except ValidationError as exc:
            await self._persist_validation_failure(ctx, raw_args, exc)
            raise ToolValidationError(self.name, exc) from exc

        # 2. Create the "running" log row up-front and commit so it survives
        #    even if _execute crashes mid-way.
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
            await self._finalize_log(
                ctx,
                log_id,
                status="failed",
                started=started,
                error_class=exc.error_class,
                error_detail=exc.detail,
            )
            raise
        except Exception as exc:  # noqa: BLE001 — convert unknown errors uniformly
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
            await self._finalize_log(
                ctx,
                log_id,
                status="success",
                started=started,
                result_json=result.get("data"),
            )
        else:
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
        # Pydantic failure happens before we even attempt execution, so the
        # log row goes straight to status='failed'.
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
        # If _execute left the session in a bad state (e.g. raised mid-DML),
        # roll it back so the log update can commit on a fresh transaction.
        try:
            await ctx.db.rollback()
        except Exception:  # noqa: BLE001 — best effort
            pass

        # Re-fetch the log row to avoid expired-instance / stale-state issues
        # that can arise after rollback.
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
