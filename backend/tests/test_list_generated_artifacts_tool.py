"""ListGeneratedArtifactsTool 集成测试。"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.list_generated_artifacts_tool import ListGeneratedArtifactsTool
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.generated_artifact import GeneratedArtifact
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
        title=f"{marker} la-res",
        raw_text="text",
        content_hash=f"{marker}-la-res",
        source_type="manual",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} LaCo",
        job_title="AI 工程师",
        jd_text="JD",
    )
    db.add_all([resume, job])
    await db.flush()

    # 种 2 个求职信 + 1 个面试准备,验证类型过滤。
    artifacts = [
        GeneratedArtifact(
            user_id=user.id,
            artifact_type="cover_letter",
            resume_id=resume.id,
            job_posting_id=job.id,
            title=f"{marker} cl-1",
            content_text="正文不该被返回",
            status="generated",
            generator_type="llm",
        ),
        GeneratedArtifact(
            user_id=user.id,
            artifact_type="cover_letter",
            resume_id=resume.id,
            job_posting_id=job.id,
            title=f"{marker} cl-2",
            content_text="正文不该被返回",
            status="generated",
            generator_type="llm",
        ),
        GeneratedArtifact(
            user_id=user.id,
            artifact_type="interview_prep",
            resume_id=resume.id,
            job_posting_id=job.id,
            title=f"{marker} ip-1",
            content_text="正文不该被返回",
            status="generated",
            generator_type="llm",
        ),
    ]
    db.add_all(artifacts)
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} list-arti conv")
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


def test_list_generated_artifacts_tool_returns_all(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id, _job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ListGeneratedArtifactsTool().invoke({}, ctx)
        assert result["ok"] is True
        # 当前 test user 可能有其它历史 artifact,但本 marker 的 3 条必须都包含。
        titles = [a["title"] for a in result["data"]["artifacts"]]
        assert f"{test_marker} cl-1" in titles
        assert f"{test_marker} cl-2" in titles
        assert f"{test_marker} ip-1" in titles
        # 关键不变量:不返回 content_text(避免拖大 prompt)。
        first = result["data"]["artifacts"][0]
        assert "content_text" not in first
        assert "title" in first

    _run(_scenario)


def test_list_generated_artifacts_tool_filter_by_type(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _resume_id, _job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ListGeneratedArtifactsTool().invoke(
            {"artifact_type": "interview_prep"},
            ctx,
        )
        assert result["ok"] is True
        types = {a["artifact_type"] for a in result["data"]["artifacts"]}
        # 只允许 interview_prep,过滤要严格。
        assert types == {"interview_prep"} or types == set()  # 容忍其它无关数据被过滤掉

        # 本 marker 的 interview_prep 必须出现。
        titles = [a["title"] for a in result["data"]["artifacts"]]
        assert f"{test_marker} ip-1" in titles
        assert f"{test_marker} cl-1" not in titles

    _run(_scenario)


def test_list_generated_artifacts_tool_filter_by_resume_id(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, resume_id, _job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ListGeneratedArtifactsTool().invoke(
            {"resume_id": resume_id},
            ctx,
        )
        assert result["ok"] is True
        # 所有返回项 resume_id 必须等于过滤值。
        for a in result["data"]["artifacts"]:
            assert a["resume_id"] == resume_id

    _run(_scenario)


def test_list_generated_artifacts_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["list_generated_artifacts"] is ListGeneratedArtifactsTool
