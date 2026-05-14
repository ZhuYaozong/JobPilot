"""Integration tests for TailoredResumeTool."""

import asyncio
import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.tailored_resume_tool import TailoredResumeTool
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
    "skills": ["FastAPI", "LangGraph", "PostgreSQL"],
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
    "preferred_skills": ["LangGraph"],
    "keywords": ["workflow", "ai application"],
    "seniority": "junior-mid",
    "city": "Shanghai",
}


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
        title=f"{marker} tailored resume",
        raw_text="FastAPI and LangGraph experience.",
        content_hash=f"{marker}-tr-res",
        source_type="manual",
        parsed_json=_PARSED_RESUME,
        parse_status="parsed",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} tailored company",
        job_title="AI Application Engineer",
        city="Shanghai",
        jd_text="Build AI workflow apps.",
        parsed_json=_PARSED_JOB,
    )
    db.add_all([resume, job])
    await db.flush()

    if with_match:
        db.add(
            MatchResult(
                user_id=user.id,
                resume_id=resume.id,
                job_posting_id=job.id,
                overall_score=86.0,
                strengths=["FastAPI"],
                weaknesses=[],
                missing_keywords=[],
                suggestions=["Highlight workflow project impact"],
            ),
        )

    conversation = Conversation(user_id=user.id, title=f"{marker} tr conversation")
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


def test_tailored_resume_tool_happy_path(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return json.dumps(
            {
                "version_label": "AI 定制版",
                "content_markdown": "# 定制简历\n\n- JobPilot workflow",
                "change_summary": ["突出 workflow 项目"],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db,
            marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await TailoredResumeTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["version_no"] == 1
        assert data["source_type"] == "ai_tailored"
        assert data["resume_id"] == resume_id
        assert data["job_posting_id"] == job_id
        assert "JobPilot" in data["content"]

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "success"
        assert logs[0].tool_name == "generate_tailored_resume"

    _run(_scenario)


def test_tailored_resume_tool_missing_match_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db,
            marker=test_marker,
            with_match=False,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await TailoredResumeTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "match_result_missing"
        assert "analyze_match" in result["message_for_llm"]

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "failed"
        assert logs[0].error_class == "match_result_missing"

    _run(_scenario)

