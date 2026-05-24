"""DraftJobTool 集成测试。

draft_job 是组合工具:调 LLM、不落库。这里覆盖 text 路径成功、URL 路径成功、
URL 抓取失败转业务错、LLM 异常转 ToolSystemError、空输入转业务错。
"""

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext, ToolSystemError
from app.agent.tools.draft_job_tool import DraftJobTool
from app.core.config import settings
from app.llm.client import LLMClient, LLMClientError
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


_SAMPLE_HTML = """
<!doctype html>
<html lang="zh">
<head><meta charset="utf-8"><title>AI 应用研发工程师 · ExampleCo Careers</title></head>
<body>
  <main>
    <article>
      <h1>AI 应用研发工程师</h1>
      <p>ExampleCo 正在招募 AI 应用研发工程师,负责 RAG / Agent 工作流。</p>
      <h2>岗位职责</h2><ul><li>设计 Agent 工作流</li></ul>
      <h2>任职要求</h2><ul><li>3 年以上后端经验</li></ul>
    </article>
  </main>
</body>
</html>
"""


def _fake_llm_response() -> str:
    return json.dumps(
        {
            "company_name": "ExampleCo",
            "job_title": "AI 应用研发工程师",
            "city": "上海",
            "parsed": {
                "summary": "构建 RAG / Agent 工作流",
                "responsibilities": ["设计 Agent 工作流"],
                "required_skills": ["Python", "FastAPI"],
                "preferred_skills": [],
                "keywords": ["LLM", "RAG"],
                "seniority": "中级",
                "city": "上海",
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
    conversation = Conversation(user_id=user.id, title=f"{marker} draft-job conv")
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


def test_draft_job_tool_text_success(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        # 验证 prompt 确实带了文本片段,避免误把 hint 当成 jd_text。
        assert "ExampleCo" in prompt
        return _fake_llm_response()

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await DraftJobTool().invoke(
            {"text": "ExampleCo 招 AI 应用研发工程师,负责 Agent 工作流。"},
            ctx,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["company_name"] == "ExampleCo"
        assert data["job_title"] == "AI 应用研发工程师"
        assert data["city"] == "上海"
        assert data["source_url"] is None
        assert data["jd_text"].startswith("ExampleCo 招")
        # parsed_json 必须是 dict,便于 create_job 直接复用。
        assert isinstance(data["parsed_json"], dict)
        assert data["parsed_json"]["seniority"] == "中级"

        logs = await _fetch_logs(db, agent_run_id)
        assert len(logs) == 1
        assert logs[0].status == "success"
        assert logs[0].tool_name == "draft_job"

    _run(_scenario)


@respx.mock
def test_draft_job_tool_url_success(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    url = "https://careers.example.com/jobs/ai-engineer"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=_SAMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        ),
    )

    async def fake_llm(self, prompt: str) -> str:
        return _fake_llm_response()

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await DraftJobTool().invoke({"url": url}, ctx)
        assert result["ok"] is True, result
        data = result["data"]
        assert data["source_url"] == url
        # URL 模式下 jd_text 是 trafilatura 抓取出来的正文,应该包含主要描述。
        assert "ExampleCo" in data["jd_text"] or "AI 应用" in data["jd_text"]

    _run(_scenario)


@respx.mock
def test_draft_job_tool_url_fetch_failure_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    url = "https://careers.example.com/jobs/missing"
    respx.get(url).mock(return_value=httpx.Response(404, text="not found"))

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await DraftJobTool().invoke({"url": url}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "url_fetch_failed"
        # message_for_llm 应引导用户改用文本贴正文。
        assert "JD 文本" in result["message_for_llm"]

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "failed"
        assert logs[0].error_class == "url_fetch_failed"

    _run(_scenario)


def test_draft_job_tool_empty_input_returns_missing_required_field(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        # text 与 url 都为空 → 统一映射到 missing_required_field 业务错,
        # 让 LLM 转 respond_directly 向用户追问。
        result = await DraftJobTool().invoke({}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "missing_required_field"
        assert result["missing_fields"] == ["text_or_url"]
        # message 必须明确指引向用户追问。
        assert "respond_directly" in result["message_for_llm"]
        assert "JD 文本" in result["message_for_llm"]

    _run(_scenario)


def test_draft_job_tool_llm_failure_raises_system_error(
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
            await DraftJobTool().invoke({"text": "some JD"}, ctx)
        assert excinfo.value.error_class == "llm_unavailable"

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "failed"
        assert logs[0].error_class == "llm_unavailable"

    _run(_scenario)


def test_draft_job_tool_llm_returns_invalid_json_raises_system_error(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def fake_llm(self, prompt: str) -> str:
        return "not a valid json"

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_environment(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        with pytest.raises(ToolSystemError) as excinfo:
            await DraftJobTool().invoke({"text": "some JD"}, ctx)
        # service 层把坏 JSON 映射为 502,工具层转 llm_unavailable。
        assert excinfo.value.error_class == "llm_unavailable"

    _run(_scenario)


# 保险:DraftJobTool 必须出现在 TOOL_REGISTRY 里,否则 workflow 永远拿不到它。
def test_draft_job_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["draft_job"] is DraftJobTool


# 防御:声明的描述里必须显式提示先 respond_directly 给用户确认,避免 LLM 直接链到 create_job。
def test_draft_job_tool_description_mentions_confirm_step() -> None:
    assert "respond_directly" in DraftJobTool.description
    assert "create_job" in DraftJobTool.description


# 引用 Any 以避免 lint 报未使用,同时保留类型一致。
_: Any = None
