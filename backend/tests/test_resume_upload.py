"""POST /api/v1/resumes/upload 测试。

接口接收 PDF / DOCX / TXT / MD 文件，抽取文本，并按需立即解析；如果跳过解析，则简历会保持
``parse_status=pending``，等待用户手动调用 /parse 重试。这些测试同时固定成功路径和面向用户的错误响应，
方便前端依赖稳定的 detail 文案。

这里不测试 PDF 往返，因为在单元测试里生成合法 PDF 需要仅为测试引入 reportlab；基于 pdfplumber 的抽取路径改由手工验证。
DOCX 则使用 python-docx writer 测试，它已经是生产抽取器依赖路径的一部分。
"""

import io

from fastapi.testclient import TestClient


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    """构造内存中的 DOCX，正文包含给定段落。

    读取形态与生产抽取器保持一致：段落 + 表格单元格，因此这个 fixture 会覆盖真实上传使用的同一条代码路径。
    """
    from docx import Document  # 局部导入，避免模块加载时受到更宽泛的 docx 配置影响。

    doc = Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_accepts_txt_and_creates_resume(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """纯文本上传应创建简历行，把文件文本写入 raw_text，并设置 source_type='text'。

    自动解析会被 mock 掉，因为 LLM 成功路径已经由 test_resume_parsing 覆盖。
    """
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
    # 标题来自文件名主干；"resume" 位于通用黑名单内，因此会回退为带日期的占位标题。
    assert data["title"].startswith("上传简历 ")


def test_upload_preserves_custom_title(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """显式 title 表单字段优先于从文件名推导的默认标题。"""
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
    """非通用文件名（不是 'upload'/'resume'）去掉扩展名后会成为标题。"""
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
    """DOCX 上传应把含文本的段落写入 raw_text，source_type 为 'docx'，并用同一个模拟 LLM 自动解析。"""
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
    """超过 5 MB 上限的文件会返回 400，并在错误中提示大小限制。"""
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


def test_upload_accepts_short_txt_when_auto_parse_disabled(client: TestClient) -> None:
    """TXT/Markdown 上传本身已经是文本内容，不应仅因笔记很短就展示扫描 PDF 的抽取错误。"""
    response = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("nano.txt", b"too short", "text/plain")},
        data={"auto_parse": "false"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["raw_text"] == "too short"


def test_upload_can_skip_auto_parse(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """auto_parse=false 时只创建 parse_status='pending' 的简历行，且不会调用 LLM，适合批量导入场景。"""
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
