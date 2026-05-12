"""Integration tests for InterviewPrepTool.

Mirrors test_cover_letter_tool.py — same end-to-end pattern but exercises
interview_prep_service through the agent adapter.
"""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.interview_prep_tool import InterviewPrepTool
from app.core.config import settings
from app.llm.client import LLMClient
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


_PARSED_RESUME: dict[str, Any] = {
    "summary": "AI application backend engineer.",
    "skills": ["FastAPI", "SQLAlchemy", "PostgreSQL"],
    "experiences": ["Built workflow-backed APIs"],
    "projects": ["JobPilot"],
    "education": [],
    "target_roles": ["AI Application Engineer"],
    "years_of_experience": "2 years",
}

_PARSED_JOB: dict[str, Any] = {
    "summary": "Build workflow-backed AI applications.",
    "responsibilities": ["Build FastAPI services"],
    "required_skills": ["FastAPI", "PostgreSQL"],
    "preferred_skills": ["SQLAlchemy"],
    "keywords": ["workflow", "ai application"],
    "seniority": "junior-mid",
    "city": "Shanghai",
}

_FAKE_INTERVIEW_PREP = """
岗位核心考察点:
1. FastAPI 异步接口设计
2. AI workflow 编排

候选人优势:
- JobPilot 项目积累

可能的面试问题:
- 你如何处理 LLM 不稳定输出?
- 如何设计 schema repair?

准备建议:
准备一个端到端的 workflow 示例。
"""


async def _setup_environment(
    db: AsyncSession,
    *,
    marker: str,
    with_match: bool = True,
) -> tuple[User, int, int, int]:
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    resume = Resume(
        user_id=user.id,
        title=f"{marker} ip resume",
        raw_text="FastAPI experience.",
        content_hash=f"{marker}-ip-res",
        source_type="manual",
        parsed_json=_PARSED_RESUME,
        parse_status="parsed",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} ip company",
        job_title="AI Application Engineer",
        city="Shanghai",
        jd_text="Build AI workflow apps.",
        parsed_json=_PARSED_JOB,
    )
    db.add(resume)
    db.add(job)
    await db.flush()
    if with_match:
        db.add(
            MatchResult(
                user_id=user.id,
                resume_id=resume.id,
                job_posting_id=job.id,
                overall_score=80.0,
                strengths=["FastAPI"],
                weaknesses=[],
                missing_keywords=[],
                suggestions=[],
            ),
        )
        await db.flush()
    conversation = Conversation(user_id=user.id, title=f"{marker} ip conversation")
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
    await db.refresh(job)
    await db.refresh(agent_run)
    return user, agent_run.id, resume.id, job.id


def _run(coro_factory):
    async def _do():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await coro_factory(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


async def _fetch_logs(db: AsyncSession, agent_run_id: int) -> list[ToolCallLog]:
    result = await db.execute(
        select(ToolCallLog)
        .where(ToolCallLog.agent_run_id == agent_run_id)
        .order_by(ToolCallLog.id),
    )
    return list(result.scalars().all())


def test_interview_prep_tool_happy_path(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return _FAKE_INTERVIEW_PREP

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await InterviewPrepTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is True
        assert result["data"]["artifact_type"] == "interview_prep"
        assert "考察" in result["data"]["content_text"]

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "success"
        assert logs[0].tool_name == "generate_interview_prep"

    _run(_scenario)


def test_interview_prep_tool_missing_match_returns_business_error(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db, marker=test_marker, with_match=False,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await InterviewPrepTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "match_result_missing"

    _run(_scenario)


def test_interview_prep_tool_too_generic_output_classified(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def too_generic(self, prompt: str) -> str:
        return "你很适合这个岗位。"

    monkeypatch.setattr(LLMClient, "generate_text", too_generic)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await InterviewPrepTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "llm_output_too_generic"

    _run(_scenario)


def test_interview_prep_tool_resume_not_found(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id, job_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await InterviewPrepTool().invoke(
            {"resume_id": 999_999_999, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "resume_not_found"

    _run(_scenario)
