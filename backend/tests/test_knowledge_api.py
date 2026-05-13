"""Tests for /api/v1/knowledge — slice 7'c1 (data + upload, no embedding).

Verifies the KB / document CRUD shape + ACL invariants. Indexing /
embedding behaviour ships in slice 7'c2 and gets its own test file.
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


# ---------- KB CRUD -------------------------------------------------------


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

    # Upload a TXT document so we have a document row to cascade.
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

    # Manually insert a fake chunk so we can prove cascade also wipes chunks
    # (slice 7'c1 doesn't run real indexing, so we backfill via DB write).
    async def _seed_chunk(db: AsyncSession) -> None:
        db.add(
            KnowledgeChunk(
                document_id=doc_id,
                user_id=upload_resp.json()["id"],  # any int is fine; we use doc_id-derived
                chunk_index=0,
                content="seed chunk",
                embedding=None,
                char_start=0,
                char_end=10,
            ),
        )
        # Pull the real user_id off the document and patch the row above —
        # using doc_id as user_id worked by accident before, but be explicit.
        await db.flush()
        await db.commit()

    # Find the user_id off the document row for the seeded chunk.
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

    # Delete the KB → expect doc and chunk both gone via ON DELETE CASCADE.
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


# ---------- Document upload ------------------------------------------------


def test_upload_txt_creates_document_with_text_persisted(
    client: TestClient, test_marker: str,
) -> None:
    """The data-layer guarantees: text is extracted, source_type/raw_text are
    populated, and the row lands in a terminal status (ready / failed).
    Whether indexing succeeds depends on whether the test environment has
    an embedding endpoint configured — assertions are written so the row
    contract holds in either case. Slice 7'c2's dedicated tests
    (test_knowledge_indexing.py) verify the indexing pipeline itself."""
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
    """Uploading byte-identical content to the same KB should return the
    existing document instead of creating a duplicate."""
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
    """The /documents endpoint (vs /documents/upload) lets the user paste
    a note instead of uploading a file. Same downstream shape; source_type
    becomes ``manual``."""
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
    """A document uploaded into KB A must not appear in KB B's listing."""
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
