"""ParseJobPostingTool 集成测试。"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext, ToolSystemError
from app.agent.tools.parse_job_posting_tool import ParseJobPostingTool
from app.core.config import settings
from app.llm.client import LLMClient, LLMClientError
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.user import User


def _fake_parse_response() -> str:
    return json.dumps(
        {
            "summary": "构建 AI 应用",
            "responsibilities": ["设计 Agent 工作流"],
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["LangGraph"],
            "keywords": ["LLM"],
            "seniority": "中级",
            "city": "上海",
        },
        ensure_ascii=False,
    )


async def _setup(
    db: AsyncSession,
    *,
    marker: str,
    jd_text: str = "招聘 AI 应用研发工程师,负责 Agent 工作流。",
) -> tuple[User, int, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} ParseCo",
        job_title="AI 应用研发工程师",
        city="上海",
        jd_text=jd_text,
    )
    db.add(job)
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} parse-job conv")
    db.add(conversation)
    await db.flush()
    agent_run = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(job)
    await db.refresh(agent_run)
    return user, agent_run.id, job.id


def _run(coro_factory) -> None:
    async def _do():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await coro_factory(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


def test_parse_job_posting_tool_happy_path(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return _fake_parse_response()

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ParseJobPostingTool().invoke({"job_posting_id": job_id}, ctx)
        assert result["ok"] is True
        data = result["data"]
        assert data["job_posting_id"] == job_id
        assert data["parse_status"] == "parsed"
        assert data["parsed_json"]["seniority"] == "中级"

        rows = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
        job = rows.scalar_one()
        assert job.parsed_json is not None

    _run(_scenario)


def test_parse_job_posting_tool_not_found_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ParseJobPostingTool().invoke({"job_posting_id": 999_999_999}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "job_posting_not_found"

    _run(_scenario)


def test_parse_job_posting_tool_llm_failure_raises_system_error(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        raise LLMClientError("upstream timeout")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        with pytest.raises(ToolSystemError) as excinfo:
            await ParseJobPostingTool().invoke({"job_posting_id": job_id}, ctx)
        assert excinfo.value.error_class == "llm_unavailable"

    _run(_scenario)


def test_parse_job_posting_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["parse_job_posting"] is ParseJobPostingTool
