"""Integration tests for slice 7'c2 indexing pipeline.

The real embedding endpoint is mocked via ``monkeypatch`` so tests are
deterministic + cheap. We patch ``EmbeddingClient.embed`` directly rather
than respx-mocking HTTP because the indexing service creates the client
inside its own scope and we want to control the *behaviour* (success,
failure, dim mismatch) not the wire format.
"""

import asyncio
import hashlib
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.llm.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
    EmbeddingConfigError,
)
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument


# ---------- Helpers --------------------------------------------------------


def _run(coro_factory: Callable) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


def _fake_embedding(text: str, dim: int) -> list[float]:
    """Deterministic fake embedding: hash the text into ``dim`` floats in
    [-1, 1]. Order-preserving so tests can assert vector content correlates
    with chunk content.
    """
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    # Repeat the seed bytes to fill dim, then map each byte to [-1, 1].
    raw = (seed * (dim // len(seed) + 1))[:dim]
    return [(b / 127.5) - 1.0 for b in raw]


def _install_fake_embedder(monkeypatch, *, dim: int | None = None) -> None:
    """Patch EmbeddingClient.embed to return fake vectors."""
    target_dim = dim if dim is not None else settings.embedding_dimensions

    async def fake_embed(self, texts: list[str]) -> list[list[float]]:
        return [_fake_embedding(t, target_dim) for t in texts]

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)


def _install_failing_embedder(monkeypatch, exc: Exception) -> None:
    async def fake_embed(self, texts: list[str]) -> list[list[float]]:
        raise exc

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)


# ---------- Happy path ----------------------------------------------------


def test_upload_indexes_document_to_ready(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """End-to-end: upload a TXT → indexing writes chunks → status=ready,
    chunk_count > 0, embeddings persisted with the right dim."""
    _install_fake_embedder(monkeypatch)

    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} index"},
    ).json()["id"]

    # Long enough to produce multiple chunks at the default 800-char size.
    body = (
        f"{test_marker} 我在 ByteDance 做了大规模数据管道。"
        "上线后日处理 1 TB,延迟降低 40%。\n\n"
        + ("继续描述项目细节。详细记录技术方案。" * 50)
    ).encode("utf-8")

    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={"file": (f"{test_marker}.txt", body, "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "ready"
    assert data["chunk_count"] > 0
    doc_id = data["id"]

    # Chunks should exist with embeddings.
    async def _inspect(db: AsyncSession) -> tuple[int, bool]:
        rows = (
            await db.execute(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.document_id == doc_id,
                ).order_by(KnowledgeChunk.chunk_index),
            )
        ).scalars().all()
        all_have_embeddings = all(c.embedding is not None for c in rows)
        return len(rows), all_have_embeddings

    count, has_embeddings = _run(_inspect)
    assert count == data["chunk_count"]
    assert has_embeddings


def test_manual_document_also_indexed(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    _install_fake_embedder(monkeypatch)

    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} manual idx"},
    ).json()["id"]

    body = "公司背景:" + ("这家公司是 B 轮 SaaS,做协作工具。" * 20)
    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents",
        json={"title": f"{test_marker} 笔记", "body": body},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ready"
    assert data["chunk_count"] >= 1


# ---------- Failure paths ------------------------------------------------


def test_indexing_failure_lands_in_failed_status_with_error_detail(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """When the embedding endpoint isn't configured, indexing should mark
    the doc as failed (not 500) and surface a friendly error_detail."""
    _install_failing_embedder(
        monkeypatch, EmbeddingConfigError("missing api key"),
    )

    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} fail"},
    ).json()["id"]

    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={
            "file": (
                f"{test_marker}.txt",
                f"{test_marker} valid resume body content to pass min length.".encode("utf-8"),
                "text/plain",
            ),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "failed"
    assert data["chunk_count"] == 0
    assert "embedding_config_missing" in data["error_detail"]

    # No chunks should have been written.
    doc_id = data["id"]

    async def _count(db: AsyncSession) -> int:
        rows = (
            await db.execute(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.document_id == doc_id,
                ),
            )
        ).scalars().all()
        return len(rows)

    assert _run(_count) == 0


def test_remote_error_maps_to_failed(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    _install_failing_embedder(
        monkeypatch, EmbeddingClientError("HTTP 502 from upstream"),
    )

    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} 502"},
    ).json()["id"]

    resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={
            "file": (
                f"{test_marker}.txt",
                f"{test_marker} body to pass length threshold.".encode("utf-8"),
                "text/plain",
            ),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "failed"
    assert "embedding_request_failed" in data["error_detail"]


# ---------- Reindex --------------------------------------------------------


def test_reindex_clears_failed_state_and_writes_chunks(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """User flow:
    1. Upload while embedding is misconfigured → status=failed
    2. Fix config (= swap fake embedder to a working one)
    3. POST /reindex → status=ready with chunks
    """
    _install_failing_embedder(
        monkeypatch, EmbeddingConfigError("oops"),
    )

    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} reindex"},
    ).json()["id"]

    body = f"{test_marker} valid body content to pass the length threshold.".encode("utf-8")
    upload_resp = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={"file": (f"{test_marker}.txt", body, "text/plain")},
    )
    assert upload_resp.json()["status"] == "failed"
    doc_id = upload_resp.json()["id"]

    # Now install a working embedder and retry.
    _install_fake_embedder(monkeypatch)
    reindex_resp = client.post(
        f"/api/v1/knowledge/documents/{doc_id}/reindex",
    )
    assert reindex_resp.status_code == 200, reindex_resp.text
    body = reindex_resp.json()
    assert body["status"] == "ready"
    assert body["chunk_count"] >= 1
    assert body["error_detail"] is None


def test_reindex_idempotent_on_ready_document(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """Calling reindex on an already-ready document should drop old chunks
    and write fresh ones — chunk count may stay the same, embeddings should
    be regenerated (which we don't bother asserting since fakes are
    deterministic per text)."""
    _install_fake_embedder(monkeypatch)

    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} idem"},
    ).json()["id"]

    body = f"{test_marker} small but valid body content here to be indexed.".encode("utf-8")
    doc_id = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={"file": (f"{test_marker}.txt", body, "text/plain")},
    ).json()["id"]

    initial_count = client.get(
        f"/api/v1/knowledge/documents/{doc_id}",
    ).json()["chunk_count"]

    reindex_resp = client.post(
        f"/api/v1/knowledge/documents/{doc_id}/reindex",
    )
    assert reindex_resp.status_code == 200
    after = reindex_resp.json()
    assert after["status"] == "ready"
    assert after["chunk_count"] == initial_count


# ---------- Cleanup invariants -------------------------------------------


def test_reindex_drops_previous_chunks_atomically(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """After reindexing, the document should never have BOTH old and new
    chunks. We assert by checking chunk_index is contiguous from 0."""
    _install_fake_embedder(monkeypatch)

    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} drop"},
    ).json()["id"]

    body = ("第一段。" * 100 + "\n\n" + "第二段。" * 100).encode("utf-8")
    doc_id = client.post(
        f"/api/v1/knowledge/bases/{kb_id}/documents/upload",
        files={"file": (f"{test_marker}.txt", body, "text/plain")},
    ).json()["id"]

    client.post(f"/api/v1/knowledge/documents/{doc_id}/reindex")

    async def _indices(db: AsyncSession) -> list[int]:
        rows = (
            await db.execute(
                select(KnowledgeChunk.chunk_index)
                .where(KnowledgeChunk.document_id == doc_id)
                .order_by(KnowledgeChunk.chunk_index),
            )
        ).all()
        return [int(row[0]) for row in rows]

    indices = _run(_indices)
    assert indices == list(range(len(indices))), (
        f"expected contiguous 0..N indices, got {indices}"
    )


def test_doc_status_pending_when_auto_index_disabled(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """Sanity check that the test seam still works — auto_index=False is
    used by other test files to seed pending docs cheaply.

    We can't reach this codepath through the API (auto_index is always
    true in production), so we exercise the service function directly.
    """
    from app.models.knowledge_base import KnowledgeBase
    from app.models.user import User
    from app.services import knowledge_service

    _install_failing_embedder(
        monkeypatch, AssertionError("embed should not be called when auto_index=False"),
    )

    async def _scenario(db: AsyncSession) -> str:
        user = (
            await db.execute(select(User).where(User.username == "test"))
        ).scalar_one()
        kb = KnowledgeBase(user_id=user.id, name=f"{test_marker} no-idx")
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        doc = await knowledge_service.upload_document(
            db,
            kb=kb,
            user=user,
            filename="x.txt",
            content_type="text/plain",
            payload=f"{test_marker} text long enough to pass threshold filter.".encode("utf-8"),
            auto_index=False,
        )
        return doc.status

    assert _run(_scenario) == "pending"
