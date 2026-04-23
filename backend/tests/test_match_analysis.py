from fastapi.testclient import TestClient

from app.llm.client import LLMClient, LLMConfigError


def create_parsed_resume(client: TestClient, test_marker: str) -> dict:
    response = client.post(
        "/api/v1/resumes",
        json={
            "title": f"{test_marker} parsed resume",
            "raw_text": "FastAPI and SQLAlchemy backend experience.",
            "content_hash": f"{test_marker}-mres",
            "source_type": "manual",
            "parse_status": "parsed",
            "parsed_json": {
                "summary": "Backend engineer focused on AI workflow systems.",
                "skills": ["FastAPI", "SQLAlchemy", "PostgreSQL"],
                "experiences": ["Built async API services"],
                "projects": ["JobPilot"],
                "education": [],
                "target_roles": ["AI Application Engineer"],
                "years_of_experience": "2 years",
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def create_parsed_job(client: TestClient, test_marker: str) -> dict:
    response = client.post(
        "/api/v1/jobs",
        json={
            "company_name": f"{test_marker} company",
            "job_title": "AI Application Engineer",
            "city": "Shanghai",
            "jd_text": "Build FastAPI workflow-backed AI applications.",
            "parsed_json": {
                "summary": "Build AI workflow backend services.",
                "responsibilities": ["Build FastAPI services"],
                "required_skills": ["FastAPI", "PostgreSQL"],
                "preferred_skills": ["SQLAlchemy"],
                "keywords": ["ai workflow", "backend"],
                "seniority": "junior-mid",
                "city": "Shanghai",
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def count_matches_for_pair(
    client: TestClient,
    resume_id: int,
    job_posting_id: int,
) -> int:
    response = client.get("/api/v1/matches?limit=100&offset=0")
    assert response.status_code == 200
    return sum(
        1
        for match in response.json()
        if match["resume_id"] == resume_id
        and match["job_posting_id"] == job_posting_id
    )


def test_analyze_match_success(
    client: TestClient,
    test_marker: str,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        assert "Resume structured JSON" in prompt
        assert "Job posting structured JSON" in prompt
        assert "FastAPI" in prompt
        return """
        {
          "overall_score": 86,
          "strengths": ["FastAPI backend experience", "PostgreSQL experience"],
          "weaknesses": ["Limited production AI eval experience"],
          "missing_keywords": ["evaluation"],
          "suggestions": ["Highlight workflow project impact"]
        }
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_parsed_resume(client, test_marker)
    job = create_parsed_job(client, test_marker)
    before_count = count_matches_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["resume_id"] == resume["id"]
    assert data["job_posting_id"] == job["id"]
    assert data["overall_score"] == 86
    assert data["strengths"] == [
        "FastAPI backend experience",
        "PostgreSQL experience",
    ]
    assert data["weaknesses"] == ["Limited production AI eval experience"]
    assert data["missing_keywords"] == ["evaluation"]
    assert data["suggestions"] == ["Highlight workflow project impact"]
    assert count_matches_for_pair(client, resume["id"], job["id"]) == before_count + 1


def test_analyze_missing_resume_returns_404(
    client: TestClient,
    test_marker: str,
) -> None:
    job = create_parsed_job(client, test_marker)

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": 999999999, "job_posting_id": job["id"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume not found"


def test_analyze_missing_job_returns_404(
    client: TestClient,
    test_marker: str,
) -> None:
    resume = create_parsed_resume(client, test_marker)

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": resume["id"], "job_posting_id": 999999999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job posting not found"


def test_analyze_unparsed_resume_returns_400(
    client: TestClient,
    test_marker: str,
) -> None:
    resume = client.post(
        "/api/v1/resumes",
        json={
            "title": f"{test_marker} unparsed resume",
            "raw_text": "FastAPI backend experience.",
            "content_hash": f"{test_marker}-unres",
            "source_type": "manual",
        },
    )
    assert resume.status_code == 201
    job = create_parsed_job(client, test_marker)

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": resume.json()["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Resume needs parsing first"


def test_analyze_unparsed_job_returns_400(
    client: TestClient,
    test_marker: str,
) -> None:
    resume = create_parsed_resume(client, test_marker)
    job = client.post(
        "/api/v1/jobs",
        json={
            "company_name": f"{test_marker} unparsed company",
            "job_title": "Backend Engineer",
            "jd_text": "Build backend services.",
        },
    )
    assert job.status_code == 201

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": resume["id"], "job_posting_id": job.json()["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Job posting needs parsing first"


def test_analyze_invalid_llm_json_returns_502_without_creating_match(
    client: TestClient,
    test_marker: str,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return "This is not JSON."

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_parsed_resume(client, test_marker)
    job = create_parsed_job(client, test_marker)
    before_count = count_matches_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM response is not valid JSON"
    assert count_matches_for_pair(client, resume["id"], job["id"]) == before_count


def test_analyze_invalid_schema_returns_502_without_creating_match(
    client: TestClient,
    test_marker: str,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return """
        {
          "overall_score": 120,
          "strengths": "FastAPI",
          "weaknesses": [],
          "missing_keywords": [],
          "suggestions": []
        }
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_parsed_resume(client, test_marker)
    job = create_parsed_job(client, test_marker)
    before_count = count_matches_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "LLM response does not match match analysis schema"
    )
    assert count_matches_for_pair(client, resume["id"], job["id"]) == before_count


def test_analyze_llm_config_error_returns_500_without_creating_match(
    client: TestClient,
    test_marker: str,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_parsed_resume(client, test_marker)
    job = create_parsed_job(client, test_marker)
    before_count = count_matches_for_pair(client, resume["id"], job["id"])

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "LLM configuration is incomplete"
    assert count_matches_for_pair(client, resume["id"], job["id"]) == before_count


def test_analyze_accepts_llm_json_code_fence(
    client: TestClient,
    test_marker: str,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return """
        ```json
        {
          "overall_score": 74,
          "strengths": ["Python API experience"],
          "weaknesses": ["Needs clearer AI workflow metrics"],
          "missing_keywords": ["metrics"],
          "suggestions": ["Add measurable project outcomes"]
        }
        ```
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_parsed_resume(client, test_marker)
    job = create_parsed_job(client, test_marker)

    response = client.post(
        "/api/v1/matches/analyze",
        json={"resume_id": resume["id"], "job_posting_id": job["id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["overall_score"] == 74
    assert data["missing_keywords"] == ["metrics"]
