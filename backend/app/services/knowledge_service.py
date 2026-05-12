"""Business logic for knowledge bases and their documents.

Kept separate from the API layer so future entry points (agent tool,
batch import job) can reuse the same CRUD + ownership checks without
re-implementing them. The API layer is responsible only for HTTP shape
translation.

Slice 7'c1 deliberately stops at "document text persisted, status =
pending". Chunking + embedding live in slice 7'c2; see ``knowledge_chunks``
table comment for the indexing state machine.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.user import User
from app.services.file_text_extractor import (
    ExtractedFile,
    FileExtractionError,
    extract_text_from_upload,
)


# ============================================================================
# Knowledge base CRUD
# ============================================================================


async def list_knowledge_bases(
    db: AsyncSession,
    user: User,
    *,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[tuple[KnowledgeBase, int]]:
    """Return ``(kb, document_count)`` pairs scoped to the user.

    Recent-first by updated_at; archived KBs hidden by default but kept
    accessible via the include_archived flag for the admin / cleanup UI.
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

    # Single round-trip for counts — N+1 here would be embarrassing.
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
    """Cascade delete: documents + chunks both have ON DELETE CASCADE so
    a single DELETE on the parent walks the whole tree. We still load+delete
    via the ORM (not a raw SQL delete) so SQLAlchemy event hooks fire if/when
    we add them later."""
    await db.delete(kb)
    await db.commit()


# ============================================================================
# Document CRUD
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


async def upload_document(
    db: AsyncSession,
    *,
    kb: KnowledgeBase,
    user: User,
    filename: str,
    content_type: str | None,
    payload: bytes,
    title_override: str | None = None,
) -> KnowledgeDocument:
    """Extract text from an uploaded file and persist a pending document.

    Indexing (chunking + embedding + vector write) is the next slice's job.
    This function intentionally returns once the row hits the DB so the UI
    can show progress on the document list independently of the indexing
    worker.
    """
    try:
        extracted = extract_text_from_upload(filename, content_type, payload)
    except FileExtractionError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc

    return await _persist_extracted_document(
        db,
        kb=kb,
        user=user,
        extracted=extracted,
        title=title_override or _derive_title_from_filename(filename),
        source_url=None,
    )


async def create_manual_document(
    db: AsyncSession,
    *,
    kb: KnowledgeBase,
    user: User,
    title: str,
    body: str,
    source_url: str | None,
) -> KnowledgeDocument:
    """Counterpart to upload_document for the "粘贴文本" entry point.

    Mirrors the resume "manual paste" path: useful when the user wants to
    capture a note that doesn't live in a file (e.g. interviewer feedback).
    """
    trimmed = (body or "").strip()
    if len(trimmed) < 30:
        raise HTTPException(
            status_code=400,
            detail="正文太短,请粘贴更多内容(至少 30 字)。",
        )
    extracted = ExtractedFile(text=trimmed, source_type="manual")
    return await _persist_extracted_document(
        db,
        kb=kb,
        user=user,
        extracted=extracted,
        title=title.strip() or _placeholder_title(),
        source_url=source_url,
    )


async def delete_document(
    db: AsyncSession, doc: KnowledgeDocument,
) -> None:
    # ON DELETE CASCADE on knowledge_chunks.document_id removes the
    # embeddings too — no manual fan-out needed.
    await db.delete(doc)
    await db.commit()


async def reset_document_chunks(
    db: AsyncSession, doc: KnowledgeDocument,
) -> None:
    """Drop all chunks for a document and reset it to pending.

    Used by the future reindex path (7'c2 or a manual UI action). We keep
    this helper in 7'c1 so the data layer is fully usable from the start.
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
# Internals
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

    # Duplicate detection: if the same user already uploaded byte-identical
    # text into the same KB, return the existing row instead of creating a
    # duplicate. (Different KBs are allowed; users genuinely use "公司资料"
    # and "项目素材" with overlap.)
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
