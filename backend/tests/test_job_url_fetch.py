"""Tests for POST /api/v1/jobs/fetch-from-url.

The endpoint is preview-only — nothing should be persisted. We mock httpx via
``respx`` so tests stay deterministic regardless of network/DNS availability.
trafilatura runs for real against the mocked HTML so we exercise the actual
extraction pipeline; only the network leg is faked.
"""

import httpx
import respx
from fastapi.testclient import TestClient

# Minimal but realistic JD page — content-heavy enough that trafilatura
# returns text without getting fooled by nav/footer noise. Repeating the
# JD body keeps us well above MIN_TEXT_CHARS even after trafilatura's
# default dedupe.
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
    # ``careers.example.com`` → strips ``careers.`` → ``Example``.
    assert body["company_hint"] in {"Example", "Examplecom"}
    assert "distributed systems" in body["jd_text"].lower()
    assert "responsibilities" in body["jd_text"].lower()


@respx.mock
def test_fetch_from_url_rejects_js_shell_page(client: TestClient) -> None:
    """When the server returns a JS-shell stub the user should get a hint to
    paste manually rather than a confusing empty result."""
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
    """Boss / LinkedIn / 智联 etc. are detected before we even fire a request;
    we cut straight to "请直接粘贴 JD"."""
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
    """httpx timeout is mapped to a user-facing message instead of bubbling up
    as a raw 500."""
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
    """If the URL points at a PDF / binary we tell the user to upload instead
    of trying to parse it as HTML."""
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
    """A page that parses cleanly but has barely any extractable text most
    likely lost the JD behind an auth wall."""
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
    """Sanity check: a successful preview should NOT create a job_postings
    row. The user has to confirm via POST /jobs before anything sticks."""
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
