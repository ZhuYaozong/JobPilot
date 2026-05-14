"""Eval case 的种子数据 helper。

每个 ``seed_*`` 函数对应 :class:`SeedSpec` 的一种 ``kind``,返回新建资源的
主键 id。Runner 把这个 id 写进 ``ref_context`` 后,后续的 setup 条目和
assertions 就能通过占位符引用。

设计取舍:
- 直接走 ORM 落库,不走 HTTP API。原因:case 想种"已经 indexed 完成"的
  KnowledgeChunk(带向量),走 HTTP 会触发真嵌入调用,成本不可控
- 用一个 marker(uuid 后缀)嵌进所有标题 / content_hash,保证多次 eval
  跑共用一个测试 DB 时不会撞键
- 所有种子用户固定取 username='test',跟 ``backend/tests/conftest.py``
  的约定一致 —— eval 不引入新 dev user
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.fake_llm import fake_embedding
from app.models.application_record import ApplicationRecord
from app.models.job_posting import JobPosting
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.resume import Resume
from app.models.user import User


async def resolve_test_user(db: AsyncSession) -> User:
    """所有 case 都共用 test 用户;不存在时由 deps 自动创建,这里只 select。

    我们不在 eval 框架里自动 create_or_get;假设运行环境至少跑过一次 API
    或 conftest,数据库里已经有 test 用户。失败抛出能立即提示作者去 init。
    """
    row = await db.execute(select(User).where(User.username == "test"))
    user = row.scalar_one_or_none()
    if user is None:
        raise RuntimeError(
            "测试 DB 里没有 username='test' 用户。"
            "先在 backend 跑一次 pytest 或调一次 API 让 deps 自动建。",
        )
    return user


# ---------- 各 kind 的种子函数 ---------------------------------------------


async def seed_knowledge_base(
    db: AsyncSession,
    user: User,
    *,
    marker: str,
    name: str = "公司资料",
    description: str | None = None,
) -> int:
    """种一个空知识库。"""
    kb = KnowledgeBase(
        user_id=user.id,
        name=f"{marker} {name}",
        description=description,
        status="active",
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb.id


async def seed_knowledge_document(
    db: AsyncSession,
    user: User,
    *,
    marker: str,
    kb_id: int,
    title: str,
    body: str,
    embedding: list[float] | None = None,
    chunk_index: int = 0,
) -> int:
    """种一份"已经 indexed"的知识库文档 + 1 个 chunk。

    向量默认全 0(便于 fake 检索的 deterministic 排序;真实场景下嵌入服务
    生成,这里我们模拟最终状态)。如果作者要测排序,可显式传 ``embedding``。
    """
    content_hash = hashlib.sha256(
        f"{marker}-{title}-{body}".encode("utf-8"),
    ).hexdigest()
    doc = KnowledgeDocument(
        knowledge_base_id=kb_id,
        user_id=user.id,
        title=title,
        source_type="manual",
        raw_text=body,
        content_hash=content_hash,
        chunk_count=1,
        status="ready",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    chunk = KnowledgeChunk(
        document_id=doc.id,
        user_id=user.id,
        chunk_index=chunk_index,
        content=body,
        # 用 hash-based 向量(:func:`fake_embedding`)而不是全 0;后者会让
        # pgvector 的 cosine_distance 出现 NaN,top-K 查询乱序。
        # 案例作者想测排序时仍可显式传 ``embedding``。
        embedding=list(embedding) if embedding is not None
        else fake_embedding(body, _embedding_dim()),
        char_start=0,
        char_end=len(body),
    )
    db.add(chunk)
    await db.commit()
    await db.refresh(doc)
    return doc.id


async def seed_resume(
    db: AsyncSession,
    user: User,
    *,
    marker: str,
    title: str = "通用简历",
    raw_text: str = "FastAPI, SQLAlchemy async, PostgreSQL。",
    parsed_json: dict[str, Any] | None = None,
) -> int:
    """种一份简历(可选已解析)。"""
    resume = Resume(
        user_id=user.id,
        title=f"{marker} {title}",
        raw_text=raw_text,
        content_hash=hashlib.sha256(f"{marker}-{title}-{raw_text}".encode("utf-8")).hexdigest(),
        source_type="manual",
        parse_status="parsed" if parsed_json else "pending",
        parsed_json=parsed_json,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume.id


async def seed_job(
    db: AsyncSession,
    user: User,
    *,
    marker: str,
    company_name: str = "腾讯",
    job_title: str = "AI 应用工程师",
    city: str = "深圳",
    jd_text: str = "构建基于 LangGraph 的工作流应用。",
    parsed_json: dict[str, Any] | None = None,
) -> int:
    """种一个岗位(可选已解析)。"""
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} {company_name}",
        job_title=job_title,
        city=city,
        jd_text=jd_text,
        parsed_json=parsed_json,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job.id


async def seed_application(
    db: AsyncSession,
    user: User,
    *,
    resume_id: int,
    job_posting_id: int,
    current_stage: str = "saved",
    next_action: str | None = "看 JD",
) -> int:
    app = ApplicationRecord(
        user_id=user.id,
        resume_id=resume_id,
        job_posting_id=job_posting_id,
        current_stage=current_stage,
        next_action=next_action,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app.id


# ---------- dispatch -------------------------------------------------------


# 各 kind 的种子函数注册表 —— runner 调用时按 kind 找到对应函数。
# 每个种子函数接受 ``(db, user, *, marker, **params)``,返回新资源 id。
SEEDERS = {
    "knowledge_base": seed_knowledge_base,
    "knowledge_document": seed_knowledge_document,
    "resume": seed_resume,
    "job": seed_job,
    "application": seed_application,
}


def new_marker() -> str:
    """为一次 case run 生成稳定的隔离标识符。"""
    return f"eval-{uuid4().hex[:16]}"


def _embedding_dim() -> int:
    """读 settings.embedding_dimensions,延迟到调用时,避免 import-time 触发。"""
    from app.core.config import settings

    return int(settings.embedding_dimensions)
