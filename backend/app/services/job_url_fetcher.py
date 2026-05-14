"""从岗位 URL 抓取 JD，并转换成前端可预览的文本。

当前范围刻意保持务实：只做普通 HTTP 抓取 + trafilatura 主体文本抽取。
公司官网招聘页、Greenhouse/Lever 一类静态页面通常能工作；Boss 直聘、LinkedIn、
智联登录态页面这类需要登录或 JS 渲染的网站，会被识别成友好错误，引导用户回到
“手动填写”粘贴 JD。

这里没有引入 playwright / headless chromium。动态浏览器抓取会显著增加部署成本和
反爬脆弱性，对当前“先拿到可编辑预览”的产品目标不划算。

接口只返回 preview DTO，用户确认后才会走常规 POST /jobs 保存，避免错误抽取在
数据库里留下脏岗位。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


# 不让慢站点长期占住请求线程；前端 axios 外层是 60s，这里提前失败，给 UI 留出展示错误的余量。
FETCH_CONNECT_TIMEOUT_SECONDS = 6.0
FETCH_READ_TIMEOUT_SECONDS = 12.0

# 响应体硬上限。大多数 JD 页面渲染后的 HTML 在 50–300 KB，5 MB 已经很宽松；
# 如果误点到二进制下载或超大页面，这个保护能避免占满内存。
MAX_HTML_BYTES = 5 * 1024 * 1024

# 抽取正文短于这个阈值时，通常说明服务端只返回了 JS 壳或反爬占位文案。
# 与其让 trafilatura 静默失败，不如直接给用户一个可操作的错误。
MIN_TEXT_CHARS = 80

# 用桌面 Chrome 的 UA 作为基线，避免静态页面把我们当成 curl 直接拒掉。
# 这不是强反爬方案，不能绕过 Cloudflare challenge，只是降低普通网页的误拒率。
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 已知普通 HTTP 抓取稳定失败的平台：多半需要登录或 JS 渲染。
# 提前返回定制错误，比让用户等到超时或空结果更友好。
_KNOWN_HOSTILE_HOSTS = {
    "linkedin.com",
    "www.linkedin.com",
    "zhipin.com",
    "www.zhipin.com",
    "boss.com",
    "www.boss.com",
}

# 服务端返回 JS 壳或反爬挑战时常见的提示。先识别这些短语，比等待正文抽取失败更便宜。
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
    """面向用户展示的友好错误。

    ``user_message`` 会被 API 原样回给前端；文案要短、明确、可直接展示。
    """

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True)
class FetchedJD:
    """``/jobs/fetch-from-url`` 返回的预览负载。

    可选字段为 None 表示“无法可靠抽取”，前端会把对应表单留空让用户手填。
    ``jd_text`` 是唯一必需字段；如果正文抽不出来，就抛错而不是返回空预览。
    """

    jd_text: str
    title: str | None
    company_hint: str | None
    city_hint: str | None
    source_url: str


def _normalise_url(url: str) -> str:
    """提前拒绝明显危险或无意义的 URL scheme。

    不允许 ``file://``、``data:`` 等 scheme，避免本地路径读取或无意义内容进入抓取链路。
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
    """对已知需要登录/动态渲染的平台提前短路。"""
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
    """URL 抓取入口：校验 → 抓 HTML → 抽正文 → 返回预览。

    预期内失败都抛 :class:`JobURLFetchError`，由 API 层转成 HTTP 400 和可展示的
    ``detail``。这样前端无需理解底层抓取细节。

    ``http_client`` 只给测试注入使用；生产传 None，每次请求新建一个轻量 client。
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
        city_hint=None,  # 城市很少能从原始 HTML 可靠抽取，交给用户在表单里补。
        source_url=normalised,
    )


async def _fetch_html(
    url: str, *, http_client: httpx.AsyncClient | None,
) -> str:
    """抓取 HTML，并在读取后校验大小上限。

    当前实现依赖 httpx 一次性拿到 response.content 后检查体积。这个上限是防御性保护：
    正常 JD 页面都很小，但误抓二进制或巨大页面时可以及时退出。
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
            # PDF 或二进制下载不走 HTML 解析；让用户用上传/粘贴路径处理更稳定。
            raise JobURLFetchError(
                "这个链接不是 HTML 页面,自动抓取只支持网页。"
                "如果是 PDF,可以下载后从简历管理页上传。",
            )

        content = response.content
        if len(content) > MAX_HTML_BYTES:
            raise JobURLFetchError("页面过大,自动抓取暂不支持。")

        # httpx 会按 Content-Type 自动解码；如果服务端漏掉 charset，会回退到 utf-8。
        return response.text

    if http_client is None:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await _do(client)
    return await _do(http_client)


def _extract_with_trafilatura(
    html: str, url: str,
) -> tuple[str, dict[str, str | None]]:
    """用保守参数运行 trafilatura。

    ``include_comments=False`` 会去掉评论/客服嵌入块；``favor_recall=True`` 更偏向保留
    多一点正文，因为 JD 常常分散在多个 section。metadata 单独抽取，避免标题混进正文。
    """
    import trafilatura  # noqa: PLC0415 — lazy import (~80 ms cold)
    from trafilatura.settings import use_config

    config = use_config()
    # 已经拿到 HTML，不需要 trafilatura 再做下载链路记录。
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
            # 转成普通 dict，测试不需要模拟 TrafilaturaMetadata 的完整类形状。
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
    """从页面标题里尽量提取岗位名。

    很多页面的 ``<title>`` 是“岗位名 - 公司名”或类似结构；这里只剥掉明显公司后缀。
    如果标题像“Careers”“Jobs”这种站点级横幅，就直接丢弃。
    """
    raw = (metadata.get("title") or "").strip()
    if not raw:
        return None

    # 剥掉常见的“岗位名 | 公司名”“岗位名 - 公司名”后缀。
    for sep in (" | ", " — ", " – ", " - ", " · "):
        if sep in raw:
            raw = raw.split(sep, 1)[0].strip()
            break

    # 丢弃站点级噪声标题。
    lower = raw.lower()
    if lower in {"careers", "jobs", "招聘", "career", "join us"}:
        return None
    if len(raw) > 120:
        raw = raw[:120].rsplit(" ", 1)[0]
    return raw or None


def _pick_company(
    metadata: dict[str, str | None], url: str,
) -> str | None:
    """优先使用页面声明的站点名，拿不到时再退回 hostname。"""
    sitename = (metadata.get("sitename") or "").strip()
    if sitename:
        return sitename[:255]

    host = (metadata.get("hostname") or urlparse(url).hostname or "").lower()
    if not host:
        return None
    # ``careers.example.com`` → ``example``；同时去掉开头的 ``www.``。
    host = re.sub(r"^www\.", "", host)
    host = re.sub(r"^careers?\.|^jobs\.", "", host)
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[0].capitalize() if parts[0].isascii() else parts[0]
    return host or None
