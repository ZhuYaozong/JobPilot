"""AddKnowledgeTextTool 集成测试。

覆盖:成功路径(mock embedding)、KB 不存在、内容太短、description 含显式触发约束。
"""

import asyncio
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext, ToolValidationError
from app.agent.tools.add_knowledge_text_tool import AddKnowledgeTextTool
from app.core.config import settings
from app.llm.embedding_client import EmbeddingClient
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_document import KnowledgeDocument
from app.models.user import User


def _fake_embedding(text: str, dim: int) -> list[float]:
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    raw = (seed * (dim // len(seed) + 1))[:dim]
    return [(b / 127.5) - 1.0 for b in raw]


def _install_fake_embedder(monkeypatch) -> None:
    target_dim = settings.embedding_dimensions

    async def fake_embed(self, texts: list[str]) -> list[list[float]]:
        return [_fake_embedding(t, target_dim) for t in texts]

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)


async def _setup(
    db: AsyncSession,
    *,
    marker: str,
) -> tuple[User, int, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    kb = KnowledgeBase(user_id=user.id, name=f"{marker} kb")
    db.add(kb)
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} add-kn conv")
    db.add(conversation)
    await db.flush()
    agent_run = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(kb)
    await db.refresh(agent_run)
    return user, agent_run.id, kb.id


def _run(coro_factory) -> None:
    async def _do():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await coro_factory(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


def test_add_knowledge_text_tool_happy_path(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200
    _install_fake_embedder(monkeypatch)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, kb_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        long_content = (
            f"{test_marker} 这是面试反馈记录,包含项目细节、面试官的具体反馈,以及后续行动。"
            * 5
        )
        result = await AddKnowledgeTextTool().invoke(
            {
                "knowledge_base_id": kb_id,
                "title": f"{test_marker} 面试反馈",
                "content": long_content,
            },
            ctx,
        )
        assert result["ok"] is True, result
        data = result["data"]
        assert data["knowledge_base_id"] == kb_id
        assert data["title"].startswith(test_marker)
        # 索引应该成功(fake embed 一直 ok)→ status=ready, chunk_count > 0。
        assert data["status"] == "ready"
        assert data["chunk_count"] > 0

        # 数据库里确实有文档行。
        rows = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == data["document_id"]),
        )
        doc = rows.scalar_one()
        assert doc.source_type == "manual"

    _run(_scenario)


def test_add_knowledge_text_tool_kb_not_found(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _kb_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await AddKnowledgeTextTool().invoke(
            {
                "knowledge_base_id": 999_999_999,
                "title": f"{test_marker} t",
                "content": "x" * 50,
            },
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "knowledge_base_not_found"

    _run(_scenario)


def test_add_knowledge_text_tool_content_too_short_validation_error(
    client: TestClient,
    test_marker: str,
) -> None:
    """schema 层 min_length=30 直接拦下,工具层不需要走 service。"""
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, kb_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        # content 不足 30 字符 → Pydantic validation 抛 ToolValidationError(tool_adapter 包装)。
        with pytest.raises(ToolValidationError):
            await AddKnowledgeTextTool().invoke(
                {
                    "knowledge_base_id": kb_id,
                    "title": "t",
                    "content": "短",
                },
                ctx,
            )

    _run(_scenario)


def test_add_knowledge_text_tool_description_requires_explicit_save() -> None:
    """description 必须明确告诉 LLM:仅在用户要求保存时才用本工具,绝不主动调。"""
    desc = AddKnowledgeTextTool.description
    # 关键约束字样必须存在,否则 LLM 容易看到内容就自动调。
    assert "仅在用户明确要求保存时才调用" in desc
    assert "不要" in desc and "自动调用" in desc
    assert "绝不" in desc


def test_add_knowledge_text_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["add_knowledge_text"] is AddKnowledgeTextTool
