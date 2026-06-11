"""草稿模式岗位生成的 API 行为。

draft 端点接受 text 或 URL,LLM 同时推断公司名/岗位名/城市 + 结构化字段;
URL 路径走 trafilatura 抓取(httpx 通过 respx mock);
都不落库,覆盖错误映射。
"""

import httpx
import respx
from fastapi.testclient import TestClient

from app.llm.client import LLMClient, LLMConfigError


_SAMPLE_HTML = """
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <title>AI 应用研发工程师 · ExampleCo Careers</title>
</head>
<body>
  <main>
    <article>
      <h1>AI 应用研发工程师</h1>
      <p>ExampleCo 正在招募 AI 应用研发工程师,负责对接大模型与业务系统,
      构建 RAG / Agent 工作流,长期协作产品打磨稳定的 AI 服务。</p>
      <h2>岗位职责</h2>
      <ul>
        <li>设计并实现基于 LLM 的 Agent 工作流。</li>
        <li>负责 RAG 检索链路、Prompt 工程与稳定性优化。</li>
      </ul>
      <h2>任职要求</h2>
      <ul>
        <li>3 年以上后端或 AI 工程经验。</li>
        <li>熟悉 Python / FastAPI / 向量数据库。</li>
      </ul>
    </article>
  </main>
</body>
</html>
"""


def _fake_llm_response() -> str:
    """统一的草稿 LLM 返回值,各正路用例共用。"""
    return """
    {
      "company_name": "ExampleCo",
      "job_title": "AI 应用研发工程师",
      "city": "上海",
      "parsed": {
        "summary": "构建 RAG / Agent 工作流",
        "responsibilities": ["设计 Agent 工作流", "RAG 链路优化"],
        "required_skills": ["Python", "FastAPI", "向量数据库"],
        "preferred_skills": [],
        "keywords": ["LLM", "RAG", "Agent"],
        "seniority": "中级",
        "city": "上海"
      }
    }
    """


def test_draft_job_from_text_success(
    client: TestClient,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        assert "ExampleCo" in prompt or "AI 应用" in prompt
        return _fake_llm_response()

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/jobs/draft-from-input",
        json={"text": "ExampleCo 招 AI 应用研发工程师,负责 Agent 工作流。"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["company_name"] == "ExampleCo"
    assert data["job_title"] == "AI 应用研发工程师"
    assert data["city"] == "上海"
    assert data["source_url"] is None
    assert data["jd_text"].startswith("ExampleCo 招")
    assert data["parsed_json"]["seniority"] == "中级"


@respx.mock
def test_draft_job_from_url_success(
    client: TestClient,
    monkeypatch,
) -> None:
    url = "https://careers.example.com/jobs/ai-engineer"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=_SAMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        ),
    )

    async def fake_generate_text(self, prompt: str) -> str:
        # URL 路径下 prompt 里应该有 trafilatura 抽出来的 JD 正文。
        assert "AI 应用研发工程师" in prompt
        return _fake_llm_response()

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/jobs/draft-from-input",
        json={"url": url},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source_url"] == url
    assert data["company_name"] == "ExampleCo"
    assert "AI 应用研发" in data["jd_text"]


def test_draft_job_missing_text_and_url_returns_422(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/jobs/draft-from-input", json={})
    assert response.status_code == 422


def test_draft_job_does_not_persist(
    client: TestClient,
    monkeypatch,
) -> None:
    """draft 端点不能在数据库里留下岗位;调用后列表条数不变。"""

    async def fake_generate_text(self, prompt: str) -> str:
        return _fake_llm_response()

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    before = client.get("/api/v1/jobs").json()
    response = client.post(
        "/api/v1/jobs/draft-from-input",
        json={"text": "随便一段 JD"},
    )
    assert response.status_code == 200
    after = client.get("/api/v1/jobs").json()
    assert len(after) == len(before), "draft 不应该写入 job_postings 表"


@respx.mock
def test_draft_job_url_fetch_failure_returns_422(
    client: TestClient,
) -> None:
    """URL 抓取失败映射为 422 + 友好文案。"""
    url = "https://timeout.example.com/jobs/x"
    respx.get(url).mock(side_effect=httpx.TimeoutException("boom"))

    response = client.post(
        "/api/v1/jobs/draft-from-input",
        json={"url": url},
    )
    assert response.status_code == 422
    assert "及时响应" in response.json()["detail"]


def test_draft_job_tolerates_flat_structure(
    client: TestClient,
    monkeypatch,
) -> None:
    """模型把 parsed 拍平到顶层(没有 parsed 包裹)时,仍能正常归一化。"""

    async def fake_generate_text(self, prompt: str) -> str:
        return """
        {
          "company_name": "字节",
          "job_title": "后端开发",
          "city": "深圳",
          "summary": "后端服务开发",
          "responsibilities": ["设计微服务"],
          "required_skills": ["Go", "MySQL"],
          "preferred_skills": [],
          "keywords": ["微服务"],
          "seniority": "高级"
        }
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/jobs/draft-from-input",
        json={"text": "字节招后端开发"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["company_name"] == "字节"
    assert data["job_title"] == "后端开发"
    assert data["parsed_json"]["required_skills"] == ["Go", "MySQL"]
    assert data["parsed_json"]["seniority"] == "高级"


def test_draft_job_tolerates_string_list_fields(
    client: TestClient,
    monkeypatch,
) -> None:
    """列表字段被模型写成单个字符串时,自动包成数组。"""

    async def fake_generate_text(self, prompt: str) -> str:
        return """
        {
          "company_name": "腾讯",
          "job_title": "测试开发",
          "city": null,
          "parsed": {
            "summary": null,
            "responsibilities": "编写自动化测试",
            "required_skills": "Python",
            "preferred_skills": [],
            "keywords": [],
            "seniority": null,
            "city": null
          }
        }
        """

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/jobs/draft-from-input",
        json={"text": "腾讯招测试开发"},
    )
    assert response.status_code == 200, response.text
    parsed = response.json()["parsed_json"]
    assert parsed["responsibilities"] == ["编写自动化测试"]
    assert parsed["required_skills"] == ["Python"]


def test_draft_job_invalid_llm_json_returns_502(
    client: TestClient,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        return "not json"

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/jobs/draft-from-input",
        json={"text": "随便一段 JD"},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "LLM response is not valid JSON"


def test_draft_job_llm_config_error_returns_500(
    client: TestClient,
    monkeypatch,
) -> None:
    async def fake_generate_text(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    response = client.post(
        "/api/v1/jobs/draft-from-input",
        json={"text": "随便一段 JD"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "LLM configuration is incomplete"
