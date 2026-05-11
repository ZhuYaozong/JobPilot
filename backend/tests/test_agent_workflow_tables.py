"""Smoke test for the agent-workflow data skeleton.

Slice 1 only ships tables, models, and schemas — no API, no service layer.
This test proves that a full conversation → message → agent_run → tool_call_log →
memory_summary chain can be inserted via the ORM, that FK constraints hold, and
that the UNIQUE constraints (messages.sequence_no per conversation,
memory_summaries.conversation_id) are enforced.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.memory_summary import MemorySummary
from app.models.message import Message
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


async def _get_test_user_id(db: AsyncSession) -> int:
    # The test user is created by the X-User-Name=test middleware on first
    # request; trigger that path through any cheap endpoint before this test
    # runs, or just create it directly here.
    result = await db.execute(select(User).where(User.username == "test"))
    user = result.scalar_one_or_none()
    if user is not None:
        return user.id
    user = User(username="test", display_name="Pytest User", is_test_user=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user.id


def _run_async(coro_factory) -> None:
    async def _do() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await coro_factory(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


def test_full_agent_workflow_chain_round_trip(client: TestClient) -> None:
    # Ensure the "test" user exists by going through the API once.
    health = client.get("/health/db")
    assert health.status_code == 200

    created_ids: dict[str, int] = {}

    async def _scenario(db: AsyncSession) -> None:
        user_id = await _get_test_user_id(db)

        conversation = Conversation(user_id=user_id, title="slice1 smoke")
        db.add(conversation)
        await db.flush()

        user_message = Message(
            user_id=user_id,
            conversation_id=conversation.id,
            role="user",
            content="hello",
            sequence_no=1,
        )
        db.add(user_message)
        await db.flush()

        agent_run = AgentRun(
            user_id=user_id,
            conversation_id=conversation.id,
            trigger_message_id=user_message.id,
            status="running",
            intent="match_analysis",
        )
        db.add(agent_run)
        await db.flush()

        tool_call = ToolCallLog(
            user_id=user_id,
            agent_run_id=agent_run.id,
            tool_name="analyze_match",
            status="success",
            arguments_json={"resume_id": 1, "job_posting_id": 2},
            result_json={"overall_score": 82},
            finished_at=datetime.now(timezone.utc),
            latency_ms=1234,
        )
        db.add(tool_call)

        assistant_message = Message(
            user_id=user_id,
            conversation_id=conversation.id,
            role="assistant",
            content="match score is 82",
            sequence_no=2,
            agent_run_id=agent_run.id,
        )
        db.add(assistant_message)
        await db.flush()

        memory_summary = MemorySummary(
            user_id=user_id,
            conversation_id=conversation.id,
            summary_text="user asked for match analysis; assistant returned 82.",
            based_on_until_message_id=assistant_message.id,
        )
        db.add(memory_summary)

        agent_run.status = "succeeded"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.token_usage = {"prompt_tokens": 100, "completion_tokens": 50, "total": 150}

        await db.commit()

        created_ids["conversation_id"] = conversation.id
        created_ids["user_message_id"] = user_message.id
        created_ids["agent_run_id"] = agent_run.id
        created_ids["tool_call_id"] = tool_call.id
        created_ids["assistant_message_id"] = assistant_message.id
        created_ids["memory_summary_id"] = memory_summary.id

    _run_async(_scenario)

    # Re-read everything in a fresh session and assert the chain holds.
    async def _verify(db: AsyncSession) -> None:
        conversation = await db.get(Conversation, created_ids["conversation_id"])
        assert conversation is not None
        assert conversation.title == "slice1 smoke"

        agent_run = await db.get(AgentRun, created_ids["agent_run_id"])
        assert agent_run is not None
        assert agent_run.status == "succeeded"
        assert agent_run.trigger_message_id == created_ids["user_message_id"]
        assert agent_run.token_usage == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total": 150,
        }

        assistant_message = await db.get(Message, created_ids["assistant_message_id"])
        assert assistant_message is not None
        assert assistant_message.agent_run_id == created_ids["agent_run_id"]
        assert assistant_message.sequence_no == 2

        tool_call = await db.get(ToolCallLog, created_ids["tool_call_id"])
        assert tool_call is not None
        assert tool_call.arguments_json == {"resume_id": 1, "job_posting_id": 2}
        assert tool_call.result_json == {"overall_score": 82}

        memory_summary = await db.get(MemorySummary, created_ids["memory_summary_id"])
        assert memory_summary is not None
        assert memory_summary.based_on_until_message_id == created_ids["assistant_message_id"]

    _run_async(_verify)

    # UNIQUE(conversation_id, sequence_no) on messages should reject duplicates.
    async def _expect_message_unique_violation(db: AsyncSession) -> None:
        user_id = await _get_test_user_id(db)
        duplicate = Message(
            user_id=user_id,
            conversation_id=created_ids["conversation_id"],
            role="user",
            content="duplicate seq_no",
            sequence_no=1,
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            await db.commit()

    _run_async(_expect_message_unique_violation)

    # UNIQUE(conversation_id) on memory_summaries should reject duplicates.
    async def _expect_summary_unique_violation(db: AsyncSession) -> None:
        user_id = await _get_test_user_id(db)
        duplicate = MemorySummary(
            user_id=user_id,
            conversation_id=created_ids["conversation_id"],
            summary_text="second summary attempt",
            based_on_until_message_id=created_ids["assistant_message_id"],
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            await db.commit()

    _run_async(_expect_summary_unique_violation)
