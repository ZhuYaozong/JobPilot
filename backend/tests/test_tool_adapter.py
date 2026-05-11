"""Unit tests for BaseTool's template-method invoke().

Uses a FakeTool with a mode arg so each test exercises exactly one branch of
the error contract: success, business-error return, system-error raise,
unexpected exception, and pydantic validation failure.
"""

import asyncio
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import (
    BaseTool,
    ToolContext,
    ToolSystemError,
    ToolValidationError,
)
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


class FakeArgs(BaseModel):
    mode: Literal["success", "business_error", "system_error", "raise_unexpected"]


class FakeTool(BaseTool):
    name = "fake_tool"
    description = "Test fixture for BaseTool's invoke template method."
    args_schema = FakeArgs

    async def _execute(
        self,
        args: FakeArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        if args.mode == "success":
            return {"ok": True, "data": {"echo": "success"}}
        if args.mode == "business_error":
            return {
                "ok": False,
                "error_class": "test_business",
                "message_for_llm": "fake biz error",
                "user_facing_detail": "fake biz user-facing",
            }
        if args.mode == "system_error":
            raise ToolSystemError(self.name, "test_system", "boom")
        # "raise_unexpected"
        raise RuntimeError("unexpected explosion")


async def _setup_agent_run(db: AsyncSession) -> tuple[User, int]:
    """Create the minimum DB state a tool call needs: user, conversation,
    agent_run."""
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    conversation = Conversation(user_id=user.id, title="tool adapter test")
    db.add(conversation)
    await db.flush()
    agent_run = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(agent_run)
    return user, agent_run.id


def _run_scenario(scenario) -> None:
    async def _do() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await scenario(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


async def _fetch_logs(db: AsyncSession, agent_run_id: int) -> list[ToolCallLog]:
    result = await db.execute(
        select(ToolCallLog)
        .where(ToolCallLog.agent_run_id == agent_run_id)
        .order_by(ToolCallLog.id),
    )
    return list(result.scalars().all())


def test_invoke_success_path_writes_success_log(client: TestClient) -> None:
    assert client.get("/health/db").status_code == 200  # ensures user fixtures

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        result = await FakeTool().invoke({"mode": "success"}, ctx)

        assert result == {"ok": True, "data": {"echo": "success"}}
        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        log = logs[0]
        assert log.tool_name == "fake_tool"
        assert log.status == "success"
        assert log.arguments_json == {"mode": "success"}
        assert log.result_json == {"echo": "success"}
        assert log.error_class is None
        assert log.error_detail is None
        assert log.finished_at is not None
        assert log.latency_ms is not None and log.latency_ms >= 0

    _run_scenario(_scenario)


def test_invoke_business_error_returns_ok_false_and_logs_failure(
    client: TestClient,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        result = await FakeTool().invoke({"mode": "business_error"}, ctx)

        assert result["ok"] is False
        assert result["error_class"] == "test_business"
        assert "fake biz" in result["message_for_llm"]
        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert logs[0].error_class == "test_business"
        assert logs[0].error_detail == "fake biz user-facing"

    _run_scenario(_scenario)


def test_invoke_tool_system_error_propagates_and_logs(client: TestClient) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        with pytest.raises(ToolSystemError) as exc_info:
            await FakeTool().invoke({"mode": "system_error"}, ctx)
        assert exc_info.value.error_class == "test_system"

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert logs[0].error_class == "test_system"
        assert logs[0].error_detail == "boom"

    _run_scenario(_scenario)


def test_invoke_unexpected_exception_wraps_to_tool_system_error(
    client: TestClient,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        with pytest.raises(ToolSystemError) as exc_info:
            await FakeTool().invoke({"mode": "raise_unexpected"}, ctx)
        assert exc_info.value.error_class == "unexpected_error"

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert logs[0].error_class == "unexpected_error"
        assert "RuntimeError" in (logs[0].error_detail or "")

    _run_scenario(_scenario)


def test_invoke_invalid_args_raises_validation_error_and_logs(
    client: TestClient,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        with pytest.raises(ToolValidationError):
            await FakeTool().invoke({"mode": "not_a_valid_choice"}, ctx)

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert logs[0].error_class == "validation_error"
        assert logs[0].arguments_json == {"mode": "not_a_valid_choice"}
        # Validation failures do not run _execute, so latency is zero.
        assert logs[0].latency_ms == 0

    _run_scenario(_scenario)
