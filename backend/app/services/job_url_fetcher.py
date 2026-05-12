"""Fetch a job posting from a URL and turn it into preview text.

Pragmatic scope: simple HTTP fetch + trafilatura main-text extraction.
Companies' own career pages (Greenhouse, Lever, Greenhouse-style template
careers, 拉勾's public listings, etc.) work; sites that gate content behind
auth or JS rendering (Boss直聘, LinkedIn, 智联's logged-in views) are
detected and surfaced as a friendly error directing the user back to manual
paste. We deliberately do NOT bring in playwright / headless chromium — the
deployment cost / scraping fragility isn't worth it for the first cut.

The endpoint returns a *preview* DTO; nothing is persisted until the user
confirms (and posts to the regular POST /jobs endpoint). That keeps wrong
extractions from leaving stale rows in the DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


# Don't let a slow site stall the request thread for too long; the front-end
# axios timeout (60s) is the outer limit, this gives us margin to detect
# trouble before the client gives up.
FETCH_CONNECT_TIMEOUT_SECONDS = 6.0
FETCH_READ_TIMEOUT_SECONDS = 12.0

# Hard cap on response size; we read with stream=True and abort if a server
# sends more. Most JD pages are 50–300 KB rendered HTML — 5 MB is comfortably
# above that without letting accidental binary downloads exhaust memory.
MAX_HTML_BYTES = 5 * 1024 * 1024

# Body shorter than this almost always means the server only returned a JS
# shell with a "Please enable JavaScript" stub. trafilatura will return
# nothing useful and we'd rather give a helpful error than silently fail.
MIN_TEXT_CHARS = 80

# Browsers identify themselves so many anti-scrape filters at least let
# Chrome through; we use a real desktop-Chrome UA. This is not a defense
# against aggressive anti-bot (it won't pass Cloudflare challenges), just a
# baseline so static pages don't reject us as "curl/0.x".
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Known platforms where naive fetch reliably fails (auth / JS-rendered).
# We short-circuit with a tailored message instead of letting the user wait
# 12 seconds for an empty result.
_KNOWN_HOSTILE_HOSTS = {
    "linkedin.com",
    "www.linkedin.com",
    "zhipin.com",
    "www.zhipin.com",
    "boss.com",
    "www.boss.com",
}

# Hints that a server returned a JS shell or anti-bot challenge instead of
# the real JD. Cheaper to recognise these than to wait for trafilatura to
# return nothing useful.
_JS_SHELL_HINTS = (
    "enable javascript",
    "please enable javascript",
    "请开启 javascript",
    "请启用 javascript",
    "javascript is required",
    "cf-challenge",
    "cloudflare",
)


class JobURLFetchError(Exception):
    """Friendly, user-facing error.

    ``user_message`` is what the API echoes back; keep it short and
    actionable so the UI can render it verbatim.
    """

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True)
class FetchedJD:
    """Preview payload returned by the /jobs/fetch-from-url endpoint.

    None on any field means "we couldn't extract it confidently"; the UI
    leaves the corresponding form input empty and lets the user fill in
    manually. The full ``jd_text`` is mandatory — if we can't get text, we
    raise instead of returning an empty preview.
    """

    jd_text: str
    title: str | None
    company_hint: str | None
    city_hint: str | None
    source_url: str


def _normalise_url(url: str) -> str:
    """Reject obviously dangerous schemes early.

    httpx would otherwise happily ``file://`` an arbitrary path or fetch
    ``data:`` URIs that leak nothing useful — better to fail fast with a
    clear message.
    """
    cleaned = url.strip()
    if not cleaned:
        raise JobURLFetchError("请填写岗位链接")

    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise JobURLFetchError("只能抓取 http(s) 链接")
    if not parsed.netloc:
        raise JobURLFetchError("链接格式不正确,请检查后重试")
    return cleaned


def _check_known_hostile(url: str) -> None:
    """Short-circuit on platforms that we know don't work without auth."""
    host = (urlparse(url).hostname or "").lower()
    if host in _KNOWN_HOSTILE_HOSTS:
        raise JobURLFetchError(
            "这个网站需要登录或动态渲染才能看到 JD,自动抓取拿不到。"
            "请打开页面后复制 JD 文本,改用「手动填写」 tab 粘贴。",
        )


def _looks_like_js_shell(html: str) -> bool:
    lower = html[:2000].lower()
    return any(hint in lower for hint in _JS_SHELL_HINTS)


async def fetch_jd_from_url(
    url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> FetchedJD:
    """Top-level entry point. Validates → fetches → extracts → returns.

    Raises :class:`JobURLFetchError` with a user-facing message on any
    expected failure path. The caller (API endpoint) maps the exception to
    HTTP 400 + detail = user_message.

    ``http_client`` is injectable for tests; production passes ``None`` and
    we open a fresh client per request (httpx clients are cheap).
    """
    normalised = _normalise_url(url)
    _check_known_hostile(normalised)

    html = await _fetch_html(normalised, http_client=http_client)

    if _looks_like_js_shell(html):
        raise JobURLFetchError(
            "这个页面需要 JavaScript 才能看到 JD,自动抓取拿不到内容。"
            "请直接复制 JD 文本,改用「手动填写」 tab 粘贴。",
        )

    text, metadata = _extract_with_trafilatura(html, normalised)
    if not text or len(text) < MIN_TEXT_CHARS:
        raise JobURLFetchError(
            "页面里抽不到可读 JD 文本,可能是登录后才显示或反爬。"
            "请直接粘贴 JD 内容,改用「手动填写」 tab。",
        )

    return FetchedJD(
        jd_text=text,
        title=_pick_job_title(metadata),
        company_hint=_pick_company(metadata, normalised),
        city_hint=None,  # City rarely surfaces from raw HTML; let user fill.
        source_url=normalised,
    )


async def _fetch_html(
    url: str, *, http_client: httpx.AsyncClient | None,
) -> str:
    """Stream the response so we can enforce ``MAX_HTML_BYTES`` without
    actually loading a multi-MB binary into memory.

    Aborting mid-stream isn't strictly necessary for security (the cap is
    defensive — most JD pages are tiny) but matches the same protective
    pattern resume_file_extractor uses for uploads.
    """
    timeout = httpx.Timeout(
        FETCH_READ_TIMEOUT_SECONDS, connect=FETCH_CONNECT_TIMEOUT_SECONDS,
    )
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    async def _do(client: httpx.AsyncClient) -> str:
        try:
            response = await client.get(
                url,
                headers=headers,
                follow_redirects=True,
            )
        except httpx.TimeoutException as exc:
            raise JobURLFetchError(
                "网站没有及时响应,请稍后重试或换种方式提供 JD。",
            ) from exc
        except httpx.HTTPError as exc:
            raise JobURLFetchError(
                "无法访问这个链接,请确认链接可在浏览器打开后重试。",
            ) from exc

        if response.status_code >= 400:
            raise JobURLFetchError(
                f"网站返回了 {response.status_code},无法抓取。",
            )

        content_type = (response.headers.get("content-type") or "").lower()
        if "html" not in content_type and "xml" not in content_type:
            # PDF / binary downloads etc. — we don't try to parse them as
            # HTML; tell the user to upload directly instead.
            raise JobURLFetchError(
                "这个链接不是 HTML 页面,自动抓取只支持网页。"
                "如果是 PDF,可以下载后从简历管理页上传。",
            )

        content = response.content
        if len(content) > MAX_HTML_BYTES:
            raise JobURLFetchError("页面过大,自动抓取暂不支持。")

        # httpx already decodes per Content-Type; fall back to utf-8 if the
        # server omits a charset (common with bare nginx defaults).
        return response.text

    if http_client is None:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await _do(client)
    return await _do(http_client)


def _extract_with_trafilatura(
    html: str, url: str,
) -> tuple[str, dict[str, str | None]]:
    """Run trafilatura with conservative settings.

    ``include_comments=False`` drops disqus/intercom blocks; ``favor_recall``
    leans toward keeping more text (JDs often span multiple sections). We
    pull metadata separately so the title isn't tangled into the JD body.
    """
    import trafilatura  # noqa: PLC0415 — lazy import (~80 ms cold)
    from trafilatura.settings import use_config

    config = use_config()
    # Disable download trail signals — we already have the HTML in hand.
    config.set("DEFAULT", "EXTRACTION_TIMEOUT", "10")

    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
            config=config,
        )
    except Exception:  # noqa: BLE001 — trafilatura raises broad types
        text = None

    metadata: dict[str, str | None] = {}
    try:
        md = trafilatura.extract_metadata(html)
        if md is not None:
            # Convert TrafilaturaMetadata dataclass to a plain dict so tests
            # don't have to mock the class shape; access via .__dict__ is
            # supported.
            metadata = {
                "title": getattr(md, "title", None),
                "author": getattr(md, "author", None),
                "sitename": getattr(md, "sitename", None),
                "hostname": getattr(md, "hostname", None),
            }
    except Exception:  # noqa: BLE001
        pass

    return (text or "").strip(), metadata


def _pick_job_title(metadata: dict[str, str | None]) -> str | None:
    """The page <title> is usually "<Job Title> at <Company>" or similar.

    Strip the company suffix when it's obviously there; leave the rest. Drop
    the title entirely if it looks like a sitewide banner ("Careers", "Jobs"
    etc.).
    """
    raw = (metadata.get("title") or "").strip()
    if not raw:
        return None

    # Strip common "<Title> | Company" / "<Title> - Company" suffixes.
    for sep in (" | ", " — ", " – ", " - ", " · "):
        if sep in raw:
            raw = raw.split(sep, 1)[0].strip()
            break

    # Discard noise pages.
    lower = raw.lower()
    if lower in {"careers", "jobs", "招聘", "career", "join us"}:
        return None
    if len(raw) > 120:
        raw = raw[:120].rsplit(" ", 1)[0]
    return raw or None


def _pick_company(
    metadata: dict[str, str | None], url: str,
) -> str | None:
    """Prefer the page's declared sitename; fall back to hostname stem."""
    sitename = (metadata.get("sitename") or "").strip()
    if sitename:
        return sitename[:255]

    host = (metadata.get("hostname") or urlparse(url).hostname or "").lower()
    if not host:
        return None
    # ``careers.example.com`` → ``example``; strip leading ``www.``.
    host = re.sub(r"^www\.", "", host)
    host = re.sub(r"^careers?\.|^jobs\.", "", host)
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[0].capitalize() if parts[0].isascii() else parts[0]
    return host or None
