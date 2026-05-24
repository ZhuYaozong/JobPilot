"""DraftResumeTool 集成测试。"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext, ToolSystemError, ToolValidationError
from app.agent.tools.draft_resume_tool import DraftResumeTool
from app.core.config import settings
from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


def _fake_llm_response() -> str:
    return json.dumps(
        {
            "title": "张三 AI 应用研发简历",
            "parsed": {
                "summary": "三年 AI 应用研发经验",
                "skills": ["Python", "FastAPI", "LangGraph"],
                "experiences": ["在某公司搭建 RAG 系统"],
                "projects": ["JobPilot"],
                "education": ["计算机本科"],
                "target_roles": ["AI 应用工程师"],
                "years_of_experience": "3 年",
            },
        },
        ensure_ascii=False,
    )


async def _setup_environment(
    db: AsyncSession,
    *,
    marker: str,
) -> tuple[User, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} draft-resume conv")
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


def test_draft_resume_tool_text_success(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return _fake_llm_response()

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await DraftResumeTool().invoke(
            {"text": "张三,3 年 AI 应用研发经验,熟悉 Python / FastAPI / LangGraph。"},
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["title"] == "张三 AI 应用研发简历"
        assert data["raw_text"].startswith("张三")
        assert isinstance(data["parsed_json"], dict)
        assert "Python" in data["parsed_json"]["skills"]

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "success"
        assert logs[0].tool_name == "draft_resume"

    _run(_scenario)


def test_draft_resume_tool_empty_text_raises_validation_error(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        # text=空串 走 Pydantic min_length=1 → ToolValidationError(由 tool_adapter 统一抛)。
        with pytest.raises(ToolValidationError):
            await DraftResumeTool().invoke({"text": ""}, ctx)

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "failed"
        assert logs[0].error_class == "validation_error"

    _run(_scenario)


def test_draft_resume_tool_llm_failure_raises_system_error(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        raise LLMClientError("upstream timeout")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        with pytest.raises(ToolSystemError) as excinfo:
            await DraftResumeTool().invoke(
                {"text": "张三 简历文本"},
                ctx,
            )
        assert excinfo.value.error_class == "llm_unavailable"

    _run(_scenario)


def test_draft_resume_tool_llm_config_missing_raises_system_error(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        raise LLMConfigError("missing OPENAI_API_KEY")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        with pytest.raises(ToolSystemError) as excinfo:
            await DraftResumeTool().invoke(
                {"text": "张三 简历文本"},
                ctx,
            )
        # 500 → llm_config_missing。
        assert excinfo.value.error_class == "llm_config_missing"

    _run(_scenario)


def test_draft_resume_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["draft_resume"] is DraftResumeTool
