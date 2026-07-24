"""远程 MCP 工具进入现有 ReAct 循环的端到端测试。"""

import asyncio
from typing import Any

from fastapi.testclient import TestClient
from mcp.types import CallToolResult, TextContent, Tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_catalog import ToolCatalog
from app.agent.workflow import build_workflow
from app.core.config import settings
from app.llm.client import LLMClient
from app.mcp.config import MCPRemoteServerConfig
from app.mcp.tool_provider import MCPToolProvider
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


class _FakeMCPManager:
    async def call_tool(self, config, tool_name, arguments):
        assert tool_name == "search_jobs"
        assert arguments["query"] == "Python"
        return CallToolResult(
            content=[TextContent(type="text", text="找到 Python 后端岗位")],
            structuredContent={
                "jobs": [
                    {
                        "id": "remote-1",
                        "company": "Example",
                        "title": "Python Engineer",
                    },
                ],
            },
            isError=False,
        )


def test_react_loop_can_call_namespaced_mcp_tool(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200
    calls = {"count": 0}

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON 之一回复" in prompt:
            calls["count"] += 1
            if calls["count"] == 1:
                assert "mcp__jobs__search_jobs" in prompt
                return (
                    '{"action":"call_tool","tool":"mcp__jobs__search_jobs",'
                    '"args":{"query":"Python"}}'
                )
            assert "Python Engineer" in prompt
            return '{"action":"respond_directly","text":"找到一个 Python 岗位。"}'
        raise AssertionError(f"unexpected prompt: {prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def scenario() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                user = (
                    await db.execute(select(User).where(User.username == "test"))
                ).scalar_one()
                conversation = Conversation(user_id=user.id, title=test_marker)
                db.add(conversation)
                await db.flush()
                run = AgentRun(
                    user_id=user.id,
                    conversation_id=conversation.id,
                    status="running",
                )
                db.add(run)
                await db.commit()
                await db.refresh(run)
                run_id = run.id

                config = MCPRemoteServerConfig(
                    id="jobs",
                    url="http://127.0.0.1:9100/mcp",
                    allowed_tools=["search_jobs"],
                    category="job_search",
                )
                provider = MCPToolProvider(
                    config,
                    _FakeMCPManager(),  # type: ignore[arg-type]
                    [
                        Tool(
                            name="search_jobs",
                            description="搜索外部岗位",
                            inputSchema={
                                "type": "object",
                                "properties": {"query": {"type": "string"}},
                                "required": ["query"],
                                "additionalProperties": False,
                            },
                        ),
                    ],
                )
                catalog = ToolCatalog.local_only()
                catalog.add_mcp_provider(provider)
                graph = build_workflow(
                    db=db,
                    current_user=user,
                    agent_run_id=run_id,
                    tool_catalog=catalog,
                )
                final = await graph.ainvoke(
                    {
                        "user_id": user.id,
                        "conversation_id": conversation.id,
                        "user_message_id": 0,
                        "user_text": "帮我搜索 Python 岗位",
                        "agent_run_id": run_id,
                        "conversation_history": [],
                        "existing_summary": None,
                        "message_count_before_user": 0,
                        "decide_repair_attempts": 0,
                        "iteration_count": 0,
                        "tool_call_history": [],
                    },
                )
                assert final["final_text"] == "找到一个 Python 岗位。"
                logs = list(
                    (
                        await db.execute(
                            select(ToolCallLog).where(
                                ToolCallLog.agent_run_id == run_id,
                            ),
                        )
                    ).scalars(),
                )
                assert len(logs) == 1
                assert logs[0].tool_name == "mcp__jobs__search_jobs"
                assert logs[0].source == "assistant"
                assert logs[0].status == "success"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
