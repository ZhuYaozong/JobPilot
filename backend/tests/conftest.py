from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


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
