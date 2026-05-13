"""GET /api/v1/conversations and /{id}/messages tests."""

import asyncio
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


def _run(coro_factory: Callable) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


async def _seed_conversation_with_messages(
    db: AsyncSession, marker: str, n_messages: int,
) -> int:
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} conv")
    db.add(conversation)
    await db.flush()
    for seq in range(1, n_messages + 1):
        role = "user" if seq % 2 == 1 else "assistant"
        db.add(
            Message(
                user_id=user.id,
                conversation_id=conversation.id,
                role=role,
                content=f"{marker} msg {seq}",
                sequence_no=seq,
            ),
        )
    await db.commit()
    await db.refresh(conversation)
    return conversation.id


def test_list_conversations_returns_recent_first(
    client: TestClient, test_marker: str,
) -> None:
    # Bump last_run_at on the seeded conversation so it ranks high enough
    # to show up in the top-100 result regardless of how many older
    # conversations the shared test DB has accumulated.
    cid = _run(
        lambda db: _seed_conversation_with_recent_run(db, test_marker),
    )

    response = client.get("/api/v1/conversations?limit=100")
    assert response.status_code == 200
    body = response.json()
    ids = [c["id"] for c in body]
    assert cid in ids


async def _seed_conversation_with_recent_run(
    db: AsyncSession, marker: str,
) -> int:
    from datetime import datetime, timezone

    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    conversation = Conversation(
        user_id=user.id,
        title=f"{marker} conv",
        last_run_at=datetime.now(timezone.utc),
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation.id


def test_list_messages_in_sequence_order(
    client: TestClient, test_marker: str,
) -> None:
    cid = _run(lambda db: _seed_conversation_with_messages(db, test_marker, 5))

    response = client.get(f"/api/v1/conversations/{cid}/messages")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5
    assert [m["sequence_no"] for m in body] == [1, 2, 3, 4, 5]
    assert [m["role"] for m in body] == [
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]


def test_list_messages_rejects_other_users_conversation(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/conversations/999999999/messages")
    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


def test_update_conversation_renames_title(
    client: TestClient, test_marker: str,
) -> None:
    cid = _run(lambda db: _seed_conversation_with_messages(db, test_marker, 0))

    response = client.patch(
        f"/api/v1/conversations/{cid}",
        json={"title": f"{test_marker} 改名后"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == cid
    assert body["title"] == f"{test_marker} 改名后"


def test_update_conversation_rejects_empty_title(
    client: TestClient, test_marker: str,
) -> None:
    cid = _run(lambda db: _seed_conversation_with_messages(db, test_marker, 0))

    response = client.patch(
        f"/api/v1/conversations/{cid}",
        json={"title": "   "},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_update_conversation_rejects_other_users(
    client: TestClient, test_marker: str,
) -> None:
    response = client.patch(
        "/api/v1/conversations/999999999",
        json={"title": f"{test_marker}"},
    )
    assert response.status_code == 404


def test_delete_conversation_cascades_messages(
    client: TestClient, test_marker: str,
) -> None:
    cid = _run(lambda db: _seed_conversation_with_messages(db, test_marker, 3))

    # Sanity: messages exist before delete.
    pre = client.get(f"/api/v1/conversations/{cid}/messages")
    assert pre.status_code == 200
    assert len(pre.json()) == 3

    response = client.delete(f"/api/v1/conversations/{cid}")
    assert response.status_code == 204

    # After delete the conversation is gone (404) and listing no longer
    # surfaces it.
    post = client.get(f"/api/v1/conversations/{cid}/messages")
    assert post.status_code == 404

    listing = client.get("/api/v1/conversations?limit=50")
    assert listing.status_code == 200
    assert cid not in [c["id"] for c in listing.json()]


def test_delete_conversation_handles_agent_run_message_cycle(
    client: TestClient, test_marker: str,
) -> None:
    cid = _run(lambda db: _seed_conversation_with_agent_run_graph(db, test_marker))

    response = client.delete(f"/api/v1/conversations/{cid}")
    assert response.status_code == 204, response.text

    post = client.get(f"/api/v1/conversations/{cid}/messages")
    assert post.status_code == 404


def test_delete_conversation_rejects_other_users(client: TestClient) -> None:
    response = client.delete("/api/v1/conversations/999999999")
    assert response.status_code == 404


def test_assistant_run_auto_titles_new_conversation_from_first_message(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """The first user message of a freshly-created conversation should become
    its title (truncated), replacing the old "新建对话 YYYY-MM-DD HH:MM"
    placeholder."""
    from app.llm.client import LLMClient
    from tests.test_assistant_api import _make_fake_llm

    monkeypatch.setattr(
        LLMClient,
        "generate_text",
        _make_fake_llm(
            decide_response='{"action": "respond_directly", "text": "好的。"}',
        ),
    )

    # Put the marker first so the truncated title (28-char cap) still keeps
    # enough of the marker prefix for the assertion below.
    first_question = f"{test_marker} 帮我看下今天该做什么"
    response = client.post(
        "/api/v1/assistant/run",
        json={"content": first_question},
    )
    assert response.status_code == 200
    conv_id = response.json()["conversation_id"]

    # Look up the conversation directly by id rather than going through the
    # listing endpoint — the shared test DB can hold more than 100 rows,
    # which the listing's hard cap would otherwise hide.
    title = _run(
        lambda db: _fetch_conversation_title(db, conv_id),
    )
    assert title is not None
    # The title should reflect the user's question, not the date-stamped
    # placeholder. test_marker is ~48 chars but the title caps at 28 + "…",
    # so we only assert the stable "pytest-jobpilot-" prefix.
    assert "pytest-jobpilot-" in title
    assert "新建对话" not in title


async def _fetch_conversation_title(db: AsyncSession, conv_id: int) -> str | None:
    row = (
        await db.execute(
            select(Conversation.title).where(Conversation.id == conv_id),
        )
    ).one_or_none()
    return row.title if row else None


async def _seed_conversation_with_agent_run_graph(
    db: AsyncSession, marker: str,
) -> int:
    from app.models.agent_run import AgentRun
    from app.models.memory_summary import MemorySummary
    from app.models.tool_call_log import ToolCallLog

    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} delete graph")
    db.add(conversation)
    await db.flush()

    user_message = Message(
        user_id=user.id,
        conversation_id=conversation.id,
        role="user",
        content=f"{marker} hello",
        sequence_no=1,
    )
    db.add(user_message)
    await db.flush()

    agent_run = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        trigger_message_id=user_message.id,
        status="success",
    )
    db.add(agent_run)
    await db.flush()

    assistant_message = Message(
        user_id=user.id,
        conversation_id=conversation.id,
        role="assistant",
        content=f"{marker} response",
        agent_run_id=agent_run.id,
        sequence_no=2,
    )
    db.add(assistant_message)
    db.add(
        ToolCallLog(
            user_id=user.id,
            agent_run_id=agent_run.id,
            tool_name="list_user_jobs",
            status="success",
            arguments_json={},
            result_json={"ok": True},
        ),
    )
    await db.flush()
    db.add(
        MemorySummary(
            user_id=user.id,
            conversation_id=conversation.id,
            summary_text=f"{marker} summary",
            based_on_until_message_id=assistant_message.id,
        ),
    )
    await db.commit()
    return conversation.id
