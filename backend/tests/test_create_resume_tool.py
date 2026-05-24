"""CreateResumeTool 集成测试。"""

import asyncio
import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.create_resume_tool import CreateResumeTool
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.resume import Resume
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


async def _setup_environment(
    db: AsyncSession,
    *,
    marker: str,
) -> tuple[User, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} create-resume conv")
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


def test_create_resume_tool_basic_fields_compute_content_hash(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    raw_text = f"{test_marker} 张三 简历:Python / FastAPI / LangGraph。"

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        # 工具内部 commit 会过期 user ORM 实例;预取 id 避免 lazy load。
        user_id = user.id
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CreateResumeTool().invoke(
            {
                "title": f"{test_marker} 张三 简历",
                "raw_text": raw_text,
            },
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["title"] == f"{test_marker} 张三 简历"
        # 不带 parsed_json 时 parse_status 走默认 pending。
        assert data["parse_status"] == "pending"
        assert data["source_type"] == "manual"

        rows = await db.execute(
            select(Resume).where(Resume.id == data["resume_id"]),
        )
        resume = rows.scalar_one()
        assert resume.user_id == user_id
        # 服务端必须按 raw_text 计算 sha256,与 /resumes/upload 行为一致。
        expected_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        assert resume.content_hash == expected_hash
        assert resume.parsed_json is None
        assert resume.parse_status == "pending"

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "success"
        assert logs[0].tool_name == "create_resume"

    _run(_scenario)


def test_create_resume_tool_with_parsed_json_marks_parsed(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    parsed_payload = {
        "summary": "3 年 AI 应用研发经验",
        "skills": ["Python", "FastAPI", "LangGraph"],
        "experiences": ["在某公司搭建 RAG"],
        "projects": ["JobPilot"],
        "education": [],
        "target_roles": ["AI 应用工程师"],
        "years_of_experience": "3 年",
    }

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await CreateResumeTool().invoke(
            {
                "title": f"{test_marker} 张三 AI 简历",
                "raw_text": f"{test_marker} 简历正文。",
                "parsed_json": parsed_payload,
            },
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        # 带 parsed_json → parse_status 升级为 parsed。
        assert data["parse_status"] == "parsed"

        rows = await db.execute(
            select(Resume).where(Resume.id == data["resume_id"]),
        )
        resume = rows.scalar_one()
        assert resume.parsed_json == parsed_payload

    _run(_scenario)


def test_create_resume_tool_missing_required_fields_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    """缺 title / raw_text → 业务错 missing_required_field,不再抛 ValidationError。"""
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        # 全空
        result = await CreateResumeTool().invoke({}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "missing_required_field"
        assert set(result["missing_fields"]) == {"title", "raw_text"}
        assert "respond_directly" in result["message_for_llm"]
        assert "简历正文" in result["message_for_llm"]

        # 只缺 raw_text
        result = await CreateResumeTool().invoke(
            {"title": f"{test_marker} t"},
            ctx,
        )
        assert result["ok"] is False
        assert result["missing_fields"] == ["raw_text"]

    _run(_scenario)


def test_create_resume_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["create_resume"] is CreateResumeTool
