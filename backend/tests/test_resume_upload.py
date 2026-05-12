"""Tests for POST /api/v1/resumes/upload.

The endpoint accepts PDF / DOCX / TXT / MD files, extracts text, and either
parses immediately or leaves the resume in ``parse_status=pending`` for a
manual /parse retry. These tests pin down both the happy path and the user-
facing error responses so the UI can rely on stable detail messages.

PDF round-trips aren't tested here because generating valid PDFs in a unit
test would require adding reportlab purely for tests; the pdfplumber-based
extraction path is exercised manually instead. DOCX is tested via the
python-docx writer (already on the path for the production extractor).
"""

import io

from fastapi.testclient import TestClient


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    """Build an in-memory DOCX whose body contains the given paragraphs.

    Mirrors how the production extractor reads — paragraphs + table cells —
    so this fixture exercises the same code path real uploads would.
    """
    from docx import Document  # local import keeps the test isolated from
                                # any wider docx config at module load time

    doc = Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_accepts_txt_and_creates_resume(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """A plain text upload should create a resume row with the file's text
    in raw_text and source_type='text'. Auto-parse is mocked because the
    happy-path LLM behaviour is already covered by test_resume_parsing."""
    from app.llm.client import LLMClient

    async def fake_parse(self, prompt: str) -> str:
        return (
            '{"summary": "Backend.", "skills": ["FastAPI"], "experiences": [],'
            ' "projects": [], "education": [], "target_roles": [],'
            ' "years_of_experience": "2"}'
        )

    monkeypatch.setattr(LLMClient, "generate_text", fake_parse)

    body = f"{test_marker} 后端工程师简历。\n5 年 FastAPI 经验。".encode("utf-8")
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.txt", body, "text/plain")},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["source_type"] == "text"
    assert test_marker in data["raw_text"]
    assert data["parse_status"] == "parsed"
    assert data["parsed_json"]["skills"] == ["FastAPI"]
    # Title derives from the filename stem ("resume" → falls back, "resume" is
    # in the generic blacklist so we get the date-stamped placeholder).
    assert data["title"].startswith("上传简历 ")


def test_upload_preserves_custom_title(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """Explicit title form field wins over the filename-derived default."""
    from app.llm.client import LLMClient

    async def fake_parse(self, prompt: str) -> str:
        return (
            '{"summary": null, "skills": [], "experiences": [], "projects": [],'
            ' "education": [], "target_roles": [], "years_of_experience": null}'
        )

    monkeypatch.setattr(LLMClient, "generate_text", fake_parse)

    custom_title = f"{test_marker} Custom Resume"
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("anything.txt", b"hello world hello world hello world", "text/plain")},
        data={"title": custom_title},
    )
    assert response.status_code == 201
    assert response.json()["title"] == custom_title


def test_upload_uses_filename_stem_as_title(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """Non-generic filenames (i.e. not 'upload'/'resume') become the title
    after stripping the extension."""
    from app.llm.client import LLMClient

    async def fake_parse(self, prompt: str) -> str:
        return (
            '{"summary": null, "skills": [], "experiences": [], "projects": [],'
            ' "education": [], "target_roles": [], "years_of_experience": null}'
        )

    monkeypatch.setattr(LLMClient, "generate_text", fake_parse)

    response = client.post(
        "/api/v1/resumes/upload",
        files={
            "file": (
                f"backend-{test_marker}-v3.txt",
                b"backend engineer resume content here",
                "text/plain",
            ),
        },
    )
    assert response.status_code == 201
    assert response.json()["title"] == f"backend-{test_marker}-v3"


def test_upload_accepts_docx(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """DOCX upload: text-bearing paragraphs end up in raw_text, source_type
    is 'docx', and auto-parse runs against the same fake LLM."""
    from app.llm.client import LLMClient

    async def fake_parse(self, prompt: str) -> str:
        return (
            f'{{"summary": "{test_marker}", "skills": ["DOCX"],'
            ' "experiences": [], "projects": [], "education": [],'
            ' "target_roles": [], "years_of_experience": null}'
        )

    monkeypatch.setattr(LLMClient, "generate_text", fake_parse)

    docx_bytes = _build_docx_bytes(
        [
            f"{test_marker} 高级后端工程师",
            "5 年 Python / FastAPI 经验。",
            "曾在 ByteDance 负责微服务改造。",
        ],
    )
    response = client.post(
        "/api/v1/resumes/upload",
        files={
            "file": (
                "experienced-backend.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["source_type"] == "docx"
    assert test_marker in data["raw_text"]
    assert "FastAPI" in data["raw_text"]
    assert data["parsed_json"]["summary"] == test_marker


def test_upload_rejects_oversized_file(client: TestClient) -> None:
    """Files above the 5 MB cap surface a 400 with the size mentioned."""
    oversized = b"x" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("huge.txt", oversized, "text/plain")},
    )
    assert response.status_code == 400
    assert "5 MB" in response.json()["detail"]


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/api/v1/resumes/upload",
        files={
            "file": (
                "resume.zip",
                b"PK\x03\x04 fake zip payload",
                "application/zip",
            ),
        },
    )
    assert response.status_code == 400
    assert "不支持" in response.json()["detail"]


def test_upload_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert "空" in response.json()["detail"]


def test_upload_rejects_text_too_short_to_be_a_resume(client: TestClient) -> None:
    """A file with so little text it can't be a real resume should be
    rejected rather than handed off to the LLM. ``MIN_EXTRACTED_CHARS=30``."""
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("nano.txt", b"too short", "text/plain")},
    )
    assert response.status_code == 400
    assert "扫描" in response.json()["detail"] or "可读文本" in response.json()["detail"]


def test_upload_can_skip_auto_parse(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """When auto_parse=false the resume row is created with parse_status
    'pending' and the LLM is not invoked. Useful for batch import flows."""
    from app.llm.client import LLMClient

    async def fail_if_called(self, prompt: str) -> str:
        raise AssertionError("LLM should not be called when auto_parse=false")

    monkeypatch.setattr(LLMClient, "generate_text", fail_if_called)

    response = client.post(
        "/api/v1/resumes/upload",
        files={
            "file": (
                f"{test_marker}.txt",
                b"some valid resume content here to pass the minimum length check",
                "text/plain",
            ),
        },
        data={"auto_parse": "false"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["parse_status"] == "pending"
    assert data["parsed_json"] is None
