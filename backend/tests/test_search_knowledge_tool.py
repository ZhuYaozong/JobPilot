"""search_knowledge 检索工具测试，对应 7'c3。

工具本身刻意保持轻量，但它位于 Agent -> embedding client -> pgvector -> ACL filtering 的关键路径上。
这些测试直接预置数据行，让每个不变量都能在不引入 LLM 的情况下被看见。
"""

import asyncio
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.search_knowledge_tool import SearchKnowledgeTool
from app.core.config import settings
from app.llm.embedding_client import (
    EmbeddingClient,
    EmbeddingConfigError,
)
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
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


def _vec(axis: int = 0, value: float = 1.0) -> list[float]:
    vector = [0.0] * settings.embedding_dimensions
    vector[axis] = value
    return vector


def _marker_axis(marker: str) -> int:
    return int(marker[-6:], 16) % settings.embedding_dimensions


def _install_query_embedder(monkeypatch, vector: list[float]) -> None:
    async def fake_embed(self: EmbeddingClient, texts: list[str]) -> list[list[float]]:
        assert len(texts) == 1
        return [vector]

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)


def _install_failing_embedder(monkeypatch, exc: Exception) -> None:
    async def fake_embed(self: EmbeddingClient, texts: list[str]) -> list[list[float]]:
        raise exc

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)


async def _setup_agent_run(db: AsyncSession, marker: str) -> tuple[User, int]:
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} search conv")
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


async def _other_user(db: AsyncSession) -> User:
    return (
        await db.execute(select(User).where(User.username == "demo"))
    ).scalar_one()


async def _seed_kb(
    db: AsyncSession,
    *,
    user_id: int,
    marker: str,
    suffix: str,
) -> tuple[KnowledgeBase, KnowledgeDocument]:
    kb = KnowledgeBase(
        user_id=user_id,
        name=f"{marker} {suffix} KB",
        description="pytest search_knowledge",
    )
    db.add(kb)
    await db.flush()
    doc = KnowledgeDocument(
        knowledge_base_id=kb.id,
        user_id=user_id,
        title=f"{marker} {suffix} doc",
        source_type="manual",
        raw_text=f"{marker} {suffix} raw text",
        content_hash=f"{marker[-32:]}-{suffix[:20]}",
        status="ready",
        chunk_count=0,
    )
    db.add(doc)
    await db.flush()
    return kb, doc


async def _seed_chunk(
    db: AsyncSession,
    *,
    doc: KnowledgeDocument,
    content: str,
    embedding: list[float] | None,
    index: int = 0,
) -> KnowledgeChunk:
    chunk = KnowledgeChunk(
        document_id=doc.id,
        user_id=doc.user_id,
        chunk_index=index,
        content=content,
        embedding=embedding,
        char_start=0,
        char_end=len(content),
    )
    db.add(chunk)
    await db.flush()
    doc.chunk_count = int(doc.chunk_count or 0) + 1
    return chunk


def test_search_knowledge_returns_nearest_chunks_and_logs_success(
    monkeypatch, test_marker: str,
) -> None:
    axis = _marker_axis(test_marker)
    other_axis = (axis + 1) % settings.embedding_dimensions
    _install_query_embedder(monkeypatch, _vec(axis))

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        kb, doc = await _seed_kb(
            db, user_id=user.id, marker=test_marker, suffix="happy",
        )
        target = await _seed_chunk(
            db,
            doc=doc,
            content=f"{test_marker} ByteDance 推荐系统项目,延迟降低 40%。",
            embedding=_vec(axis),
            index=0,
        )
        await _seed_chunk(
            db,
            doc=doc,
            content=f"{test_marker} 无关的面试礼仪笔记。",
            embedding=_vec(other_axis),
            index=1,
        )
        await db.commit()
        target_id = target.id
        doc_title = doc.title
        kb_id = kb.id

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await SearchKnowledgeTool().invoke(
            {
                "query": "ByteDance 推荐系统",
                "knowledge_base_id": kb_id,
                "top_k": 1,
            },
            ctx,
        )

        assert result["ok"] is True
        hits = result["data"]["hits"]
        assert result["data"]["count"] == 1
        assert hits[0]["chunk_id"] == target_id
        assert hits[0]["document_title"] == doc_title
        assert "ByteDance" in hits[0]["content"]
        assert hits[0]["distance"] == 0.0
        assert hits[0]["relevance"] == 1.0

        log = (
            await db.execute(
                select(ToolCallLog).where(ToolCallLog.agent_run_id == agent_run_id),
            )
        ).scalar_one()
        assert log.tool_name == "search_knowledge"
        assert log.status == "success"
        assert log.result_json["count"] == 1

    _run(_scenario)


def test_search_knowledge_excludes_other_users_chunks(
    monkeypatch, test_marker: str,
) -> None:
    axis = _marker_axis(test_marker)
    _install_query_embedder(monkeypatch, _vec(axis))

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        other = await _other_user(db)
        _, own_doc = await _seed_kb(
            db, user_id=user.id, marker=test_marker, suffix="own",
        )
        _, other_doc = await _seed_kb(
            db, user_id=other.id, marker=test_marker, suffix="other",
        )
        await _seed_chunk(
            db,
            doc=own_doc,
            content=f"{test_marker} 自己的知识库内容。",
            embedding=_vec(axis),
        )
        await _seed_chunk(
            db,
            doc=other_doc,
            content=f"{test_marker} 别人的高度相关内容。",
            embedding=_vec(axis),
        )
        await db.commit()

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await SearchKnowledgeTool().invoke(
            {"query": "高度相关", "top_k": 20}, ctx,
        )

        assert result["ok"] is True
        contents = [hit["content"] for hit in result["data"]["hits"]]
        assert any("自己的知识库内容" in text for text in contents)
        assert all("别人的高度相关内容" not in text for text in contents)

    _run(_scenario)


def test_search_knowledge_filters_by_knowledge_base_id(
    monkeypatch, test_marker: str,
) -> None:
    axis = _marker_axis(test_marker)
    other_axis = (axis + 1) % settings.embedding_dimensions
    _install_query_embedder(monkeypatch, _vec(axis))

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        kb_a, doc_a = await _seed_kb(
            db, user_id=user.id, marker=test_marker, suffix="kb-a",
        )
        kb_b, doc_b = await _seed_kb(
            db, user_id=user.id, marker=test_marker, suffix="kb-b",
        )
        await _seed_chunk(
            db,
            doc=doc_a,
            content=f"{test_marker} A 库内容,相似度最高但不应返回。",
            embedding=_vec(axis),
        )
        expected = await _seed_chunk(
            db,
            doc=doc_b,
            content=f"{test_marker} B 库内容,被 knowledge_base_id 指定。",
            embedding=_vec(other_axis),
        )
        await db.commit()
        expected_id = expected.id
        kb_a_id = kb_a.id
        kb_b_id = kb_b.id

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await SearchKnowledgeTool().invoke(
            {
                "query": "库内容",
                "knowledge_base_id": kb_b_id,
                "top_k": 5,
            },
            ctx,
        )

        assert result["ok"] is True
        hits = result["data"]["hits"]
        assert [hit["chunk_id"] for hit in hits] == [expected_id]
        assert result["data"]["knowledge_base_id"] == kb_b_id
        assert hits[0]["knowledge_base_id"] == kb_b_id
        assert kb_a_id != kb_b_id

    _run(_scenario)


def test_search_knowledge_rejects_other_users_knowledge_base(
    monkeypatch, test_marker: str,
) -> None:
    _install_query_embedder(monkeypatch, _vec(_marker_axis(test_marker)))

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        other = await _other_user(db)
        other_kb, _ = await _seed_kb(
            db, user_id=other.id, marker=test_marker, suffix="foreign",
        )
        await db.commit()
        other_kb_id = other_kb.id

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await SearchKnowledgeTool().invoke(
            {
                "query": "任何内容",
                "knowledge_base_id": other_kb_id,
            },
            ctx,
        )

        assert result["ok"] is False
        assert result["error_class"] == "knowledge_base_not_found"
        assert "不存在或不属于当前用户" in result["message_for_llm"]

        log = (
            await db.execute(
                select(ToolCallLog).where(ToolCallLog.agent_run_id == agent_run_id),
            )
        ).scalar_one()
        assert log.status == "failed"
        assert log.error_class == "knowledge_base_not_found"

    _run(_scenario)


def test_search_knowledge_skips_chunks_without_embedding(
    monkeypatch, test_marker: str,
) -> None:
    axis = _marker_axis(test_marker)
    _install_query_embedder(monkeypatch, _vec(axis))

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        kb, doc = await _seed_kb(
            db, user_id=user.id, marker=test_marker, suffix="null-embedding",
        )
        await _seed_chunk(
            db,
            doc=doc,
            content=f"{test_marker} pending/failed document chunk.",
            embedding=None,
        )
        ready_chunk = await _seed_chunk(
            db,
            doc=doc,
            content=f"{test_marker} ready embedded chunk.",
            embedding=_vec(axis),
            index=1,
        )
        await db.commit()
        ready_chunk_id = ready_chunk.id
        kb_id = kb.id

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await SearchKnowledgeTool().invoke(
            {
                "query": "document chunk",
                "knowledge_base_id": kb_id,
                "top_k": 5,
            },
            ctx,
        )

        assert result["ok"] is True
        hits = result["data"]["hits"]
        assert [hit["chunk_id"] for hit in hits] == [ready_chunk_id]
        assert all("pending/failed" not in hit["content"] for hit in hits)

    _run(_scenario)


def test_search_knowledge_embedding_config_error_is_business_error(
    monkeypatch, test_marker: str,
) -> None:
    _install_failing_embedder(
        monkeypatch, EmbeddingConfigError("missing embedding config"),
    )

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        _, doc = await _seed_kb(
            db, user_id=user.id, marker=test_marker, suffix="config-error",
        )
        await _seed_chunk(
            db,
            doc=doc,
            content=f"{test_marker} existing chunk.",
            embedding=_vec(_marker_axis(test_marker)),
        )
        await db.commit()

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await SearchKnowledgeTool().invoke({"query": "x"}, ctx)

        assert result["ok"] is False
        assert result["error_class"] == "embedding_config_missing"
        assert "embedding 接口没有配置" in result["message_for_llm"]

        log = (
            await db.execute(
                select(ToolCallLog).where(ToolCallLog.agent_run_id == agent_run_id),
            )
        ).scalar_one()
        assert log.status == "failed"
        assert log.error_class == "embedding_config_missing"

    _run(_scenario)
