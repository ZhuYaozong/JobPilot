"""CreateApplicationTool 集成测试。"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.create_application_tool import CreateApplicationTool
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.application_record import ApplicationRecord
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.models.user import User


async def _setup(
    db: AsyncSession,
    *,
    marker: str,
) -> tuple[User, int, int, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    resume = Resume(
        user_id=user.id,
        title=f"{marker} app-res",
        raw_text="text",
        content_hash=f"{marker}-app-res",
        source_type="manual",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} AppCo",
        job_title="AI 应用研发工程师",
        city="上海",
        jd_text="JD",
    )
    db.add_all([resume, job])
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} create-app conv")
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


def _run(coro_factory) -> None:
    async def _do():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await coro_factory(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


def test_create_application_tool_happy_path(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, job_id = await _setup(db, marker=test_marker)
        user_id = user.id
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CreateApplicationTool().invoke(
            {
                "resume_id": resume_id,
                "job_posting_id": job_id,
                "current_stage": "applied",
                "next_action": "等待初筛反馈",
            },
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["resume_id"] == resume_id
        assert data["job_posting_id"] == job_id
        assert data["current_stage"] == "applied"
        assert data["next_action"] == "等待初筛反馈"

        rows = await db.execute(
            select(ApplicationRecord).where(
                ApplicationRecord.id == data["application_id"],
            ),
        )
        app = rows.scalar_one()
        assert app.user_id == user_id
        assert app.current_stage == "applied"

    _run(_scenario)


def test_create_application_tool_resume_not_found(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id, job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CreateApplicationTool().invoke(
            {"resume_id": 999_999_999, "job_posting_id": job_id},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "resume_not_found"

    _run(_scenario)


def test_create_application_tool_job_not_found(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, _job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CreateApplicationTool().invoke(
            {"resume_id": resume_id, "job_posting_id": 999_999_999},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "job_posting_not_found"

    _run(_scenario)


def test_create_application_tool_missing_ids_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    """缺 resume_id / job_posting_id → 业务错 missing_required_field,
    引导 LLM 先 list_user_* 查 id 或追问用户。
    """
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id, _job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CreateApplicationTool().invoke({}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "missing_required_field"
        assert set(result["missing_fields"]) == {"resume_id", "job_posting_id"}
        assert "list_user_resumes" in result["message_for_llm"]

    _run(_scenario)


def test_create_application_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["create_application"] is CreateApplicationTool
