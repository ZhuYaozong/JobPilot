"""Generic file → plain-text extraction.

Supports PDF / DOCX / TXT / Markdown uploads. Used by both:
- Resume upload (POST /api/v1/resumes/upload) — slice 7'a
- Knowledge base document upload (POST /api/v1/knowledge/.../documents) — 7'c1

Scope intentionally small: text-only extraction. Scanned-image PDFs return
empty / near-empty text; OCR fallback is deferred to a later slice. Encrypted
files surface a friendly error to the caller.

The module is intentionally framework-agnostic — no FastAPI / SQLAlchemy
imports. Callers catch :class:`FileExtractionError` and decide whether to
map it to HTTP 400 (resumes / knowledge upload), a chat reply, or something
else.
"""

from __future__ import annotations

import io
from dataclasses import dataclass


# 5 MB cap — comfortably above a typical text-heavy resume (≈100 KB) and
# most career-page PDFs. Bumped per-deployment via env later if real users
# hit the wall.
MAX_FILE_BYTES = 5 * 1024 * 1024

# Trimmed text shorter than this almost always means OCR-only PDFs, blank
# files, or extraction failures masquerading as success. Surface the issue
# so the user knows to retry with a text-bearing copy instead of moving on
# to LLM parsing / chunking with garbage input.
MIN_EXTRACTED_CHARS = 30


class FileExtractionError(Exception):
    """Raised when we cannot reliably turn the upload into plain text.

    ``user_message`` is what the API echoes back — kept short and actionable
    so the UI can show it verbatim without further translation.
    """

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True)
class ExtractedFile:
    text: str
    source_type: str  # "pdf" | "docx" | "markdown" | "text"


def extract_text_from_upload(
    filename: str,
    content_type: str | None,
    payload: bytes,
) -> ExtractedFile:
    """Dispatch on file extension first, falling back to content_type.

    Filename extension is more reliable than the browser-supplied MIME type
    (which is often ``application/octet-stream`` for downloads). The
    content_type is only consulted as a tie-breaker for extension-less files.
    """
    if len(payload) > MAX_FILE_BYTES:
        size_mb = MAX_FILE_BYTES // (1024 * 1024)
        raise FileExtractionError(
            f"文件超过 {size_mb} MB 上限，请压缩或截取后再上传。",
        )

    if not payload:
        raise FileExtractionError("上传的文件是空的。")

    lower = filename.lower().strip()
    if lower.endswith(".pdf"):
        text = _extract_pdf(payload)
        source = "pdf"
    elif lower.endswith(".docx"):
        text = _extract_docx(payload)
        source = "docx"
    elif lower.endswith((".md", ".markdown")):
        text = _decode_text(payload)
        source = "markdown"
    elif lower.endswith(".txt"):
        text = _decode_text(payload)
        source = "text"
    elif content_type in ("application/pdf",):
        text = _extract_pdf(payload)
        source = "pdf"
    elif content_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        text = _extract_docx(payload)
        source = "docx"
    elif content_type and content_type.startswith("text/"):
        text = _decode_text(payload)
        source = "text"
    else:
        raise FileExtractionError(
            "暂不支持这种文件类型，请上传 PDF、DOCX、TXT 或 Markdown。",
        )

    normalised = _normalise_whitespace(text)
    if not normalised:
        if source in {"text", "markdown"}:
            raise FileExtractionError("上传的文本文件没有内容。")
        raise FileExtractionError(
            "文件里抽不到可读文本（可能是扫描件或图片型 PDF）。"
            "请改上传可复制文本的版本，或先转存为 DOCX/TXT。",
        )
    if source in {"pdf", "docx"} and len(normalised) < MIN_EXTRACTED_CHARS:
        raise FileExtractionError(
            "文件里抽不到可读文本（可能是扫描件或图片型 PDF）。"
            "请改上传可复制文本的版本，或先转存为 DOCX/TXT。",
        )
    return ExtractedFile(text=normalised, source_type=source)


def _extract_pdf(payload: bytes) -> str:
    """Pull text out of a PDF using pdfplumber.

    Imported lazily so the rest of the backend doesn't pay the import cost
    (pdfplumber pulls in pdfminer.six + pillow, ~50ms on first import).
    """
    import pdfplumber  # noqa: PLC0415 — lazy import for cold-start cost

    try:
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            chunks = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:  # noqa: BLE001 — pdfplumber surfaces many error types
        raise FileExtractionError(
            "PDF 解析失败，可能文件已损坏或加密；请上传其他格式。",
        ) from exc

    return "\n\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip())


def _extract_docx(payload: bytes) -> str:
    """Pull text out of a DOCX using python-docx.

    python-docx yields paragraphs in document order — we join them with
    newlines so downstream consumers (LLM parsing, RAG chunking) see
    structure roughly equivalent to "<body>".
    """
    from docx import Document  # noqa: PLC0415 — lazy import

    try:
        document = Document(io.BytesIO(payload))
    except Exception as exc:  # noqa: BLE001 — python-docx raises broad exceptions
        raise FileExtractionError(
            "DOCX 解析失败，可能文件已损坏；请重新导出后再试。",
        ) from exc

    parts: list[str] = []
    for paragraph in document.paragraphs:
        text = (paragraph.text or "").strip()
        if text:
            parts.append(text)

    # Tables show up separately from paragraphs in python-docx; pull cell
    # text out too so e.g. a resume that uses a side-bar table for skills,
    # or a knowledge-base doc with structured info, isn't silently dropped.
    for table in document.tables:
        for row in table.rows:
            cells = [(cell.text or "").strip() for cell in row.cells]
            row_text = " | ".join(cell for cell in cells if cell)
            if row_text:
                parts.append(row_text)

    return "\n".join(parts)


def _decode_text(payload: bytes) -> str:
    """Decode UTF-8 with a graceful fallback to GBK / UTF-16.

    Most resumes / notes posted online are UTF-8 these days, but legacy
    Windows exports from Chinese-locale machines can still be GBK; trying
    a few common encodings keeps those users from hitting a wall.
    """
    for encoding in ("utf-8", "gbk", "utf-16"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FileExtractionError("文件编码不支持，请保存为 UTF-8 后重试。")


def _normalise_whitespace(text: str) -> str:
    """Trim each line + collapse runs of blank lines.

    Token budget is precious; PDFs especially tend to insert empty lines
    between every paragraph. Collapsing them costs nothing and shortens
    downstream LLM prompts noticeably.
    """
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    blank_pending = False
    for line in lines:
        if line.strip():
            if blank_pending and out:
                out.append("")
            out.append(line)
            blank_pending = False
        else:
            blank_pending = True
    return "\n".join(out).strip()
