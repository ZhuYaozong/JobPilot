"""Assistant mock-interview mode tests.

The mock interview is intentionally built on the existing Assistant ReAct loop
rather than a separate interview-session table. These tests pin the two core
contracts: the mode reaches the decide prompt, and a prepared run can chain
match analysis, interview prep, and knowledge search before asking one
interactive question.
"""

import asyncio
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.llm.client import LLMClient
from app.llm.embedding_client import EmbeddingClient
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


_PARSED_RESUME: dict[str, Any] = {
    "summary": "Backend engineer with AI workflow experience.",
    "skills": ["FastAPI", "LangGraph", "PostgreSQL"],
    "experiences": [],
    "projects": ["JobPilot"],
    "education": [],
    "target_roles": ["AI Application Engineer"],
    "years_of_experience": "3 years",
}

_PARSED_JOB: dict[str, Any] = {
    "summary": "Build AI workflow applications.",
    "responsibilities": ["Design agent workflows", "Ship backend APIs"],
    "required_skills": ["FastAPI", "RAG", "PostgreSQL"],
    "preferred_skills": ["LangGraph"],
    "keywords": ["agent", "retrieval"],
    "seniority": "mid",
    "city": "Shanghai",
}

_MATCH_LLM_JSON = (
    '{"overall_score": 88, "strengths": ["FastAPI", "LangGraph"],'
    ' "weaknesses": ["RAG evaluation"], "missing_keywords": ["hybrid retrieval"],'
    ' "suggestions": ["Prepare concrete RAG tradeoff examples"]}'
)


def _run(coro_factory: Callable[[AsyncSession], Any]) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


def _vec(axis: int = 0) -> list[float]:
    vector = [0.0] * settings.embedding_dimensions
    vector[axis] = 1.0
    return vector


async def _seed_resume_job_kb(
    db: AsyncSession,
    marker: str,
) -> tuple[int, int, int]:
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    resume = Resume(
        user_id=user.id,
        title=f"{marker} mock resume",
        raw_text="FastAPI, LangGraph, RAG.",
        parsed_json=_PARSED_RESUME,
        parse_status="parsed",
        content_hash=f"{marker[:40]}-mock-resume",
        source_type="manual",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} InterviewCo",
        job_title="AI Application Engineer",
        city="Shanghai",
        jd_text="Build agentic workflow applications with RAG.",
        parsed_json=_PARSED_JOB,
    )
    kb = KnowledgeBase(
        user_id=user.id,
        name=f"{marker} 面试知识库",
        description="mock interview notes",
    )
    db.add_all([resume, job, kb])
    await db.flush()

    doc = KnowledgeDocument(
        knowledge_base_id=kb.id,
        user_id=user.id,
        title=f"{marker} 面试笔记",
        source_type="manual",
        raw_text="面试官喜欢追问 RAG 的召回率、引用溯源和失败兜底。",
        content_hash=f"{marker[:40]}-mock-kb-doc",
        status="ready",
        chunk_count=1,
    )
    db.add(doc)
    await db.flush()
    db.add(
        KnowledgeChunk(
            document_id=doc.id,
            user_id=user.id,
            chunk_index=0,
            content="面试官喜欢追问 RAG 的召回率、引用溯源和失败兜底。",
            embedding=_vec(0),
            char_start=0,
            char_end=28,
        ),
    )
    await db.commit()
    return resume.id, job.id, kb.id


def test_mock_interview_mode_without_resume_or_job_asks_for_context(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    seen_prompts: list[str] = []

    async def fake_llm(self, prompt: str) -> str:
        seen_prompts.append(prompt)
        if "请严格按以下两种 JSON 之一回复" in prompt:
            return (
                '{"action": "respond_directly", '
                '"text": "开始模拟面试前,请先在右侧选择一份简历和一个岗位。"}'
            )
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    response = client.post(
        "/api/v1/assistant/run",
        json={
            "content": f"{test_marker} 开始模拟面试",
            "context": {"assistant_mode": "mock_interview"},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agent_run"]["intent"] == "mock_interview"
    assert body["agent_run"]["tool_calls"] == []
    assert "选择一份简历和一个岗位" in body["assistant_message"]["content"]

    decide_prompt = next(
        prompt for prompt in seen_prompts if "请严格按以下两种 JSON 之一回复" in prompt
    )
    assert "模式:模拟面试" in decide_prompt
    assert "每轮只问一个问题" in decide_prompt


def test_mock_interview_can_chain_match_prep_and_knowledge_search(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    resume_id, job_id, kb_id = _run(
        lambda db: _seed_resume_job_kb(db, test_marker),
    )

    async def fake_embed(self: EmbeddingClient, texts: list[str]) -> list[list[float]]:
        assert texts == ["RAG 面试追问"]
        return [_vec(0)]

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)

    seen_decide_prompts: list[str] = []

    async def fake_llm(self, prompt: str) -> str:
        if "请比较结构化简历" in prompt:
            return _MATCH_LLM_JSON
        if "生成一份简洁的中文面试准备提纲" in prompt:
            return (
                "岗位核心考察点:Agent workflow 与 RAG 落地。\n"
                "可能问题:你如何设计知识库检索的失败兜底？\n"
                "准备建议:用 JobPilot 的 search_knowledge 例子回答。"
            )
        if "请严格按以下两种 JSON 之一回复" in prompt:
            seen_decide_prompts.append(prompt)
            if "(本轮还没有调用过工具)" in prompt:
                return (
                    '{"action": "call_tool", "tool": "analyze_match", '
                    f'"args": {{"resume_id": {resume_id}, "job_posting_id": {job_id}}}}}'
                )
            if "工具: analyze_match" in prompt and "工具: generate_interview_prep" not in prompt:
                return (
                    '{"action": "call_tool", "tool": "generate_interview_prep", '
                    f'"args": {{"resume_id": {resume_id}, "job_posting_id": {job_id}}}}}'
                )
            if "工具: generate_interview_prep" in prompt and "工具: search_knowledge" not in prompt:
                return (
                    '{"action": "call_tool", "tool": "search_knowledge", '
                    '"args": {"query": "RAG 面试追问", "top_k": 3}}'
                )
            if "工具: search_knowledge" in prompt:
                return (
                    '{"action": "respond_directly", '
                    '"text": "我们开始。请你先回答:如果知识库检索没有命中,你会怎样设计兜底策略？"}'
                )
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    response = client.post(
        "/api/v1/assistant/run",
        json={
            "content": f"{test_marker} 基于当前上下文开始模拟面试",
            "context": {
                "assistant_mode": "mock_interview",
                "resume_id": resume_id,
                "job_posting_id": job_id,
                "knowledge_base_id": kb_id,
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agent_run"]["status"] == "succeeded"
    assert body["agent_run"]["intent"] == "mock_interview"
    assert "如果知识库检索没有命中" in body["assistant_message"]["content"]

    tool_names = [call["tool_name"] for call in body["agent_run"]["tool_calls"]]
    assert tool_names == [
        "analyze_match",
        "generate_interview_prep",
        "search_knowledge",
    ]

    async def _read_search_log(db: AsyncSession) -> ToolCallLog:
        return (
            await db.execute(
                select(ToolCallLog)
                .where(ToolCallLog.agent_run_id == body["agent_run"]["id"])
                .where(ToolCallLog.tool_name == "search_knowledge"),
            )
        ).scalar_one()

    search_log = _run(_read_search_log)
    assert search_log.arguments_json["knowledge_base_id"] == kb_id
    assert search_log.result_json["knowledge_base_id"] == kb_id
    assert search_log.result_json["hits"][0]["document_title"].endswith("面试笔记")

    final_decide_prompt = seen_decide_prompts[-1]
    assert "模式:模拟面试" in final_decide_prompt
    assert "只提出 1 个问题" in final_decide_prompt
