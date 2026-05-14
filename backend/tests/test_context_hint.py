"""验证 AssistantRunRequest.context 会进入 decide prompt。

上下文提示会作为带标签的前缀拼到 workflow 的 user_text 前面，因此 LLM 会看到类似：

    [当前上下文]
    - 简历:Backend Resume v2 (#7)
    - 岗位:腾讯 · 后端工程师 (#12)

    [用户问题]
    帮我分析匹配度

数据库中持久化的用户消息只保留干净问题，确保 UI 展示的就是用户实际输入。
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
    """请求携带 context.resume_id + job_posting_id 时，decide prompt 应带上可读上下文。"""
    assert client.get("/health/db").status_code == 200

    # 在 test 用户下预置一份简历和一个岗位。
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
    # 即使前面拼了上下文提示，原始用户问题仍应出现在 prompt 的用户问题区段里。
    assert user_question in decide_prompt

    # DB 中持久化的用户消息仍是原始干净文本，不包含上下文提示。
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
    """空 context 对象（或 None）不应引入 [当前上下文] 块，保持纯聊天请求干净。"""
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
    """UI 传入无权访问或不存在的 resume_id 时，应静默丢弃该上下文行而不是失败。"""
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
    # 所有上下文解析都失败时，不应生成上下文块。
    assert "[当前上下文]" not in decide_prompt


def test_context_hint_includes_selected_knowledge_base(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """选中的知识库应进入 decide prompt 作为清晰检索约束，同时保持持久化消息干净。"""
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
