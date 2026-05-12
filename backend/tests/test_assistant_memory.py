"""Multi-turn history & memory_summary tests for the assistant pipeline.

These tests go through the HTTP layer and assert two slice-4 behaviours:

1. The decide / format_response prompts on turn N+1 include the content of
   turn N's user message — proving conversation history is wired through.
2. When the conversation crosses ``SUMMARIZE_MESSAGE_THRESHOLD``,
   ``maybe_summarize`` fires and a row appears in ``memory_summaries``.
"""

import asyncio
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.workflow import SUMMARIZE_MESSAGE_THRESHOLD
from app.core.config import settings
from app.llm.client import LLMClient
from app.models.conversation import Conversation
from app.models.memory_summary import MemorySummary
from app.models.message import Message
from app.models.user import User


def _run(coro_factory: Callable[[AsyncSession], Any]) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


def test_second_turn_decide_prompt_contains_first_turn_user_text(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """First turn writes content; second turn's decide prompt must include
    the first turn's user text under the 对话历史 section."""
    assert client.get("/health/db").status_code == 200

    seen_prompts: list[str] = []

    async def fake_llm(self, prompt: str) -> str:
        seen_prompts.append(prompt)
        if "请严格按以下两种 JSON" in prompt:
            return '{"action": "respond_directly", "text": "好的,继续聊。"}'
        if "本轮你为了回答用户的问题" in prompt:
            return "(format_response not expected here)"
        if "对话摘要生成器" in prompt:
            return "summary text"
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    first_marker_payload = f"{test_marker} 第一轮特殊关键词 alpha"
    second_marker_payload = f"{test_marker} 第二轮 beta"

    first = client.post(
        "/api/v1/assistant/run",
        json={"content": first_marker_payload},
    )
    assert first.status_code == 200, first.text
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/v1/assistant/run",
        json={"conversation_id": conversation_id, "content": second_marker_payload},
    )
    assert second.status_code == 200, second.text

    # The decide prompt fired on each turn. The second turn's prompt should
    # contain the first turn's user content + assistant content under 对话历史.
    decide_prompts = [p for p in seen_prompts if "请严格按以下两种 JSON" in p]
    assert len(decide_prompts) == 2
    second_decide = decide_prompts[1]
    assert "对话历史" in second_decide
    assert "alpha" in second_decide  # user msg from turn 1
    assert "好的,继续聊" in second_decide  # assistant msg from turn 1


def test_summarize_fires_when_message_threshold_reached(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """Seed messages straight into the DB so the next turn crosses the
    threshold, then send one real turn and verify ``memory_summaries`` is
    populated with the LLM-produced summary text."""
    assert client.get("/health/db").status_code == 200

    # We need to insert messages BEFORE the API call. Use a fresh engine.
    async def _seed(db: AsyncSession) -> int:
        user = (
            await db.execute(select(User).where(User.username == "test"))
        ).scalar_one()
        conversation = Conversation(user_id=user.id, title=f"{test_marker} sum conv")
        db.add(conversation)
        await db.flush()
        # Seed SUMMARIZE_MESSAGE_THRESHOLD - 1 messages so the next user
        # message + assistant message crosses the threshold.
        seed_count = SUMMARIZE_MESSAGE_THRESHOLD - 1
        for i in range(1, seed_count + 1):
            db.add(
                Message(
                    user_id=user.id,
                    conversation_id=conversation.id,
                    role="user" if i % 2 == 1 else "assistant",
                    content=f"{test_marker} seeded msg #{i}",
                    sequence_no=i,
                ),
            )
        await db.commit()
        await db.refresh(conversation)
        return conversation.id

    conversation_id = _run(_seed)

    summary_text = f"{test_marker} this is the synthetic summary"

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON" in prompt:
            return '{"action": "respond_directly", "text": "ok"}'
        if "对话摘要生成器" in prompt:
            return summary_text
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    response = client.post(
        "/api/v1/assistant/run",
        json={"conversation_id": conversation_id, "content": f"{test_marker} trigger summary"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agent_run"]["status"] == "succeeded"

    async def _verify(db: AsyncSession) -> None:
        row = (
            await db.execute(
                select(MemorySummary).where(
                    MemorySummary.conversation_id == conversation_id,
                ),
            )
        ).scalar_one()
        assert row.summary_text == summary_text
        assert row.based_on_until_message_id is not None

    _run(_verify)


def test_summary_not_written_below_threshold(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """A fresh conversation with one turn should NOT trigger summarisation."""
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON" in prompt:
            return '{"action": "respond_directly", "text": "ok"}'
        if "对话摘要生成器" in prompt:
            # If this fires, the threshold logic is wrong.
            raise AssertionError("summary should not fire for a 2-message conversation")
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    response = client.post(
        "/api/v1/assistant/run",
        json={"content": f"{test_marker} short turn"},
    )
    assert response.status_code == 200, response.text
    conversation_id = response.json()["conversation_id"]

    async def _verify(db: AsyncSession) -> None:
        row = (
            await db.execute(
                select(MemorySummary).where(
                    MemorySummary.conversation_id == conversation_id,
                ),
            )
        ).scalar_one_or_none()
        assert row is None

    _run(_verify)
