"""Integration tests for the MatchAnalysisTool adapter.

Exercises the real analyze_match service end-to-end (with the LLM monkeypatched)
and asserts that each failure mode the service can produce gets classified
correctly and recorded in tool_call_logs.
"""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext, ToolSystemError
from app.agent.tools.match_analysis_tool import MatchAnalysisTool
from app.core.config import settings
from app.llm.client import LLMClient, LLMConfigError
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


_FAKE_PARSED_RESUME: dict[str, Any] = {
    "summary": "Backend engineer with workflow API experience.",
    "skills": ["FastAPI", "SQLAlchemy", "PostgreSQL"],
    "experiences": ["Built workflow services"],
    "projects": ["JobPilot"],
    "education": [],
    "target_roles": ["AI Application Engineer"],
    "years_of_experience": "2 years",
}

_FAKE_PARSED_JOB: dict[str, Any] = {
    "summary": "Build AI workflow apps.",
    "responsibilities": ["FastAPI services"],
    "required_skills": ["FastAPI", "PostgreSQL"],
    "preferred_skills": ["SQLAlchemy"],
    "keywords": ["workflow"],
    "seniority": "junior-mid",
    "city": "Shanghai",
}

_FAKE_LLM_MATCH_JSON = """
{
  "overall_score": 81,
  "strengths": ["FastAPI backend experience"],
  "weaknesses": ["Limited AI eval experience"],
  "missing_keywords": ["evaluation"],
  "suggestions": ["Add measurable workflow outcomes"]
}
"""


async def _setup_environment(
    db: AsyncSession,
    *,
    marker: str,
    resume_parsed: dict[str, Any] | None = _FAKE_PARSED_RESUME,
    job_parsed: dict[str, Any] | None = _FAKE_PARSED_JOB,
) -> tuple[User, int, int, int]:
    """Create user/conversation/agent_run plus a Resume and JobPosting that
    the tool can reference. Returns user, agent_run_id, resume_id, job_id."""
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()

    resume = Resume(
        user_id=user.id,
        title=f"{marker} resume",
        raw_text="FastAPI and workflow backend experience.",
        content_hash=f"{marker}-res",
        source_type="manual",
        parsed_json=resume_parsed,
        parse_status="parsed" if resume_parsed is not None else "pending",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} company",
        job_title="AI Application Engineer",
        city="Shanghai",
        jd_text="Build AI workflow apps.",
        parsed_json=job_parsed,
    )
    db.add(resume)
    db.add(job)
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} conversation")
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
    await db.refresh(resume)
    await db.refresh(job)
    return user, agent_run.id, resume.id, job.id


def _run_scenario(scenario) -> None:
    async def _do() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await scenario(db)
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


def test_match_analysis_tool_happy_path(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return _FAKE_LLM_MATCH_JSON

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        result = await MatchAnalysisTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )

        assert result["ok"] is True
        data = result["data"]
        assert data["overall_score"] == 81
        assert data["strengths"] == ["FastAPI backend experience"]
        assert data["missing_keywords"] == ["evaluation"]
        assert data["resume_id"] == resume_id
        assert data["job_posting_id"] == job_id

        # MatchResult row was actually persisted by the service.
        persisted = await db.get(MatchResult, data["match_id"])
        assert persisted is not None
        assert persisted.overall_score == 81

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        log = logs[0]
        assert log.status == "success"
        assert log.tool_name == "analyze_match"
        assert log.result_json is not None
        assert log.result_json["overall_score"] == 81
        assert log.latency_ms is not None

    _run_scenario(_scenario)


def test_match_analysis_tool_resume_not_found(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id, job_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        result = await MatchAnalysisTool().invoke(
            {"resume_id": 999_999_999, "job_posting_id": job_id},
            ctx,
        )

        assert result["ok"] is False
        assert result["error_class"] == "resume_not_found"
        assert "有效的 resume_id" in result["message_for_llm"]

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert logs[0].error_class == "resume_not_found"

    _run_scenario(_scenario)


def test_match_analysis_tool_resume_not_parsed(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db,
            marker=test_marker,
            resume_parsed=None,  # leave resume unparsed
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        result = await MatchAnalysisTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )

        assert result["ok"] is False
        assert result["error_class"] == "resume_not_parsed"

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].error_class == "resume_not_parsed"

    _run_scenario(_scenario)


def test_match_analysis_tool_llm_returns_invalid_json(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return "not json"

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        result = await MatchAnalysisTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )

        assert result["ok"] is False
        assert result["error_class"] == "llm_output_invalid"

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].error_class == "llm_output_invalid"

    _run_scenario(_scenario)


def test_match_analysis_tool_llm_config_missing_raises_system_error(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        with pytest.raises(ToolSystemError) as exc_info:
            await MatchAnalysisTool().invoke(
                {"resume_id": resume_id, "job_posting_id": job_id},
                ctx,
            )
        assert exc_info.value.error_class == "llm_config_missing"

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "failed"
        assert logs[0].error_class == "llm_config_missing"

    _run_scenario(_scenario)


def test_match_analysis_tool_rejects_invalid_args(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id, _job_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        from app.agent.tool_adapter import ToolValidationError

        with pytest.raises(ToolValidationError):
            await MatchAnalysisTool().invoke({"resume_id": "not_an_int"}, ctx)

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "failed"
        assert logs[0].error_class == "validation_error"

    _run_scenario(_scenario)
