from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.llm.client import LLMClient, LLMClientError, LLMConfigError


def create_parsed_resume(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
) -> dict:
    response = client.post(
        "/api/v1/resumes",
        json={
            "title": f"{test_marker} cover letter resume",
            "raw_text": "FastAPI and workflow backend experience.",
            "content_hash": f"{test_marker}-clres",
            "source_type": "manual",
        },
    )
    assert response.status_code == 201
    resume = response.json()
    set_resume_parsed_data(
        resume["id"],
        {
            "summary": "AI application backend engineer.",
            "skills": ["FastAPI", "SQLAlchemy", "PostgreSQL"],
            "experiences": ["Built workflow-backed APIs"],
            "projects": ["JobPilot"],
            "education": [],
            "target_roles": ["AI Application Engineer"],
            "years_of_experience": "2 years",
        },
        "parsed",
    )
    refreshed = client.get(f"/api/v1/resumes/{resume['id']}")
    assert refreshed.status_code == 200
    return refreshed.json()


def create_parsed_job(
    client: TestClient,
    test_marker: str,
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> dict:
    response = client.post(
        "/api/v1/jobs",
        json={
            "company_name": f"{test_marker} company",
            "job_title": "AI Application Engineer",
            "city": "Shanghai",
            "jd_text": "Build AI workflow applications with FastAPI.",
        },
    )
    assert response.status_code == 201
    job = response.json()
    set_job_parsed_data(
        job["id"],
        {
            "summary": "Build workflow-backed AI applications.",
            "responsibilities": ["Build FastAPI services"],
            "required_skills": ["FastAPI", "PostgreSQL"],
            "preferred_skills": ["SQLAlchemy"],
            "keywords": ["workflow", "ai application"],
            "seniority": "junior-mid",
            "city": "Shanghai",
        },
    )
    refreshed = client.get(f"/api/v1/jobs/{job['id']}")
    assert refreshed.status_code == 200
    return refreshed.json()


def create_match_result(
    client: TestClient,
    resume_id: int,
    job_posting_id: int,
) -> dict:
    response = client.post(
        "/api/v1/matches",
        json={
            "resume_id": resume_id,
            "job_posting_id": job_posting_id,
            "overall_score": 88,
            "strengths": ["FastAPI backend experience", "Workflow project experience"],
            "weaknesses": ["Needs more production metrics"],
            "missing_keywords": ["evaluation"],
            "suggestions": ["Highlight JobPilot workflow impact"],
        },
    )
    assert response.status_code == 201
    return response.json()


def create_application_record(
    client: TestClient,
    resume_id: int,
    job_posting_id: int,
) -> dict:
    response = client.post(
        "/api/v1/applications",
        json={
            "resume_id": resume_id,
            "job_posting_id": job_posting_id,
            "current_stage": "saved",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_cover_letter_ready_pair(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> tuple[dict, dict, dict]:
    resume = create_parsed_resume(client, test_marker, set_resume_parsed_data)
    job = create_parsed_job(client, test_marker, set_job_parsed_data)
    match = create_match_result(client, resume["id"], job["id"])
    return resume, job, match


def count_cover_letter_artifacts_for_pair(
    client: TestClient,
    resume_id: int,
    job_posting_id: int,
) -> int:
    response = client.get("/api/v1/artifacts?limit=100&offset=0")
    assert response.status_code == 200
    return sum(
        1
        for artifact in response.json()
        if artifact["artifact_type"] == "cover_letter"
        and artifact["resume_id"] == resume_id
        and artifact["job_posting_id"] == job_posting_id
    )


def test_generate_cover_letter_zh_success(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        assert "最新匹配结果" in prompt
        assert "只写中文求职信草稿。" in prompt
        return "尊敬的招聘团队：您好！我希望申请 AI Application Engineer 岗位。我的 FastAPI 和工作流项目经验与岗位需求高度匹配。"

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume, job, match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)
    before_count = count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["artifact_type"] == "cover_letter"
    assert data["resume_id"] == resume["id"]
    assert data["job_posting_id"] == job["id"]
    assert data["generator_type"] == "ai"
    assert data["status"] == "draft"
    assert "尊敬的招聘团队" in data["content_text"]
    assert data["content_json"]["artifact_type"] == "cover_letter"
    assert data["content_json"]["language_mode"] == "zh"
    assert data["content_json"]["based_on_match_result_id"] == match["id"]
    assert data["content_json"]["key_points"]
    assert count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"]) == (
        before_count + 1
    )


def test_generate_cover_letter_bilingual_success(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        assert "先写中文版本，再写英文版本。" in prompt
        return """
中文版本：
尊敬的招聘团队：您好！我希望申请 AI Application Engineer 岗位，并能结合 FastAPI 和工作流项目经验创造价值。

English Version:
Dear hiring team, I am excited to apply for the AI Application Engineer role.
"""

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume, job, _match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "language_mode": "bilingual",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["content_json"]["language_mode"] == "bilingual"
    assert "中文版本" in data["content_text"]
    assert "English Version" in data["content_text"]


def test_generate_cover_letter_missing_resume_returns_404(
    client: TestClient,
    test_marker: str,
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    job = create_parsed_job(client, test_marker, set_job_parsed_data)

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": 999999999, "job_posting_id": job["id"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume not found"


def test_generate_cover_letter_missing_job_returns_404(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
) -> None:
    resume = create_parsed_resume(client, test_marker, set_resume_parsed_data)

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": resume["id"], "job_posting_id": 999999999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job posting not found"


def test_generate_cover_letter_missing_application_returns_404(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    resume, job, _match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "application_record_id": 999999999,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application record not found"


def test_generate_cover_letter_mismatched_application_returns_400(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    resume, job, _match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)
    other_job = create_parsed_job(client, f"{test_marker}-other", set_job_parsed_data)
    application = create_application_record(client, resume["id"], other_job["id"])

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "application_record_id": application["id"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Application record does not match resume and job posting"
    )


def test_generate_cover_letter_unparsed_resume_returns_400(
    client: TestClient,
    test_marker: str,
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    resume = client.post(
        "/api/v1/resumes",
        json={
            "title": f"{test_marker} unparsed cover letter resume",
            "raw_text": "FastAPI backend experience.",
            "content_hash": f"{test_marker}-cl-unres",
            "source_type": "manual",
        },
    )
    assert resume.status_code == 201
    job = create_parsed_job(client, test_marker, set_job_parsed_data)

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": resume.json()["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Resume needs parsing first"


def test_generate_cover_letter_unparsed_job_returns_400(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
) -> None:
    resume = create_parsed_resume(client, test_marker, set_resume_parsed_data)
    job = client.post(
        "/api/v1/jobs",
        json={
            "company_name": f"{test_marker} unparsed job company",
            "job_title": "AI Application Engineer",
            "jd_text": "Build AI workflow apps.",
        },
    )
    assert job.status_code == 201

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": resume["id"], "job_posting_id": job.json()["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Job posting needs parsing first"


def test_generate_cover_letter_missing_match_returns_400(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    resume = create_parsed_resume(client, test_marker, set_resume_parsed_data)
    job = create_parsed_job(client, test_marker, set_job_parsed_data)

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Match analysis is required first"


def test_generate_cover_letter_invalid_language_mode_returns_400(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    resume, job, _match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "language_mode": "en",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported language_mode"


def test_generate_cover_letter_llm_config_error_returns_500_without_artifact(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume, job, _match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)
    before_count = count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "LLM configuration is incomplete"
    assert count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"]) == (
        before_count
    )


def test_generate_cover_letter_llm_call_error_returns_502_without_artifact(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        raise LLMClientError("LLM request failed")

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume, job, _match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)
    before_count = count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM request failed"
    assert count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"]) == (
        before_count
    )


def test_generate_cover_letter_empty_result_returns_502_without_artifact(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return "   "

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume, job, _match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)
    before_count = count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Generated cover letter is empty"
    assert count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"]) == (
        before_count
    )


def test_generate_cover_letter_english_only_result_returns_502_without_artifact(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return "Dear hiring team, I am excited to apply for this role."

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume, job, _match = create_cover_letter_ready_pair(client, test_marker, set_resume_parsed_data, set_job_parsed_data)
    before_count = count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/artifacts/generate-cover-letter",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "language_mode": "bilingual",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Generated cover letter must contain Chinese content"
    )
    assert count_cover_letter_artifacts_for_pair(client, resume["id"], job["id"]) == (
        before_count
    )
