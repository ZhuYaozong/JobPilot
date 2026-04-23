from fastapi.testclient import TestClient

from app.llm.client import LLMClient


def test_parse_job_success(
    client: TestClient,
    test_marker: str,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        assert "Build FastAPI services" in prompt
        return """
        {
          "summary": "Backend role focused on FastAPI services.",
          "responsibilities": ["Build FastAPI services"],
          "required_skills": ["FastAPI", "PostgreSQL"],
          "preferred_skills": ["Docker"],
          "keywords": ["backend", "api"],
          "seniority": "mid",
          "city": "Shanghai"
        }
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    job = client.post(
        "/api/v1/jobs",
        json={
            "company_name": f"{test_marker} company",
            "job_title": "Backend Engineer",
            "city": "Shanghai",
            "jd_text": "Build FastAPI services with PostgreSQL.",
        },
    )
    assert job.status_code == 201

    response = client.post(f"/api/v1/jobs/{job.json()['id']}/parse")

    assert response.status_code == 200
    parsed_json = response.json()["parsed_json"]
    assert parsed_json["summary"] == "Backend role focused on FastAPI services."
    assert parsed_json["required_skills"] == ["FastAPI", "PostgreSQL"]
    assert parsed_json["city"] == "Shanghai"


def test_parse_missing_job_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/jobs/999999999/parse")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job posting not found"


def test_parse_empty_jd_returns_400(client: TestClient, test_marker: str) -> None:
    job = client.post(
        "/api/v1/jobs",
        json={
            "company_name": f"{test_marker} empty jd company",
            "job_title": "Backend Engineer",
            "jd_text": "   ",
        },
    )
    assert job.status_code == 201

    response = client.post(f"/api/v1/jobs/{job.json()['id']}/parse")

    assert response.status_code == 400
    assert response.json()["detail"] == "Job description is empty"


def test_parse_invalid_llm_json_returns_502(
    client: TestClient,
    create_job,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return "This is not JSON."

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    job = create_job()

    response = client.post(f"/api/v1/jobs/{job['id']}/parse")

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM response is not valid JSON"


def test_parse_accepts_llm_json_code_fence(
    client: TestClient,
    create_job,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return """
        ```json
        {
          "summary": "Role returned inside a JSON code fence.",
          "responsibilities": ["Build AI applications"],
          "required_skills": ["Python"],
          "preferred_skills": [],
          "keywords": ["ai"],
          "seniority": null,
          "city": "Hangzhou"
        }
        ```
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    job = create_job()

    response = client.post(f"/api/v1/jobs/{job['id']}/parse")

    assert response.status_code == 200
    parsed_json = response.json()["parsed_json"]
    assert parsed_json["summary"] == "Role returned inside a JSON code fence."
    assert parsed_json["city"] == "Hangzhou"
