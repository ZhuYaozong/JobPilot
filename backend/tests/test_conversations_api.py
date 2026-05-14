"""GET /api/v1/conversations 与 /{id}/messages 测试。"""

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
    # 抬高预置会话的 last_run_at，让它在共享测试库积累很多旧会话时，
    # 仍然能排进 top-100 结果。
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

    # 基础确认：删除前消息确实存在。
    pre = client.get(f"/api/v1/conversations/{cid}/messages")
    assert pre.status_code == 200
    assert len(pre.json()) == 3

    response = client.delete(f"/api/v1/conversations/{cid}")
    assert response.status_code == 204

    # 删除后会话应不存在（404），列表也不再展示它。
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
    """新建会话的第一条用户消息应成为标题（截断后），替代旧的日期占位标题。"""
    from app.llm.client import LLMClient
    from tests.test_assistant_api import _make_fake_llm

    monkeypatch.setattr(
        LLMClient,
        "generate_text",
        _make_fake_llm(
            decide_response='{"action": "respond_directly", "text": "好的。"}',
        ),
    )

    # 把 marker 放在最前面，确保标题被 28 字符截断后仍保留足够前缀用于断言。
    first_question = f"{test_marker} 帮我看下今天该做什么"
    response = client.post(
        "/api/v1/assistant/run",
        json={"content": first_question},
    )
    assert response.status_code == 200
    conv_id = response.json()["conversation_id"]

    # 直接按 id 查询会话，而不走列表 endpoint。共享测试库可能超过 100 行，
    # 列表硬上限会把目标会话藏掉。
    title = _run(
        lambda db: _fetch_conversation_title(db, conv_id),
    )
    assert title is not None
    # 标题应反映用户问题，而不是带日期的占位标题。test_marker 约 48 字符，
    # 标题上限是 28 + "…"，所以只断言稳定的 "pytest-jobpilot-" 前缀。
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
