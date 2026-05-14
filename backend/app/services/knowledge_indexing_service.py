"""知识库文档索引流水线：切片 → 向量化 → 持久化。

状态机由 ``KnowledgeDocument.status`` 驱动：

    pending  (just persisted, no chunks yet)
       │
       ▼
    parsing  (this function holds the row in flight)
       │
       ├── on success → ready (chunks written, chunk_count populated)
       └── on failure → failed (error_detail set, old chunks restored to None)

切片 7'c2 刻意保持同步执行，不引 celery / RQ。典型文档少于 50 个 chunk，
一次批量 embedding 通常 1–3 秒；如果真实用户反馈上传等待太久，后续可以把调用
移到 FastAPI BackgroundTasks，当前 service 契约不需要改变。

安全上限：如果文档会切出超过 ``MAX_CHUNKS_PER_DOCUMENT`` 个 chunk，就拒绝索引。
这能防止没有段落换行的 5 MB Markdown 文件烧掉大量 embedding 预算。
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
    EmbeddingConfigError,
)
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.text_splitter import TextChunk, split_text


# 切片参数。800 / 100 适合中英混合求职资料：中文段落常在 200 字左右，
# 800 字能容纳 3–4 句话并带足上下文；真实资料变长后再做配置化。
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100

# 单文档 chunk 数硬上限。普通简历约 10 个 chunk，30 页公司背景文档约 50 个；
# 200 留出余量，同时避免格式异常的上传耗尽 embedding 预算。
MAX_CHUNKS_PER_DOCUMENT = 200


async def index_document(
    db: AsyncSession,
    document: KnowledgeDocument,
    *,
    embedding_client: EmbeddingClient | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> KnowledgeDocument:
    """为单个文档执行切片、embedding、写入 chunk 的完整流程。

    无论成功或失败都会提交最终状态，调用方即使不手动 refresh，也能相信数据库里的
    row 反映真实结果。只有程序员错误会继续抛出；embedding 配置、网络、供应商响应
    等问题都落到 ``status=failed`` 和 ``error_detail``。
    """
    client = embedding_client or EmbeddingClient()

    document.status = "parsing"
    document.error_detail = None
    await db.commit()
    await db.refresh(document)

    try:
        chunks = await _build_and_persist_chunks(
            db, document, client, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        )
    except EmbeddingConfigError as exc:
        return await _mark_failed(db, document, f"embedding_config_missing: {exc}")
    except EmbeddingClientError as exc:
        return await _mark_failed(db, document, f"embedding_request_failed: {exc}")
    except ValueError as exc:
        # 切片参数或 chunk 数保护会抛 ValueError；这属于文档不可索引，不升级成 500。
        return await _mark_failed(db, document, f"indexing_rejected: {exc}")
    except Exception as exc:  # noqa: BLE001 — last-ditch defensive
        return await _mark_failed(
            db, document, f"unexpected_indexing_error: {type(exc).__name__}: {exc}",
        )

    document.status = "ready"
    document.chunk_count = len(chunks)
    document.error_detail = None
    await db.commit()
    await db.refresh(document)
    return document


async def reindex_document(
    db: AsyncSession,
    document: KnowledgeDocument,
    *,
    embedding_client: EmbeddingClient | None = None,
) -> KnowledgeDocument:
    """删除文档已有 chunks，并从头重新索引。

    失败后用户点“重新索引”会走这里；未来如果支持编辑文档正文，也可以复用。
    该函数幂等，同一个文档重复调用不会留下重叠 chunk。
    """
    await _drop_chunks(db, document)
    document.chunk_count = 0
    document.status = "pending"
    document.error_detail = None
    await db.commit()
    await db.refresh(document)
    return await index_document(db, document, embedding_client=embedding_client)


async def _build_and_persist_chunks(
    db: AsyncSession,
    document: KnowledgeDocument,
    client: EmbeddingClient,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    """index_document 中真正执行切片和写库的主体逻辑，单独拆出便于读失败路径。"""
    text_chunks = split_text(
        document.raw_text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if not text_chunks:
        # 空文本经过归一化后没有任何 chunk；保持 ready + 0 chunks，用户可编辑后重新索引。
        await _drop_chunks(db, document)
        return []

    if len(text_chunks) > MAX_CHUNKS_PER_DOCUMENT:
        raise ValueError(
            f"document would produce {len(text_chunks)} chunks "
            f"(cap {MAX_CHUNKS_PER_DOCUMENT}); please split or shorten it.",
        )

    embeddings = await client.embed([c.text for c in text_chunks])
    if len(embeddings) != len(text_chunks):
        # EmbeddingClient 已经校验过数量；这里再防御一次，避免部分写入污染检索。
        raise ValueError(
            "embedding count mismatch — refusing to write partial chunks",
        )

    # 保证幂等：写新 chunks 之前先删旧 chunks，避免两次索引结果重叠。
    await _drop_chunks(db, document)

    rows = [
        KnowledgeChunk(
            document_id=document.id,
            user_id=document.user_id,
            chunk_index=i,
            content=tc.text,
            embedding=vec,
            char_start=tc.char_start,
            char_end=tc.char_end,
        )
        for i, (tc, vec) in enumerate(zip(text_chunks, embeddings))
    ]
    db.add_all(rows)
    await db.commit()
    return text_chunks


async def _drop_chunks(db: AsyncSession, document: KnowledgeDocument) -> None:
    """批量删除某个文档已有的 chunks。

    这个函数独立出来，是为了让失败路径也能清理部分写入，而不必触发完整 reindex。
    """
    await db.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id),
    )


async def _mark_failed(
    db: AsyncSession, document: KnowledgeDocument, detail: str,
) -> KnowledgeDocument:
    """持久化失败状态，并返回重新加载后的文档行。

    这里返回新实例而不是 patch 调用方手上的旧实例，是为了避开 MissingGreenlet：
    ``db.rollback()`` 后，session 上挂着的 ORM 实例都会过期，之后任何同步 ``.attr``
    访问都可能触发 lazy SELECT，而 FastAPI serializer 不在 SQLAlchemy async greenlet
    里。重新 select 一次并返回已加载实例，调用方序列化时就不会踩这个坑。

    这和 ``assistant_service._finalize_failed_run`` 使用的是同一类防御模式。
    """
    document_id = document.id

    try:
        await db.rollback()
    except Exception:  # noqa: BLE001
        pass
    refreshed = (
        await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id),
        )
    ).scalar_one_or_none()
    if refreshed is None:
        # 文档在索引过程中被删除了，没有可标记的行，直接把旧对象交回调用方。
        return document
    # 删除异常发生前可能已经写入的部分 chunks，避免 failed 文档还能被检索到。
    await db.execute(
        delete(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id,
        ),
    )
    refreshed.status = "failed"
    refreshed.chunk_count = 0
    refreshed.error_detail = detail
    await db.commit()
    await db.refresh(refreshed)
    return refreshed
