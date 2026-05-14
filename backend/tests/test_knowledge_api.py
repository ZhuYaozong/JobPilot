"""/api/v1/knowledge 测试：7'c1 数据层 + 上传，不包含 embedding。

验证知识库 / 文档 CRUD 形状与 ACL 不变量。索引 / embedding 行为在 7'c2 交付，
并由独立测试文件覆盖。
"""

import asyncio
import io
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument


def _run(coro_factory: Callable) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------- 知识库 CRUD -------------------------------------------------------


def test_create_and_list_knowledge_base(
    client: TestClient, test_marker: str,
) -> None:
    create_resp = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} KB", "description": "test"},
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["name"] == f"{test_marker} KB"
    assert created["document_count"] == 0
    kb_id = created["id"]

    list_resp = client.get("/api/v1/knowledge/bases?limit=100")
    assert list_resp.status_code == 200
    ids = [kb["id"] for kb in list_resp.json()]
    assert kb_id in ids


def test_update_knowledge_base_renames(
    client: TestClient, test_marker: str,
) -> None:
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} before"},
    ).json()["id"]

    patch_resp = client.patch(
        f"/api/v1/knowledge/bases/{kb_id}",
        json={"name": f"{test_marker} after", "description": "updated"},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["name"] == f"{test_marker} after"
    assert body["description"] == "updated"


def test_update_knowledge_base_rejects_empty_name(
    client: TestClient, test_marker: str,
) -> None:
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} k"},
    ).json()["id"]

    resp = client.patch(
        f"/api/v1/knowledge/bases/{kb_id}",
        json={"name": "   "},
    )
    assert resp.status_code == 400


def test_kb_endpoints_reject_other_users_or_missing(client: TestClient) -> None:
    for route in (
        "/api/v1/knowledge/bases/999999999",
        "/api/v1/knowledge/bases/999999999/documents",
        "/api/v1/knowledge/documents/999999999",
    ):
        resp = client.get(route)
        assert resp.status_code == 404, route


def test_delete_kb_cascades_documents_and_chunks(
    client: TestClient, test_marker: str,
) -> None:
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} cascade"},
    ).json()["id"]

    # 上传 TXT 文档，得到一行可用于级联删除验证的 document。
    upload_resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={
            "file": (
                f"{test_marker}-note.txt",
                b"This is a test knowledge document with enough text to pass the threshold.",
                "text/plain",
            ),
        },
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # 手工插入模拟 chunk，用来证明级联删除也会清理 chunks。
    # 7'c1 不运行真实索引，因此这里直接写 DB 回填。
    async def _seed_chunk(db: AsyncSession) -> None:
        db.add(
            KnowledgeChunk(
                document_id=doc_id,
                user_id=upload_resp.json()["id"],  # 任意整数都可以；这里使用由 doc_id 派生的值。
                chunk_index=0,
                content="seed chunk",
                embedding=None,
                char_start=0,
                char_end=10,
            ),
        )
        # 从 document 上取真实 user_id 再 patch 上方行。以前把 doc_id 当 user_id
        # 只是碰巧可用，这里显式写清楚。
        await db.flush()
        await db.commit()

    # 从 document 行读取 user_id，用于预置 chunk。
    async def _seed_chunk_correct(db: AsyncSession) -> int:
        doc = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id),
            )
        ).scalar_one()
        chunk = KnowledgeChunk(
            document_id=doc_id,
            user_id=doc.user_id,
            chunk_index=0,
            content="seed chunk",
            embedding=None,
            char_start=0,
            char_end=10,
        )
        db.add(chunk)
        await db.commit()
        return chunk.id

    chunk_id = _run(_seed_chunk_correct)

    # 删除 KB 后，doc 和 chunk 都应通过 ON DELETE CASCADE 消失。
    del_resp = client.delete(f"/api/v1/knowledge/bases/{kb_id}")
    assert del_resp.status_code == 204

    async def _check_gone(db: AsyncSession) -> tuple[bool, bool]:
        doc = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id),
            )
        ).scalar_one_or_none()
        chunk = (
            await db.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id),
            )
        ).scalar_one_or_none()
        return doc is None, chunk is None

    doc_gone, chunk_gone = _run(_check_gone)
    assert doc_gone
    assert chunk_gone


# ---------- 文档上传 ------------------------------------------------


def test_upload_txt_creates_document_with_text_persisted(
    client: TestClient, test_marker: str,
) -> None:
    """验证数据层保证：文本会被抽取，source_type/raw_text 会被填充，行进入终态。

    索引是否成功取决于测试环境是否配置了 embedding endpoint；这里的断言覆盖
    ready / failed 两种终态。7'c2 的专门测试负责验证索引流水线本身。
    """
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} upload"},
    ).json()["id"]

    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={
            "file": (
                f"{test_marker}.txt",
                f"{test_marker} 我在 ByteDance 做了大规模数据管道。".encode("utf-8"),
                "text/plain",
            ),
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] in {"ready", "failed"}
    assert body["source_type"] == "text"
    assert test_marker in body["raw_text"]


def test_upload_docx_extracts_paragraphs(
    client: TestClient, test_marker: str,
) -> None:
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} docx"},
    ).json()["id"]

    docx_bytes = _build_docx_bytes(
        [
            f"{test_marker} 项目素材库",
            "在 Alibaba 做了用户增长系统的架构改造。",
            "上线后 DAU 提升 12%。",
        ],
    )
    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={
            "file": (
                "growth.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_type"] == "docx"
    assert "DAU" in body["raw_text"]


def test_upload_dedups_same_file_in_same_kb(
    client: TestClient, test_marker: str,
) -> None:
    """同一 KB 内上传字节完全相同的内容时，应返回已有文档而不是创建重复行。"""
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} dedup"},
    ).json()["id"]

    body = (
        f"{test_marker} duplicate content with enough text to pass minimum."
    ).encode("utf-8")
    first = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={"file": (f"{test_marker}.txt", body, "text/plain")},
    )
    second = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={"file": (f"{test_marker}-renamed.txt", body, "text/plain")},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_upload_rejects_oversized(
    client: TestClient, test_marker: str,
) -> None:
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} big"},
    ).json()["id"]

    huge = b"x" * (5 * 1024 * 1024 + 1)
    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={"file": ("huge.txt", huge, "text/plain")},
    )
    assert resp.status_code == 400


def test_create_manual_document_persists_pasted_body(
    client: TestClient, test_marker: str,
) -> None:
    """/documents endpoint 允许用户粘贴文本，而不是上传文件。

    下游形状与上传一致，source_type 会变成 ``manual``。
    """
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} manual"},
    ).json()["id"]

    body = f"{test_marker} 公司背景:这家是 B 轮 SaaS,主要做协作工具。"
    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents",
        json={"title": "公司笔记", "body": body},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_type"] == "manual"
    assert data["title"] == "公司笔记"
    assert test_marker in data["raw_text"]


def test_create_manual_document_rejects_short_body(
    client: TestClient, test_marker: str,
) -> None:
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} short"},
    ).json()["id"]

    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents",
        json={"title": "tiny", "body": "too short"},
    )
    assert resp.status_code == 400


def test_delete_document_cascades_chunks(
    client: TestClient, test_marker: str,
) -> None:
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} del doc"},
    ).json()["id"]

    doc_resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={
            "file": (
                f"{test_marker}-x.txt",
                b"some test document body big enough to pass the threshold here.",
                "text/plain",
            ),
        },
    )
    doc_id = doc_resp.json()["id"]

    async def _seed_chunk(db: AsyncSession) -> int:
        doc = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id),
            )
        ).scalar_one()
        chunk = KnowledgeChunk(
            document_id=doc_id,
            user_id=doc.user_id,
            chunk_index=0,
            content="seed",
            embedding=None,
            char_start=0,
            char_end=4,
        )
        db.add(chunk)
        await db.commit()
        return chunk.id

    chunk_id = _run(_seed_chunk)

    del_resp = client.delete(f"/api/v1/knowledge/documents/{doc_id}")
    assert del_resp.status_code == 204

    async def _check(db: AsyncSession) -> bool:
        return (
            await db.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id),
            )
        ).scalar_one_or_none() is None

    assert _run(_check)


def test_list_documents_filters_by_kb(
    client: TestClient, test_marker: str,
) -> None:
    """上传到 KB A 的文档不应出现在 KB B 的列表里。"""
    kb_a = client.post(
        "/api/v1/knowledge/bases", json={"name": f"{test_marker} A"},
    ).json()["id"]
    kb_b = client.post(
        "/api/v1/knowledge/bases", json={"name": f"{test_marker} B"},
    ).json()["id"]

    upload = client.post(
        f"/api/v1/knowledge/bases/{kb_a}/documents/upload",
        files={
            "file": (
                f"{test_marker}-a.txt",
                b"a document that belongs to knowledge base A only.",
                "text/plain",
            ),
        },
    )
    doc_id_in_a = upload.json()["id"]

    docs_in_b = client.get(f"/api/v1/knowledge/bases/{kb_b}/documents").json()
    assert all(d["id"] != doc_id_in_a for d in docs_in_b)

    docs_in_a = client.get(f"/api/v1/knowledge/bases/{kb_a}/documents").json()
    assert any(d["id"] == doc_id_in_a for d in docs_in_a)


def test_list_document_chunks_returns_ordered_preview(
    client: TestClient, test_marker: str,
) -> None:
    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} chunks"},
    ).json()["id"]

    doc_resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={
            "file": (
                f"{test_marker}-chunks.txt",
                b"chunk preview document body big enough to pass the threshold.",
                "text/plain",
            ),
        },
    )
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    async def _replace_chunks(db: AsyncSession) -> None:
        doc = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id),
            )
        ).scalar_one()
        await db.execute(
            sa_delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id),
        )
        db.add_all(
            [
                KnowledgeChunk(
                    document_id=doc.id,
                    user_id=doc.user_id,
                    chunk_index=1,
                    content=f"{test_marker} second chunk",
                    embedding=None,
                    char_start=20,
                    char_end=39,
                ),
                KnowledgeChunk(
                    document_id=doc.id,
                    user_id=doc.user_id,
                    chunk_index=0,
                    content=f"{test_marker} first chunk",
                    embedding=None,
                    char_start=0,
                    char_end=18,
                ),
            ],
        )
        doc.chunk_count = 2
        await db.commit()

    _run(_replace_chunks)

    resp = client.get(f"/api/v1/knowledge/documents/{doc_id}/chunks?limit=10")
    assert resp.status_code == 200
    chunks = resp.json()
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]
    assert chunks[0]["document_id"] == doc_id
    assert chunks[0]["content"] == f"{test_marker} first chunk"
    assert chunks[0]["char_start"] == 0
    assert chunks[0]["char_end"] == 18


def test_list_document_chunks_rejects_missing_document(client: TestClient) -> None:
    resp = client.get("/api/v1/knowledge/documents/999999999/chunks")
    assert resp.status_code == 404
