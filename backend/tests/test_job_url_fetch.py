"""POST /api/v1/jobs/fetch-from-url 测试。

这个 endpoint 只返回预览，不应持久化任何内容。测试通过 ``respx`` mock httpx，
避免受网络或 DNS 影响。trafilatura 会真实处理被 mock 的 HTML，因此能覆盖实际抽取流水线；
只有网络请求这一段是假的。
"""

import httpx
import respx
from fastapi.testclient import TestClient

# 尽量小但足够真实的 JD 页面。正文信息量足够让 trafilatura 抽到文本，
# 不会被导航和页脚噪音误导；重复 JD 正文可以确保默认去重后仍高于 MIN_TEXT_CHARS。
_SAMPLE_HTML = """
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <title>Senior Backend Engineer · ExampleCo Careers</title>
  <meta name="description" content="Backend role">
</head>
<body>
  <header><nav>Home | About | Careers</nav></header>
  <main>
    <article>
      <h1>Senior Backend Engineer</h1>
      <p>At ExampleCo we build distributed systems that move trillions of bytes a day.
      We are looking for a senior backend engineer who can own end-to-end services in
      Go and Python, mentor junior engineers, and partner closely with product to
      ship reliably.</p>
      <h2>Responsibilities</h2>
      <ul>
        <li>Design, build and operate large-scale backend services.</li>
        <li>Mentor mid-level engineers on testing and code review practices.</li>
        <li>Work with SRE on observability and on-call rotations.</li>
      </ul>
      <h2>Requirements</h2>
      <ul>
        <li>5+ years of production backend engineering.</li>
        <li>Strong fluency in Go or Python; comfort with the other.</li>
        <li>Experience with PostgreSQL, Redis and Kafka at scale.</li>
      </ul>
    </article>
  </main>
  <footer>&copy; 2025 ExampleCo</footer>
</body>
</html>
"""


@respx.mock
def test_fetch_from_url_extracts_title_company_and_jd(
    client: TestClient,
) -> None:
    url = "https://careers.example.com/jobs/senior-backend"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=_SAMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        ),
    )

    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": url},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["source_url"] == url
    assert body["title"] == "Senior Backend Engineer"
    # ``careers.example.com`` 会去掉 ``careers.``，得到 ``Example``。
    assert body["company_hint"] in {"Example", "Examplecom"}
    assert "distributed systems" in body["jd_text"].lower()
    assert "responsibilities" in body["jd_text"].lower()


@respx.mock
def test_fetch_from_url_rejects_js_shell_page(client: TestClient) -> None:
    """服务端返回 JS 外壳页面时，应提示用户手动粘贴，而不是给出迷惑性的空结果。"""
    url = "https://www.example-shell.com/job/123"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=(
                "<html><body><noscript>Please enable JavaScript to continue.</noscript>"
                "<div id='app'></div></body></html>"
            ),
            headers={"content-type": "text/html"},
        ),
    )

    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": url},
    )
    assert response.status_code == 400
    assert "JavaScript" in response.json()["detail"]


def test_fetch_from_url_short_circuits_known_hostile_hosts(
    client: TestClient,
) -> None:
    """Boss / LinkedIn / 智联等站点会在发请求前识别，并直接提示用户粘贴 JD。"""
    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": "https://www.zhipin.com/job_detail/abc123.html"},
    )
    assert response.status_code == 400
    assert "登录" in response.json()["detail"]


def test_fetch_from_url_rejects_non_http_schemes(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": "file:///etc/passwd"},
    )
    assert response.status_code == 400
    assert "http" in response.json()["detail"].lower()


def test_fetch_from_url_rejects_blank_url(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": "   "},
    )
    assert response.status_code == 400


@respx.mock
def test_fetch_from_url_surfaces_remote_error(client: TestClient) -> None:
    url = "https://careers.example.com/jobs/gone"
    respx.get(url).mock(return_value=httpx.Response(404, text="Not Found"))

    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": url},
    )
    assert response.status_code == 400
    assert "404" in response.json()["detail"]


@respx.mock
def test_fetch_from_url_surfaces_timeout(client: TestClient) -> None:
    """httpx timeout 应映射成用户可读提示，而不是冒泡成原始 500。"""
    url = "https://slow.example.com/job"
    respx.get(url).mock(side_effect=httpx.ConnectTimeout("connect timeout"))

    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": url},
    )
    assert response.status_code == 400
    assert "及时响应" in response.json()["detail"]


@respx.mock
def test_fetch_from_url_rejects_non_html_content_type(
    client: TestClient,
) -> None:
    """URL 指向 PDF 或二进制内容时，应提示用户上传文件，而不是当作 HTML 解析。"""
    url = "https://careers.example.com/jd.pdf"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=b"%PDF-1.7 binary content here",
            headers={"content-type": "application/pdf"},
        ),
    )

    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": url},
    )
    assert response.status_code == 400
    assert "HTML" in response.json()["detail"]


@respx.mock
def test_fetch_from_url_rejects_page_with_too_little_text(
    client: TestClient,
) -> None:
    """页面能解析但几乎抽不到文本时，大概率是 JD 被登录墙挡住了。"""
    url = "https://careers.example.com/empty"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text="<html><body><p>Sign in to view this job.</p></body></html>",
            headers={"content-type": "text/html"},
        ),
    )

    response = client.post(
        "/api/v1/jobs/fetch-from-url",
        json={"url": url},
    )
    assert response.status_code == 400
    assert "可读" in response.json()["detail"] or "登录" in response.json()["detail"]


@respx.mock
def test_fetch_from_url_does_not_persist_anything(
    client: TestClient,
) -> None:
    """基础确认：成功预览不应创建 job_postings 行，用户必须 POST /jobs 才会保存。"""
    url = "https://careers.example.com/preview-only"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=_SAMPLE_HTML.replace(
                "Senior Backend Engineer", "Preview-Only Engineer",
            ),
            headers={"content-type": "text/html"},
        ),
    )

    list_before = client.get("/api/v1/jobs?limit=100").json()
    ids_before = {j["id"] for j in list_before}

    response = client.post("/api/v1/jobs/fetch-from-url", json={"url": url})
    assert response.status_code == 200

    list_after = client.get("/api/v1/jobs?limit=100").json()
    ids_after = {j["id"] for j in list_after}
    assert ids_after == ids_before
