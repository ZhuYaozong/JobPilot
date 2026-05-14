"""CoverLetterTool 集成测试。

底层 service 会通过 monkeypatched LLM 端到端执行。这里断言每个业务失败都会变成带正确 ``error_class`` 的
``ok=False`` 响应，而基础设施失败会冒泡为 ``ToolSystemError``。
"""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext, ToolSystemError
from app.agent.tools.cover_letter_tool import CoverLetterTool
from app.core.config import settings
from app.llm.client import LLMClient, LLMConfigError
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

_FAKE_COVER_LETTER_ZH = "尊敬的招聘团队：您好！我希望申请 AI Application Engineer 岗位..."


async def _setup_environment(
    db: AsyncSession,
    *,
    marker: str,
    with_match: bool = True,
    resume_parsed: dict[str, Any] | None = _PARSED_RESUME,
) -> tuple[User, int, int, int, int | None]:
    """返回 user、agent_run_id、resume_id、job_id，以及可选 match_id。"""
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()

    resume = Resume(
        user_id=user.id,
        title=f"{marker} cl resume",
        raw_text="FastAPI experience.",
        content_hash=f"{marker}-cl-res",
        source_type="manual",
        parsed_json=resume_parsed,
        parse_status="parsed" if resume_parsed is not None else "pending",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} cl company",
        job_title="AI Application Engineer",
        city="Shanghai",
        jd_text="Build AI workflow apps.",
        parsed_json=_PARSED_JOB,
    )
    db.add(resume)
    db.add(job)
    await db.flush()

    match_id: int | None = None
    if with_match:
        match = MatchResult(
            user_id=user.id,
            resume_id=resume.id,
            job_posting_id=job.id,
            overall_score=82.0,
            strengths=["FastAPI"],
            weaknesses=[],
            missing_keywords=[],
            suggestions=[],
        )
        db.add(match)
        await db.flush()
        match_id = match.id

    conversation = Conversation(user_id=user.id, title=f"{marker} cl conversation")
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
    return user, agent_run.id, resume.id, job.id, match_id


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


def test_cover_letter_tool_happy_path(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return _FAKE_COVER_LETTER_ZH

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id, _match_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CoverLetterTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["artifact_type"] == "cover_letter"
        assert "招聘团队" in data["content_text"]
        assert data["resume_id"] == resume_id
        assert data["job_posting_id"] == job_id

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "success"
        assert logs[0].tool_name == "generate_cover_letter"

    _run(_scenario)


def test_cover_letter_tool_missing_match_returns_business_error(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id, _match_id = await _setup_environment(
            db, marker=test_marker, with_match=False,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CoverLetterTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "match_result_missing"
        assert "analyze_match" in result["message_for_llm"]

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].error_class == "match_result_missing"

    _run(_scenario)


def test_cover_letter_tool_unsupported_language_mode(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id, _match_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        # Pydantic args_schema 只接受 "zh" | "bilingual"，因此 adapter 会在 _execute 运行前抛参数校验错误。
        from app.agent.tool_adapter import ToolValidationError

        with pytest.raises(ToolValidationError):
            await CoverLetterTool().invoke(
                {
                    "resume_id": resume_id,
                    "job_posting_id": job_id,
                    "language_mode": "en",
                },
                ctx,
            )

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "failed"
        assert logs[0].error_class == "validation_error"

    _run(_scenario)


def test_cover_letter_tool_llm_config_missing_raises_system_error(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def broken(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", broken)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id, _match_id = await _setup_environment(
            db, marker=test_marker,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)

        with pytest.raises(ToolSystemError) as exc_info:
            await CoverLetterTool().invoke(
                {"resume_id": resume_id, "job_posting_id": job_id},
                ctx,
            )
        assert exc_info.value.error_class == "llm_config_missing"

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "failed"
        assert logs[0].error_class == "llm_config_missing"

    _run(_scenario)


def test_cover_letter_tool_resume_not_parsed(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id, _match_id = await _setup_environment(
            db, marker=test_marker, resume_parsed=None, with_match=False,
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CoverLetterTool().invoke(
            {"resume_id": resume_id, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "resume_not_parsed"

    _run(_scenario)
