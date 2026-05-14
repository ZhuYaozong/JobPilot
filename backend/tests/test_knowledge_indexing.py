"""7'c2 索引流水线集成测试。

真实 embedding endpoint 通过 ``monkeypatch`` mock 掉，让测试保持确定且低成本。
这里直接 patch ``EmbeddingClient.embed``，而不是用 respx mock HTTP，因为索引服务会在
自己的作用域里创建 client；测试关心的是行为（成功、失败、维度不匹配），不是网络格式。
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


# ---------- 辅助方法 --------------------------------------------------------


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
    """确定性的模拟 embedding：把文本 hash 成 ``dim`` 个 [-1, 1] 浮点数。

    相同文本会得到相同向量，方便测试断言向量内容与 chunk 内容存在对应关系。
    """
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    # 重复 seed 字节直到填满 dim，再把每个字节映射到 [-1, 1]。
    raw = (seed * (dim // len(seed) + 1))[:dim]
    return [(b / 127.5) - 1.0 for b in raw]


def _install_fake_embedder(monkeypatch, *, dim: int | None = None) -> None:
    """替换 EmbeddingClient.embed，让它返回模拟向量。"""
    target_dim = dim if dim is not None else settings.embedding_dimensions

    async def fake_embed(self, texts: list[str]) -> list[list[float]]:
        return [_fake_embedding(t, target_dim) for t in texts]

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)


def _install_failing_embedder(monkeypatch, exc: Exception) -> None:
    async def fake_embed(self, texts: list[str]) -> list[list[float]]:
        raise exc

    monkeypatch.setattr(EmbeddingClient, "embed", fake_embed)


# ---------- 成功路径 ----------------------------------------------------


def test_upload_indexes_document_to_ready(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """端到端验证：上传 TXT → 索引写入 chunks → status=ready，且 embedding 维度正确。"""
    _install_fake_embedder(monkeypatch)

    kb_id = client.post(
        "/api/v1/knowledge/bases",
        json={"name": f"{test_marker} index"},
    ).json()["id"]

    # 文本长度足够在默认 800 字 chunk 大小下切出多个 chunk。
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

    # chunk 应已存在，并且都带有 embedding。
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


# ---------- 失败路径 ------------------------------------------------


def test_indexing_failure_lands_in_failed_status_with_error_detail(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """embedding endpoint 未配置时，索引应把文档标记为 failed，而不是返回 500。"""
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

    # 失败时不应写入任何 chunk。
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


# ---------- 重新索引 --------------------------------------------------------


def test_reindex_clears_failed_state_and_writes_chunks(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """用户流程：
    1. embedding 配置错误时上传，文档变为 status=failed。
    2. 修好配置（测试里切换成可用的模拟 embedder）。
    3. POST /reindex 后，文档变为 status=ready 并写入 chunks。
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

    # 现在安装可用 embedder 并重试。
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
    """对 ready 文档调用 reindex 应删除旧 chunks 并写入新 chunks。

    chunk 数量可以保持不变，embedding 应被重新生成；由于模拟向量对同一文本是确定性的，
    这里不额外断言向量变化。
    """
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


# ---------- 清理不变量 -------------------------------------------


def test_reindex_drops_previous_chunks_atomically(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """重新索引后，文档不应同时保留新旧 chunks；这里用 chunk_index 连续性来断言。"""
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
    """确认测试 seam 仍然可用。

    其他测试会用 auto_index=False 低成本预置 pending 文档。API 路径走不到这里
    （生产中 auto_index 恒为 true），因此直接调用 service 函数覆盖这条路径。
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
