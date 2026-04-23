from fastapi.testclient import TestClient

from app.llm.client import LLMClient, LLMConfigError


def test_parse_resume_success(
    client: TestClient,
    test_marker: str,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        assert "FastAPI workflow projects" in prompt
        return """
        {
          "summary": "AI application backend engineer.",
          "skills": ["FastAPI", "SQLAlchemy", "PostgreSQL"],
          "experiences": ["Built async backend APIs"],
          "projects": ["JobPilot workflow system"],
          "education": ["Computer Science"],
          "target_roles": ["AI Application Engineer"],
          "years_of_experience": "2 years"
        }
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = client.post(
        "/api/v1/resumes",
        json={
            "title": f"{test_marker} resume parse target",
            "raw_text": "FastAPI workflow projects with PostgreSQL.",
            "content_hash": f"{test_marker}-rparse",
            "source_type": "manual",
        },
    )
    assert resume.status_code == 201

    response = client.post(f"/api/v1/resumes/{resume.json()['id']}/parse")

    assert response.status_code == 200
    data = response.json()
    parsed_json = data["parsed_json"]
    assert data["parse_status"] == "parsed"
    assert parsed_json["summary"] == "AI application backend engineer."
    assert parsed_json["skills"] == ["FastAPI", "SQLAlchemy", "PostgreSQL"]
    assert parsed_json["target_roles"] == ["AI Application Engineer"]


def test_parse_missing_resume_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/resumes/999999999/parse")

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume not found"


def test_parse_empty_resume_raw_text_returns_400(
    client: TestClient,
    test_marker: str,
) -> None:
    resume = client.post(
        "/api/v1/resumes",
        json={
            "title": f"{test_marker} empty resume",
            "raw_text": "   ",
            "content_hash": f"{test_marker}-empty",
            "source_type": "manual",
        },
    )
    assert resume.status_code == 201

    response = client.post(f"/api/v1/resumes/{resume.json()['id']}/parse")

    assert response.status_code == 400
    assert response.json()["detail"] == "Resume raw text is empty"


def test_parse_invalid_resume_llm_json_returns_502(
    client: TestClient,
    create_resume,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return "This is not JSON."

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_resume()

    response = client.post(f"/api/v1/resumes/{resume['id']}/parse")

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM response is not valid JSON"


def test_parse_resume_llm_config_error_returns_500(
    client: TestClient,
    create_resume,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_resume()

    response = client.post(f"/api/v1/resumes/{resume['id']}/parse")

    assert response.status_code == 500
    assert response.json()["detail"] == "LLM configuration is incomplete"


def test_parse_invalid_resume_schema_returns_502(
    client: TestClient,
    create_resume,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return """
        {
          "summary": "Invalid list fields.",
          "skills": "FastAPI",
          "experiences": [],
          "projects": [],
          "education": [],
          "target_roles": [],
          "years_of_experience": null
        }
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_resume()

    response = client.post(f"/api/v1/resumes/{resume['id']}/parse")

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "LLM response does not match resume parsing schema"
    )


def test_parse_resume_accepts_llm_json_code_fence(
    client: TestClient,
    create_resume,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return """
        ```json
        {
          "summary": "Resume returned inside a JSON code fence.",
          "skills": ["Python"],
          "experiences": ["Built API services"],
          "projects": [],
          "education": [],
          "target_roles": ["Backend Engineer"],
          "years_of_experience": null
        }
        ```
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)
    resume = create_resume()

    response = client.post(f"/api/v1/resumes/{resume['id']}/parse")

    assert response.status_code == 200
    parsed_json = response.json()["parsed_json"]
    assert parsed_json["summary"] == "Resume returned inside a JSON code fence."
    assert parsed_json["skills"] == ["Python"]
