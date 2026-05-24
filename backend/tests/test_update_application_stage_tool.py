"""UpdateApplicationStageTool 集成测试。

验证 stage 流转、ApplicationEvent 事件落库,以及 operator_type=assistant 的强制写入。
"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.update_application_stage_tool import UpdateApplicationStageTool
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.application_event import ApplicationEvent
from app.models.application_record import ApplicationRecord
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.models.user import User


async def _setup(
    db: AsyncSession,
    *,
    marker: str,
    initial_stage: str = "saved",
) -> tuple[User, int, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    resume = Resume(
        user_id=user.id,
        title=f"{marker} upd-res",
        raw_text="text",
        content_hash=f"{marker}-upd-res",
        source_type="manual",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} UpdCo",
        job_title="AI 应用研发工程师",
        jd_text="JD",
    )
    db.add_all([resume, job])
    await db.flush()

    application = ApplicationRecord(
        user_id=user.id,
        resume_id=resume.id,
        job_posting_id=job.id,
        current_stage=initial_stage,
    )
    db.add(application)
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} upd-app conv")
    db.add(conversation)
    await db.flush()
    agent_run = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(application)
    await db.refresh(agent_run)
    return user, agent_run.id, application.id


def _run(coro_factory) -> None:
    async def _do():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await coro_factory(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


def test_update_application_stage_tool_happy_path(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, application_id = await _setup(
            db, marker=test_marker, initial_stage="saved",
        )
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await UpdateApplicationStageTool().invoke(
            {
                "application_id": application_id,
                "target_stage": "applied",
                "next_action": "等待初筛",
                "note": "今天投递了",
            },
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["application_id"] == application_id
        assert data["current_stage"] == "applied"
        assert data["next_action"] == "等待初筛"

        # 投递主记录已更新。
        rows = await db.execute(
            select(ApplicationRecord).where(ApplicationRecord.id == application_id),
        )
        app = rows.scalar_one()
        assert app.current_stage == "applied"

        # 事件已写入,operator_type 必须是 assistant(强约束)。
        events = (
            await db.execute(
                select(ApplicationEvent).where(
                    ApplicationEvent.application_record_id == application_id,
                ),
            )
        ).scalars().all()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "stage_changed"
        assert event.from_stage == "saved"
        assert event.to_stage == "applied"
        assert event.operator_type == "assistant"
        assert event.note == "今天投递了"

    _run(_scenario)


def test_update_application_stage_tool_not_found(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _application_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await UpdateApplicationStageTool().invoke(
            {"application_id": 999_999_999, "target_stage": "applied"},
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "application_record_not_found"

    _run(_scenario)


def test_update_application_stage_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["update_application_stage"] is UpdateApplicationStageTool
