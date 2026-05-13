"""Assistant-level knowledge-base context tests.

These cover the wiring above the search_knowledge tool: when the UI selects a
KB, the workflow must constrain search_knowledge to that KB even if the LLM
omits the argument.
"""

import asyncio
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.llm.client import LLMClient
from app.llm.embedding_client import EmbeddingClient
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.tool_call_log import ToolCallLog
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


def _vec(axis: int = 0) -> list[float]:
    vector = [0.0] * settings.embedding_dimensions
    vector[axis] = 1.0
    return vector


def test_assistant_selected_kb_overrides_search_knowledge_args(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _seed(db: AsyncSession) -> tuple[int, int]:
        user = (
            await db.execute(select(User).where(User.username == "test"))
        ).scalar_one()
        kb_a = KnowledgeBase(user_id=user.id, name=f"{test_marker} A")
        kb_b = KnowledgeBase(user_id=user.id, name=f"{test_marker} B")
        db.add_all([kb_a, kb_b])
        await db.flush()
        doc_a = KnowledgeDocument(
            knowledge_base_id=kb_a.id,
            user_id=user.id,
            title=f"{test_marker} A doc",
            source_type="manual",
            raw_text="A raw",
            content_hash=f"{test_marker[-24:]}-assistant-a",
            status="ready",
            chunk_count=1,
        )
        doc_b = KnowledgeDocument(
            knowledge_base_id=kb_b.id,
            user_id=user.id,
            title=f"{test_marker} B doc",
            source_type="manual",
            raw_text="B raw",
            content_hash=f"{test_marker[-24:]}-assistant-b",
            status="ready",
            chunk_count=1,
        )
        db.add_all([doc_a, doc_b])
        await db.flush()
        db.add_all(
            [
                KnowledgeChunk(
                    document_id=doc_a.id,
                    user_id=user.id,
                    chunk_index=0,
                    content=f"{test_marker} A 库内容,不应被选中。",
                    embedding=_vec(0),
                    char_start=0,
                    char_end=20,
                ),
                KnowledgeChunk(
                    document_id=doc_b.id,
                    user_id=user.id,
                    chunk_index=0,
                    content=f"{test_marker} B 库内容,应该被返回。",
                    embedding=_vec(0),
                    char_start=0,
                    char_end=20,
                ),
            ],
        )
        await db.commit()
        return kb_a.id, kb_b.id

    _, kb_b_id = _run(_seed)

    async def fake_embed(self: EmbeddingClient, texts: list[str]) -> list[list[float]]:
        assert texts == ["资料"]
        return [_vec(0)]

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)

    calls = {"count": 0}

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON 之一回复" in prompt:
            calls["count"] += 1
            if calls["count"] == 1:
                return (
                    '{"action": "call_tool", "tool": "search_knowledge", '
                    '"args": {"query": "资料", "top_k": 10}}'
                )
            return '{"action": "respond_directly", "text": "已查到 B 库内容"}'
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    response = client.post(
        "/api/v1/assistant/run",
        json={
            "content": f"{test_marker} 查资料",
            "context": {"knowledge_base_id": kb_b_id},
        },
    )
    assert response.status_code == 200, response.text

    agent_run_id = response.json()["agent_run"]["id"]

    async def _read_log(db: AsyncSession) -> ToolCallLog:
        return (
            await db.execute(
                select(ToolCallLog).where(ToolCallLog.agent_run_id == agent_run_id),
            )
        ).scalar_one()

    log = _run(_read_log)
    assert log.tool_name == "search_knowledge"
    assert log.arguments_json["knowledge_base_id"] == kb_b_id
    assert log.result_json["knowledge_base_id"] == kb_b_id
    contents = [hit["content"] for hit in log.result_json["hits"]]
    assert any("B 库内容" in text for text in contents)
    assert all("A 库内容" not in text for text in contents)
