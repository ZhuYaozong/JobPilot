"""知识库和文档的业务逻辑层。

它和 API 层分开，是为了让未来的 Agent 工具、批量导入任务等入口复用同一套 CRUD
和归属校验逻辑，不在多个 router 里重复实现。API 层只负责 HTTP 请求/响应形状转换。

7'c1 只保证“文档正文已保存，状态为 pending”；7'c2 开始接入切片和 embedding。
索引状态机见 ``KnowledgeDocument.status`` 与 ``knowledge_chunks`` 相关模型注释。
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.embedding_client import EmbeddingClient
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.user import User
from app.services.file_text_extractor import (
    ExtractedFile,
    FileExtractionError,
    extract_text_from_upload,
)
from app.services.knowledge_indexing_service import (
    index_document,
    reindex_document as _reindex_document_via_indexer,
)


# ============================================================================
# 知识库 CRUD
# ============================================================================


async def list_knowledge_bases(
    db: AsyncSession,
    user: User,
    *,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[tuple[KnowledgeBase, int]]:
    """返回当前用户可见的 ``(kb, document_count)`` 列表。

    默认按 updated_at 最近优先；已归档知识库默认隐藏，但可通过 include_archived 打开，
    方便后续管理或清理界面使用。
    """
    base_q = select(KnowledgeBase).where(KnowledgeBase.user_id == user.id)
    if not include_archived:
        base_q = base_q.where(KnowledgeBase.status != "archived")
    base_q = (
        base_q.order_by(KnowledgeBase.updated_at.desc(), KnowledgeBase.id.desc())
        .limit(limit)
        .offset(offset)
    )
    kbs = list((await db.execute(base_q)).scalars().all())
    if not kbs:
        return []

    # 文档数量用一条 group by 查询拿齐，避免每个 KB 再查一次造成 N+1。
    count_rows = (
        await db.execute(
            select(
                KnowledgeDocument.knowledge_base_id,
                func.count(KnowledgeDocument.id),
            )
            .where(
                KnowledgeDocument.knowledge_base_id.in_([kb.id for kb in kbs]),
                KnowledgeDocument.user_id == user.id,
            )
            .group_by(KnowledgeDocument.knowledge_base_id),
        )
    ).all()
    counts = {row[0]: int(row[1]) for row in count_rows}
    return [(kb, counts.get(kb.id, 0)) for kb in kbs]


async def get_knowledge_base_for_user_or_404(
    db: AsyncSession, kb_id: int, user: User,
) -> KnowledgeBase:
    row = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user.id,
        ),
    )
    kb = row.scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


async def count_documents_in(
    db: AsyncSession, kb_id: int, user_id: int,
) -> int:
    return int(
        (
            await db.execute(
                select(func.count(KnowledgeDocument.id)).where(
                    KnowledgeDocument.knowledge_base_id == kb_id,
                    KnowledgeDocument.user_id == user_id,
                ),
            )
        ).scalar_one(),
    )


async def create_knowledge_base(
    db: AsyncSession,
    user: User,
    *,
    name: str,
    description: str | None,
    status: str,
) -> KnowledgeBase:
    kb = KnowledgeBase(
        user_id=user.id,
        name=name.strip(),
        description=description,
        status=status,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


async def update_knowledge_base(
    db: AsyncSession,
    kb: KnowledgeBase,
    *,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> KnowledgeBase:
    if name is not None:
        trimmed = name.strip()
        if not trimmed:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        kb.name = trimmed
    if description is not None:
        kb.description = description
    if status is not None:
        kb.status = status
    await db.commit()
    await db.refresh(kb)
    return kb


async def delete_knowledge_base(
    db: AsyncSession, kb: KnowledgeBase,
) -> None:
    """级联删除知识库。

    documents 和 chunks 都有 ON DELETE CASCADE，所以删父知识库即可清掉整棵树。
    这里仍走 ORM delete，而不是裸 SQL delete；如果未来加 SQLAlchemy 事件钩子，
    这条路径可以自然触发。
    """
    await db.delete(kb)
    await db.commit()


# ============================================================================
# 文档 CRUD
# ============================================================================


async def list_documents(
    db: AsyncSession,
    kb_id: int,
    user: User,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[KnowledgeDocument]:
    rows = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.knowledge_base_id == kb_id,
            KnowledgeDocument.user_id == user.id,
        )
        .order_by(
            KnowledgeDocument.updated_at.desc(),
            KnowledgeDocument.id.desc(),
        )
        .limit(limit)
        .offset(offset),
    )
    return list(rows.scalars().all())


async def get_document_for_user_or_404(
    db: AsyncSession, document_id: int, user: User,
) -> KnowledgeDocument:
    row = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.user_id == user.id,
        ),
    )
    doc = row.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def list_document_chunks(
    db: AsyncSession,
    document: KnowledgeDocument,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[KnowledgeChunk]:
    rows = await db.execute(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.document_id == document.id,
            KnowledgeChunk.user_id == document.user_id,
        )
        .order_by(KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
        .limit(limit)
        .offset(offset),
    )
    return list(rows.scalars().all())


async def upload_document(
    db: AsyncSession,
    *,
    kb: KnowledgeBase,
    user: User,
    filename: str,
    content_type: str | None,
    payload: bytes,
    title_override: str | None = None,
    embedding_client: EmbeddingClient | None = None,
    auto_index: bool = True,
) -> KnowledgeDocument:
    """抽取文件文本、保存文档，并同步执行索引流水线。

    索引失败不会回滚文档本身；文档会进入 ``status=failed``，并写入 ``error_detail``。
    用户修复配置后可以在 UI 点击“重新索引”。

    ``auto_index=False`` 只给测试使用，用来种 pending 文档而不消耗模拟 embedding。
    生产路径默认都会立即索引。
    """
    try:
        extracted = extract_text_from_upload(filename, content_type, payload)
    except FileExtractionError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc

    doc = await _persist_extracted_document(
        db,
        kb=kb,
        user=user,
        extracted=extracted,
        title=title_override or _derive_title_from_filename(filename),
        source_url=None,
    )
    if auto_index:
        # index_document 失败时可能 rollback session，使原始 doc 实例 detached/expired。
        # 一定接住返回值，确保后续序列化的是重新加载过的安全对象。
        doc = await index_document(db, doc, embedding_client=embedding_client)
    return doc


async def create_manual_document(
    db: AsyncSession,
    *,
    kb: KnowledgeBase,
    user: User,
    title: str,
    body: str,
    source_url: str | None,
    embedding_client: EmbeddingClient | None = None,
    auto_index: bool = True,
) -> KnowledgeDocument:
    """“粘贴文本”入口对应的文档创建逻辑。

    它和简历的“手动粘贴”路径类似，适合保存不在文件里的资料，例如面试官反馈、
    公司背景笔记或临时复盘。
    """
    trimmed = (body or "").strip()
    if len(trimmed) < 30:
        raise HTTPException(
            status_code=400,
            detail="正文太短,请粘贴更多内容(至少 30 字)。",
        )
    extracted = ExtractedFile(text=trimmed, source_type="manual")
    doc = await _persist_extracted_document(
        db,
        kb=kb,
        user=user,
        extracted=extracted,
        title=title.strip() or _placeholder_title(),
        source_url=source_url,
    )
    if auto_index:
        doc = await index_document(db, doc, embedding_client=embedding_client)
    return doc


async def reindex_document(
    db: AsyncSession,
    document: KnowledgeDocument,
    *,
    embedding_client: EmbeddingClient | None = None,
) -> KnowledgeDocument:
    """面向 API 的重新索引包装函数。

    router 只依赖 ``knowledge_service``，不用知道重新索引当前是同步执行、后台任务，
    还是未来的队列任务。
    """
    return await _reindex_document_via_indexer(
        db, document, embedding_client=embedding_client,
    )


async def delete_document(
    db: AsyncSession, doc: KnowledgeDocument,
) -> None:
    # knowledge_chunks.document_id 上有 ON DELETE CASCADE，删除文档会自动清掉向量行。
    await db.delete(doc)
    await db.commit()


async def reset_document_chunks(
    db: AsyncSession, doc: KnowledgeDocument,
) -> None:
    """删除某文档所有 chunks，并把索引状态重置为 pending。

    重新索引和手动 UI 操作都会需要这个能力。它保留在 service 层，避免 router 直接懂
    chunks 表结构。
    """
    from sqlalchemy import delete as sa_delete

    await db.execute(
        sa_delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id),
    )
    doc.chunk_count = 0
    doc.status = "pending"
    doc.error_detail = None
    await db.commit()


# ============================================================================
# 内部辅助函数
# ============================================================================


async def _persist_extracted_document(
    db: AsyncSession,
    *,
    kb: KnowledgeBase,
    user: User,
    extracted: ExtractedFile,
    title: str,
    source_url: str | None,
) -> KnowledgeDocument:
    content_hash = hashlib.sha256(extracted.text.encode("utf-8")).hexdigest()

    # 同一用户在同一知识库内上传字节完全一致的文本时，直接返回已有行，避免重复索引。
    # 不同知识库允许重复，因为用户确实会在“公司资料”“项目素材”等库里保存重叠内容。
    existing = (
        await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.user_id == user.id,
                KnowledgeDocument.knowledge_base_id == kb.id,
                KnowledgeDocument.content_hash == content_hash,
            ),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    doc = KnowledgeDocument(
        knowledge_base_id=kb.id,
        user_id=user.id,
        title=title[:512],
        source_type=extracted.source_type,
        source_url=source_url,
        raw_text=extracted.text,
        content_hash=content_hash,
        chunk_count=0,
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


def _derive_title_from_filename(filename: str) -> str:
    sanitised = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    stem = re.sub(r"\.[^.]+$", "", sanitised).strip()
    if stem and stem.lower() not in {"upload", "untitled", "document"}:
        return stem[:512]
    return _placeholder_title()


def _placeholder_title() -> str:
    return f"知识库文档 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
