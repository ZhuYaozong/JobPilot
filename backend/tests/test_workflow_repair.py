"""Decide-node repair-loop tests.

We exercise the LangGraph workflow directly (bypassing the HTTP layer) and
control the LLM via a stateful fake that returns different responses on
consecutive calls. Three scenarios:

1. First decide returns unparseable text; the repair attempt returns a valid
   ``respond_directly`` envelope; workflow finishes with that text.
2. Both decide attempts return unparseable text; workflow sets
   ``decide_error_class=decide_repair_failed`` and exits without final_text.
3. Decide returns valid JSON immediately; the repair branch never fires.
"""

import asyncio
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.workflow import build_workflow
from app.core.config import settings
from app.llm.client import LLMClient
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.user import User


async def _setup_run(db: AsyncSession, marker: str) -> tuple[User, int]:
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} repair conv")
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


def _run(coro_factory: Callable[[AsyncSession], Any]) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


def _build_initial_state(user_id: int, agent_run_id: int, conversation_id: int, user_text: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "user_message_id": 0,
        "user_text": user_text,
        "agent_run_id": agent_run_id,
        "conversation_history": [],
        "existing_summary": None,
        "message_count_before_user": 0,
        "decide_repair_attempts": 0,
    }


def test_repair_succeeds_after_one_bad_decide_output(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    call_count = {"n": 0}

    async def fake_llm(self, prompt: str) -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First decide: invalid JSON
            assert "请严格按以下两种 JSON" in prompt
            return "this is not JSON at all"
        if call_count["n"] == 2:
            # Repair: valid respond_directly
            assert "修正之前的错误回复" in prompt
            return '{"action": "respond_directly", "text": "你好,我可以帮你做什么?"}'
        # No more LLM calls expected — direct_text bypasses format_response LLM.
        raise AssertionError(f"unexpected extra LLM call #{call_count['n']}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_run(db, test_marker)
        conversation_id = (
            await db.execute(
                select(AgentRun.conversation_id).where(AgentRun.id == agent_run_id),
            )
        ).scalar_one()
        graph = build_workflow(
            db=db,
            current_user=user,
            agent_run_id=agent_run_id,
        )
        final_state = await graph.ainvoke(
            _build_initial_state(user.id, agent_run_id, conversation_id, f"{test_marker} hi"),
        )
        assert final_state.get("decide_error_class") is None
        assert final_state.get("final_text") == "你好,我可以帮你做什么?"
        assert call_count["n"] == 2

    _run(_scenario)


def test_repair_fails_when_both_decide_outputs_are_bad(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def always_garbage(self, prompt: str) -> str:
        return "definitely not json"

    monkeypatch.setattr(LLMClient, "generate_text", always_garbage)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_run(db, test_marker)
        conversation_id = (
            await db.execute(
                select(AgentRun.conversation_id).where(AgentRun.id == agent_run_id),
            )
        ).scalar_one()
        graph = build_workflow(
            db=db,
            current_user=user,
            agent_run_id=agent_run_id,
        )
        final_state = await graph.ainvoke(
            _build_initial_state(user.id, agent_run_id, conversation_id, f"{test_marker} probe"),
        )
        assert final_state.get("decide_error_class") == "decide_repair_failed"
        assert "decide_output_not_json" in (final_state.get("decide_error_detail") or "") or \
               "both decide attempts" in (final_state.get("decide_error_detail") or "")
        assert final_state.get("final_text") is None or final_state.get("final_text") == ""

    _run(_scenario)


def test_repair_branch_skipped_when_first_decide_is_valid(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    call_count = {"n": 0}

    async def fake_llm(self, prompt: str) -> str:
        call_count["n"] += 1
        if "修正之前的错误回复" in prompt:
            raise AssertionError("repair prompt should not have fired")
        if call_count["n"] == 1:
            return '{"action": "respond_directly", "text": "你好"}'
        # direct_text → no format_response LLM call expected.
        raise AssertionError(f"unexpected extra LLM call #{call_count['n']}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_run(db, test_marker)
        conversation_id = (
            await db.execute(
                select(AgentRun.conversation_id).where(AgentRun.id == agent_run_id),
            )
        ).scalar_one()
        graph = build_workflow(
            db=db,
            current_user=user,
            agent_run_id=agent_run_id,
        )
        final_state = await graph.ainvoke(
            _build_initial_state(user.id, agent_run_id, conversation_id, f"{test_marker} hello"),
        )
        assert final_state.get("decide_error_class") is None
        assert final_state.get("final_text") == "你好"
        assert call_count["n"] == 1

    _run(_scenario)
