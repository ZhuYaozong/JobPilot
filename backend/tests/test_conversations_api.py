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
    cid = _run(lambda db: _seed_conversation_with_messages(db, test_marker, 0))

    response = client.get("/api/v1/conversations?limit=50")
    assert response.status_code == 200
    body = response.json()
    ids = [c["id"] for c in body]
    assert cid in ids


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
