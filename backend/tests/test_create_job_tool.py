"""CreateJobTool 集成测试。

create_job 不调 LLM,只做落库。覆盖:基础字段落库;带 parsed_json 时 parse_status=parsed。
"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.create_job_tool import CreateJobTool
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


async def _setup_environment(
    db: AsyncSession,
    *,
    marker: str,
) -> tuple[User, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} create-job conv")
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
    return user, agent_run.id


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
    result = await db.execute(
        select(ToolCallLog)
        .where(ToolCallLog.agent_run_id == agent_run_id)
        .order_by(ToolCallLog.id),
    )
    return list(result.scalars().all())


def test_create_job_tool_basic_fields(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        # 工具内部 commit 会让 user ORM 实例过期;预先取 id 避免后续访问触发 lazy load。
        user_id = user.id
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CreateJobTool().invoke(
            {
                "company_name": f"{test_marker} CreateCo",
                "job_title": "AI 应用研发工程师",
                "jd_text": "招聘 AI 应用研发工程师,负责 Agent 工作流。",
                "city": "上海",
            },
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["company_name"] == f"{test_marker} CreateCo"
        assert data["job_title"] == "AI 应用研发工程师"
        assert data["city"] == "上海"
        # 不带 parsed_json → parse_status 走数据库默认 pending。
        assert data["parse_status"] == "pending"

        # 数据库里确实有这一行。
        rows = await db.execute(
            select(JobPosting).where(JobPosting.id == data["job_posting_id"]),
        )
        job = rows.scalar_one()
        assert job.user_id == user_id
        # JobPosting 模型没有 parse_status 列;通过 parsed_json 是否为空推断,
        # 与 list_user_jobs_tool 保持一致。
        assert job.parsed_json is None

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "success"
        assert logs[0].tool_name == "create_job"

    _run(_scenario)


def test_create_job_tool_with_parsed_json_marks_parsed(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        parsed_payload = {
            "summary": "AI 应用研发",
            "responsibilities": ["设计 Agent 工作流"],
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": [],
            "keywords": ["LLM"],
            "seniority": "中级",
            "city": "上海",
        }
        result = await CreateJobTool().invoke(
            {
                "company_name": f"{test_marker} ParsedCo",
                "job_title": "AI 应用研发工程师",
                "jd_text": "招聘 AI 应用研发工程师。",
                "city": "上海",
                "source_url": "https://careers.example.com/jobs/1",
                "parsed_json": parsed_payload,
            },
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        # parsed_json 一并落库 → parse_status 应升级为 parsed。
        assert data["parse_status"] == "parsed"

        rows = await db.execute(
            select(JobPosting).where(JobPosting.id == data["job_posting_id"]),
        )
        job = rows.scalar_one()
        assert job.parsed_json == parsed_payload
        assert job.source_url == "https://careers.example.com/jobs/1"

    _run(_scenario)


def test_create_job_tool_missing_required_fields_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    """缺 jd_text / company_name / job_title → 业务错 missing_required_field,
    不再抛 ValidationError。
    """
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        # 全空调用
        result = await CreateJobTool().invoke({}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "missing_required_field"
        assert set(result["missing_fields"]) == {
            "company_name",
            "job_title",
            "jd_text",
        }
        # message 必须指引 LLM 用 respond_directly 追问用户。
        assert "respond_directly" in result["message_for_llm"]
        # 字段中文名应出现在 message 里,方便 format_response 转自然语言。
        assert "JD 正文" in result["message_for_llm"]

        # 只缺 jd_text
        result = await CreateJobTool().invoke(
            {
                "company_name": f"{test_marker} Co",
                "job_title": "AI 应用研发工程师",
            },
            ctx,
        )
        assert result["ok"] is False
        assert result["error_class"] == "missing_required_field"
        assert result["missing_fields"] == ["jd_text"]

    _run(_scenario)


def test_create_job_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["create_job"] is CreateJobTool
