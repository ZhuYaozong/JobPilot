"""ReadResumeTool 集成测试。"""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.read_resume_tool import ReadResumeTool
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.resume import Resume
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


_PARSED_RESUME: dict[str, Any] = {
    "summary": "AI 应用研发",
    "skills": ["Python", "FastAPI"],
    "experiences": ["Built JobPilot"],
    "projects": ["JobPilot"],
    "education": [],
    "target_roles": ["AI 应用工程师"],
    "years_of_experience": "3 年",
}


async def _setup(
    db: AsyncSession,
    *,
    marker: str,
    parsed: dict[str, Any] | None = _PARSED_RESUME,
) -> tuple[User, int, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    resume = Resume(
        user_id=user.id,
        title=f"{marker} read-resume",
        raw_text=f"{marker} 简历正文",
        content_hash=f"{marker}-read-res",
        source_type="manual",
        parsed_json=parsed,
        parse_status="parsed" if parsed else "pending",
    )
    db.add(resume)
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} read-resume conv")
    db.add(conversation)
    await db.flush()
    agent_run = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(resume)
    await db.refresh(agent_run)
    return user, agent_run.id, resume.id


def _run(coro_factory) -> None:
    async def _do():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await coro_factory(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


async def _fetch_logs(db: AsyncSession, agent_run_id: int) -> list[ToolCallLog]:
    rows = await db.execute(
        select(ToolCallLog).where(ToolCallLog.agent_run_id == agent_run_id),
    )
    return list(rows.scalars().all())


def test_read_resume_tool_happy_path_parsed(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ReadResumeTool().invoke({"resume_id": resume_id}, ctx)
        assert result["ok"] is True
        data = result["data"]
        assert data["id"] == resume_id
        assert data["title"] == f"{test_marker} read-resume"
        assert data["parse_status"] == "parsed"
        assert data["parsed_json"]["skills"] == ["Python", "FastAPI"]
        # raw_text 必须完整透出。
        assert data["raw_text"] == f"{test_marker} 简历正文"
        # 时间字段必须是 ISO 字符串(可 JSON 序列化)。
        assert isinstance(data["created_at"], str)

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "success"

    _run(_scenario)


def test_read_resume_tool_pending_resume(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id = await _setup(db, marker=test_marker, parsed=None)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ReadResumeTool().invoke({"resume_id": resume_id}, ctx)
        assert result["ok"] is True
        assert result["data"]["parse_status"] == "pending"
        assert result["data"]["parsed_json"] is None

    _run(_scenario)


def test_read_resume_tool_not_found_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ReadResumeTool().invoke({"resume_id": 999_999_999}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "resume_not_found"
        assert "list_user_resumes" in result["message_for_llm"]

    _run(_scenario)


def test_read_resume_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["read_resume"] is ReadResumeTool


# 防御:invoke 后访问 user.id 会触发 lazy load,跨用户测试需提前缓存。
_: Any = pytest
