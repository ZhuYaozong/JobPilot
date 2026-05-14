import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.llm.client import LLMClient

from tests.test_cover_letter_generation import (
    create_application_record,
    create_match_result,
    create_parsed_job,
    create_parsed_resume,
)


def _fake_tailored_resume_json(label: str = "AI 定制简历") -> str:
    return json.dumps(
        {
            "version_label": label,
            "content_markdown": (
                "# AI Application Engineer 定制简历\n\n"
                "## 项目经历\n- JobPilot: 使用 FastAPI 和 LangGraph 构建求职工作流。"
            ),
            "change_summary": [
                "突出 FastAPI 和 LangGraph 项目经验",
                "围绕岗位要求重排项目经历",
            ],
        },
        ensure_ascii=False,
    )


def test_generate_tailored_resume_success_and_version_no_increments(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    seen_prompts: list[str] = []

    async def fake_generate_text(self, prompt: str) -> str:
        seen_prompts.append(prompt)
        assert "不得编造不存在的经历、项目、指标、奖项、时间、技能" in prompt
        assert '"change_summary": ["中文变更摘要条目", "..."]' in prompt
        # The service should use the latest match for this resume/job pair.
        assert "93" in prompt
        return _fake_tailored_resume_json(f"{test_marker} 定制版")

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    resume = create_parsed_resume(client, test_marker, set_resume_parsed_data)
    job = create_parsed_job(client, test_marker, set_job_parsed_data)
    create_match_result(client, resume["id"], job["id"])
    latest_match = client.post(
        "/api/v1/matches",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "overall_score": 93,
            "strengths": ["FastAPI", "LangGraph"],
            "weaknesses": ["缺少量化指标"],
            "missing_keywords": ["RAG evaluation"],
            "suggestions": ["突出 JobPilot 的 Agent workflow 设计"],
        },
    )
    assert latest_match.status_code == 201

    existing = client.post(
        "/api/v1/resume-versions",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "version_no": 1,
            "version_label": f"{test_marker} 手动版",
            "content": "# Existing",
        },
    )
    assert existing.status_code == 201

    first = client.post(
        "/api/v1/resume-versions/generate-tailored",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )
    assert first.status_code == 201, first.text
    first_data = first.json()
    assert first_data["version_no"] == 2
    assert first_data["source_type"] == "ai_tailored"
    assert first_data["content_format"] == "markdown"
    assert "JobPilot" in first_data["content"]
    assert "突出 FastAPI" in first_data["change_summary"]

    second = client.post(
        "/api/v1/resume-versions/generate-tailored",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )
    assert second.status_code == 201, second.text
    assert second.json()["version_no"] == 3
    assert len(seen_prompts) == 2


def test_generate_tailored_resume_application_record_is_optional_but_validated(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return _fake_tailored_resume_json()

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    resume = create_parsed_resume(client, test_marker, set_resume_parsed_data)
    job = create_parsed_job(client, test_marker, set_job_parsed_data)
    create_match_result(client, resume["id"], job["id"])

    # No application_record_id: should still generate.
    response = client.post(
        "/api/v1/resume-versions/generate-tailored",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )
    assert response.status_code == 201, response.text

    other_job = create_parsed_job(client, f"{test_marker}-other", set_job_parsed_data)
    mismatched_application = create_application_record(
        client,
        resume["id"],
        other_job["id"],
    )
    mismatched = client.post(
        "/api/v1/resume-versions/generate-tailored",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "application_record_id": mismatched_application["id"],
        },
    )
    assert mismatched.status_code == 400
    assert mismatched.json()["detail"] == (
        "Application record does not match resume and job posting"
    )


def test_generate_tailored_resume_missing_match_returns_400(
    client: TestClient,
    test_marker: str,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    resume = create_parsed_resume(client, test_marker, set_resume_parsed_data)
    job = create_parsed_job(client, test_marker, set_job_parsed_data)

    response = client.post(
        "/api/v1/resume-versions/generate-tailored",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Match analysis is required first"


def test_generate_tailored_resume_invalid_json_returns_502_without_version(
    client: TestClient,
    test_marker: str,
    monkeypatch,
    set_resume_parsed_data: Callable[[int, dict[str, Any], str], None],
    set_job_parsed_data: Callable[[int, dict[str, Any]], None],
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return "not json"

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_parsed_resume(client, test_marker, set_resume_parsed_data)
    job = create_parsed_job(client, test_marker, set_job_parsed_data)
    create_match_result(client, resume["id"], job["id"])

    before = client.get(f"/api/v1/resumes/{resume['id']}/versions").json()
    response = client.post(
        "/api/v1/resume-versions/generate-tailored",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )
    after = client.get(f"/api/v1/resumes/{resume['id']}/versions").json()

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM response is not valid JSON"
    assert len(after) == len(before)
