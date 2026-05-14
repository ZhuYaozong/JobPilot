import asyncio
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.main import app
from app.models.job_posting import JobPosting
from app.models.resume import Resume


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        test_client.headers.update({"X-User-Name": "test"})
        yield test_client


def _run_with_fresh_engine(work: Callable[[AsyncSession], Any]) -> None:
    # TestClient 会在各自的事件循环里驱动每个请求，而全局 async engine 会把 asyncpg
    # 连接绑定到第一次使用它的事件循环。为了避免测试 fixture 中出现
    # “Future attached to a different loop”，这里每次调用都创建一次一次性 NullPool engine。
    async def _do() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await work(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


@pytest.fixture
def set_resume_parsed_data() -> Callable[[int, dict[str, Any], str], None]:
    """直接把 parsed_json / parse_status 写入简历行。

    Create/Update schema 刻意不接收这些服务端管理字段，因此需要预置已解析简历数据的测试
    会绕过 API，直接 patch 数据库。
    """

    def _set(
        resume_id: int,
        parsed_json: dict[str, Any],
        parse_status: str = "parsed",
    ) -> None:
        async def _work(db: AsyncSession) -> None:
            result = await db.execute(select(Resume).where(Resume.id == resume_id))
            resume = result.scalar_one()
            resume.parsed_json = parsed_json
            resume.parse_status = parse_status
            await db.commit()

        _run_with_fresh_engine(_work)

    return _set


@pytest.fixture
def set_job_parsed_data() -> Callable[[int, dict[str, Any]], None]:
    """基于同样原因，直接把 parsed_json 写入岗位行。"""

    def _set(job_id: int, parsed_json: dict[str, Any]) -> None:
        async def _work(db: AsyncSession) -> None:
            result = await db.execute(
                select(JobPosting).where(JobPosting.id == job_id),
            )
            job = result.scalar_one()
            job.parsed_json = parsed_json
            await db.commit()

        _run_with_fresh_engine(_work)

    return _set


@pytest.fixture
def test_marker() -> str:
    return f"pytest-jobpilot-{uuid4().hex}"


@pytest.fixture
def create_resume(
    client: TestClient,
    test_marker: str,
) -> Callable[[], dict]:
    def _create_resume() -> dict:
        response = client.post(
            "/api/v1/resumes",
            json={
                "title": f"{test_marker} resume",
                "raw_text": "FastAPI, SQLAlchemy async, PostgreSQL.",
                "content_hash": f"{test_marker}-resume-hash",
                "source_type": "manual",
            },
        )
        assert response.status_code == 201
        return response.json()

    return _create_resume


@pytest.fixture
def create_job(
    client: TestClient,
    test_marker: str,
) -> Callable[[], dict]:
    def _create_job() -> dict:
        response = client.post(
            "/api/v1/jobs",
            json={
                "company_name": f"{test_marker} company",
                "job_title": "AI Application Engineer",
                "city": "Shanghai",
                "jd_text": "Build workflow-backed AI applications with FastAPI.",
            },
        )
        assert response.status_code == 201
        return response.json()

    return _create_job


@pytest.fixture
def create_application(
    client: TestClient,
    create_resume: Callable[[], dict],
    create_job: Callable[[], dict],
) -> Callable[[], dict]:
    def _create_application() -> dict:
        resume = create_resume()
        job = create_job()
        response = client.post(
            "/api/v1/applications",
            json={
                "resume_id": resume["id"],
                "job_posting_id": job["id"],
                "current_stage": "saved",
                "next_action": "Review JD",
            },
        )
        assert response.status_code == 201
        return response.json()

    return _create_application
