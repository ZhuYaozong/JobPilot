"""草稿模式简历生成的 API 行为。

draft 不落库,只返结构化草稿;同时覆盖 LLM 异常映射。
"""

from fastapi.testclient import TestClient

from app.llm.client import LLMClient, LLMConfigError


def test_draft_resume_success(client: TestClient, monkeypatch) -> None:
    """正常路径:LLM 返合规 JSON → 200 + title + raw_text + parsed_json。"""

    async def fake_generate_text(self, prompt: str) -> str:
        # prompt 中应该包含用户原文,便于 LLM 抽结构。
        assert "在阿里做了三年" in prompt
        return """
        {
          "title": "王小明 后端开发简历",
          "parsed": {
            "summary": "三年阿里后端经验",
            "skills": ["Java", "MySQL"],
            "experiences": ["阿里巴巴 后端开发 2022-2025"],
            "projects": ["交易中台"],
            "education": ["计算机本科"],
            "target_roles": ["后端开发"],
            "years_of_experience": "3 年"
          }
        }
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/resumes/draft-from-input",
        json={"text": "王小明,在阿里做了三年后端开发。"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "王小明 后端开发简历"
    assert data["raw_text"] == "王小明,在阿里做了三年后端开发。"
    parsed = data["parsed_json"]
    assert parsed["skills"] == ["Java", "MySQL"]
    assert parsed["years_of_experience"] == "3 年"


def test_draft_resume_does_not_persist(
    client: TestClient,
    monkeypatch,
) -> None:
    """draft 端点不能在数据库里留下简历;调用后列表条数不变。"""

    async def fake_generate_text(self, prompt: str) -> str:
        return (
            '{"title":"测试 简历","parsed":'
            '{"summary":null,"skills":[],"experiences":[],"projects":[],'
            '"education":[],"target_roles":[],"years_of_experience":null}}'
        )

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    before = client.get("/api/v1/resumes").json()
    response = client.post(
        "/api/v1/resumes/draft-from-input",
        json={"text": "测试草稿不落库"},
    )
    assert response.status_code == 200
    after = client.get("/api/v1/resumes").json()
    assert len(after) == len(before), "draft 不应该写入 resumes 表"


def test_draft_resume_empty_text_returns_422(client: TestClient) -> None:
    """min_length=1 在 schema 层就拦下,返回 422。"""
    response = client.post(
        "/api/v1/resumes/draft-from-input",
        json={"text": ""},
    )
    assert response.status_code == 422


def test_draft_resume_invalid_llm_json_returns_502(
    client: TestClient,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return "not json at all"

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/resumes/draft-from-input",
        json={"text": "随便一段简历"},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "LLM response is not valid JSON"


def test_draft_resume_invalid_llm_schema_returns_502(
    client: TestClient,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        # title 缺失 → schema 校验失败
        return (
            '{"parsed":{"summary":null,"skills":[],"experiences":[],'
            '"projects":[],"education":[],"target_roles":[],'
            '"years_of_experience":null}}'
        )

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/resumes/draft-from-input",
        json={"text": "随便一段简历"},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == (
        "LLM response does not match resume draft schema"
    )


def test_draft_resume_llm_config_error_returns_500(
    client: TestClient,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/resumes/draft-from-input",
        json={"text": "随便一段简历"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "LLM configuration is incomplete"
