"""Verify that AssistantRunRequest.context flows into the decide prompt.

The hint is added as a labelled prefix to the workflow's user_text, so the
LLM sees something like:

    [当前上下文]
    - 简历:Backend Resume v2 (#7)
    - 岗位:腾讯 · 后端工程师 (#12)

    [用户问题]
    帮我分析匹配度

The persisted user message in the database keeps just the clean question so
the UI displays exactly what the user typed.
"""

import asyncio
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.llm.client import LLMClient
from app.models.job_posting import JobPosting
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.models.resume import Resume
from app.models.user import User


def _run(coro_factory: Callable[[AsyncSession], Any]) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


def test_context_hint_appears_in_decide_prompt(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """When the request carries context.resume_id + job_posting_id, the
    decide prompt receives a [当前上下文] section with the human-readable
    labels of both rows."""
    assert client.get("/health/db").status_code == 200

    # Seed a resume and a job under the test user.
    async def _seed(db: AsyncSession) -> tuple[int, int]:
        user = (
            await db.execute(select(User).where(User.username == "test"))
        ).scalar_one()
        resume = Resume(
            user_id=user.id,
            title=f"{test_marker} my-resume-title",
            raw_text="...",
            content_hash=f"{test_marker}-ch-rh",
        )
        job = JobPosting(
            user_id=user.id,
            company_name=f"{test_marker} HintCo",
            job_title="MyHintRole",
            jd_text="...",
        )
        db.add_all([resume, job])
        await db.commit()
        await db.refresh(resume)
        await db.refresh(job)
        return resume.id, job.id

    resume_id, job_id = _run(_seed)

    seen_prompts: list[str] = []

    async def fake_llm(self, prompt: str) -> str:
        seen_prompts.append(prompt)
        if "请严格按以下两种 JSON 之一回复" in prompt:
            return '{"action": "respond_directly", "text": "好的"}'
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    user_question = f"{test_marker} 帮我分析匹配度"
    response = client.post(
        "/api/v1/assistant/run",
        json={
            "content": user_question,
            "context": {
                "resume_id": resume_id,
                "job_posting_id": job_id,
            },
        },
    )
    assert response.status_code == 200, response.text

    decide_prompt = next(
        (p for p in seen_prompts if "请严格按以下两种 JSON 之一回复" in p),
        None,
    )
    assert decide_prompt is not None
    assert "[当前上下文]" in decide_prompt
    assert "my-resume-title" in decide_prompt
    assert f"#{resume_id}" in decide_prompt
    assert "HintCo" in decide_prompt
    assert "MyHintRole" in decide_prompt
    assert f"#{job_id}" in decide_prompt
    assert "[用户问题]" in decide_prompt
    # The original user question is still in the prompt (as the user-message
    # section), even with the hint prepended.
    assert user_question in decide_prompt

    # Persisted user message in DB is the original clean text — no hint.
    conversation_id = response.json()["conversation_id"]

    async def _verify(db: AsyncSession) -> None:
        user_msg = (
            await db.execute(
                select(Message).where(
                    Message.conversation_id == conversation_id,
                    Message.role == "user",
                ),
            )
        ).scalar_one()
        assert user_msg.content == user_question
        assert "[当前上下文]" not in user_msg.content

    _run(_verify)


def test_context_with_no_selection_produces_no_hint(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """An empty context object (or None) must not introduce a [当前上下文]
    block, so chat-only requests stay clean."""
    assert client.get("/health/db").status_code == 200

    seen_prompts: list[str] = []

    async def fake_llm(self, prompt: str) -> str:
        seen_prompts.append(prompt)
        if "请严格按以下两种 JSON 之一回复" in prompt:
            return '{"action": "respond_directly", "text": "好的"}'
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    response = client.post(
        "/api/v1/assistant/run",
        json={"content": f"{test_marker} 闲聊", "context": {}},
    )
    assert response.status_code == 200

    decide_prompt = next(
        (p for p in seen_prompts if "请严格按以下两种 JSON 之一回复" in p),
        None,
    )
    assert decide_prompt is not None
    assert "[当前上下文]" not in decide_prompt


def test_context_with_invalid_resume_id_silently_omits_hint(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """If the UI sends a resume_id that doesn't belong to this user (or no
    longer exists), we drop that line from the hint rather than failing."""
    assert client.get("/health/db").status_code == 200

    seen_prompts: list[str] = []

    async def fake_llm(self, prompt: str) -> str:
        seen_prompts.append(prompt)
        if "请严格按以下两种 JSON 之一回复" in prompt:
            return '{"action": "respond_directly", "text": "ok"}'
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    response = client.post(
        "/api/v1/assistant/run",
        json={
            "content": f"{test_marker} 测试无效 id",
            "context": {"resume_id": 999_999_999, "job_posting_id": 999_999_998},
        },
    )
    assert response.status_code == 200

    decide_prompt = next(
        (p for p in seen_prompts if "请严格按以下两种 JSON 之一回复" in p),
        None,
    )
    assert decide_prompt is not None
    # All resolutions failed → no context block at all.
    assert "[当前上下文]" not in decide_prompt


def test_context_hint_includes_selected_knowledge_base(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """A selected knowledge base should reach the decide prompt as a clear
    search_knowledge constraint while keeping the persisted message clean."""
    assert client.get("/health/db").status_code == 200

    async def _seed(db: AsyncSession) -> int:
        user = (
            await db.execute(select(User).where(User.username == "test"))
        ).scalar_one()
        kb = KnowledgeBase(
            user_id=user.id,
            name=f"{test_marker} 面试资料",
            description="context kb",
        )
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        return kb.id

    kb_id = _run(_seed)
    seen_prompts: list[str] = []

    async def fake_llm(self, prompt: str) -> str:
        seen_prompts.append(prompt)
        if "请严格按以下两种 JSON 之一回复" in prompt:
            return '{"action": "respond_directly", "text": "ok"}'
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    user_question = f"{test_marker} 查一下我保存的面试资料"
    response = client.post(
        "/api/v1/assistant/run",
        json={
            "content": user_question,
            "context": {"knowledge_base_id": kb_id},
        },
    )
    assert response.status_code == 200, response.text

    decide_prompt = next(
        (p for p in seen_prompts if "请严格按以下两种 JSON 之一回复" in p),
        None,
    )
    assert decide_prompt is not None
    assert "[当前上下文]" in decide_prompt
    assert "面试资料" in decide_prompt
    assert f"#{kb_id}" in decide_prompt
    assert "search_knowledge" in decide_prompt
    assert "knowledge_base_id" in decide_prompt
    assert user_question in decide_prompt
