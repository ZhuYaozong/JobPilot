"""ParseResumeTool 集成测试。"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext, ToolSystemError
from app.agent.tools.parse_resume_tool import ParseResumeTool
from app.core.config import settings
from app.llm.client import LLMClient, LLMClientError
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.resume import Resume
from app.models.user import User


def _fake_parse_response() -> str:
    return json.dumps(
        {
            "summary": "3 年 AI 应用研发",
            "skills": ["Python", "FastAPI"],
            "experiences": ["Built JobPilot"],
            "projects": ["JobPilot"],
            "education": [],
            "target_roles": ["AI 应用工程师"],
            "years_of_experience": "3 年",
        },
        ensure_ascii=False,
    )


async def _setup(
    db: AsyncSession,
    *,
    marker: str,
    raw_text: str = "FastAPI / LangGraph 经验。",
) -> tuple[User, int, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    resume = Resume(
        user_id=user.id,
        title=f"{marker} parse-resume",
        raw_text=raw_text,
        content_hash=f"{marker}-parse-res",
        source_type="manual",
        parse_status="pending",
    )
    db.add(resume)
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} parse-resume conv")
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


def test_parse_resume_tool_happy_path(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return _fake_parse_response()

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ParseResumeTool().invoke({"resume_id": resume_id}, ctx)
        assert result["ok"] is True
        data = result["data"]
        assert data["resume_id"] == resume_id
        assert data["parse_status"] == "parsed"
        assert data["parsed_json"]["skills"] == ["Python", "FastAPI"]

        # 数据库里 status / parsed_json 已落。
        rows = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = rows.scalar_one()
        assert resume.parse_status == "parsed"
        assert resume.parsed_json is not None

    _run(_scenario)


def test_parse_resume_tool_not_found_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ParseResumeTool().invoke({"resume_id": 999_999_999}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "resume_not_found"

    _run(_scenario)


def test_parse_resume_tool_llm_failure_raises_system_error(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        raise LLMClientError("upstream timeout")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        with pytest.raises(ToolSystemError) as excinfo:
            await ParseResumeTool().invoke({"resume_id": resume_id}, ctx)
        assert excinfo.value.error_class == "llm_unavailable"

    _run(_scenario)


def test_parse_resume_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["parse_resume"] is ParseResumeTool
