"""Chunk → embed → persist a knowledge document.

State machine driven by ``KnowledgeDocument.status``:

    pending  (just persisted, no chunks yet)
       │
       ▼
    parsing  (this function holds the row in flight)
       │
       ├── on success → ready (chunks written, chunk_count populated)
       └── on failure → failed (error_detail set, old chunks restored to None)

We deliberately keep this synchronous (no celery / RQ) for slice 7'c2 —
typical docs produce <50 chunks → single batched embed call ≈ 1–3 seconds.
If real users complain about waiting on uploads we'll move it behind
FastAPI BackgroundTasks in a follow-up; the contract here doesn't change.

Safety cap: refuse documents whose chunking would produce more than
``MAX_CHUNKS_PER_DOCUMENT`` chunks. Stops a 5 MB Markdown file with no
paragraph breaks from generating thousands of LLM-priced embeddings.
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


# Chunking parameters. 800 / 100 is a reasonable default for mixed CN/EN
# content (Chinese paragraphs ~200 chars; 800 holds 3–4 sentences with
# context). Tune per-deployment via env if real-world docs need it.
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100

# Hard ceiling on chunks per document. A typical resume → ~10 chunks,
# a 30-page company background doc → ~50. 200 leaves room without letting
# a misformatted upload nuke the embedding budget.
MAX_CHUNKS_PER_DOCUMENT = 200


async def index_document(
    db: AsyncSession,
    document: KnowledgeDocument,
    *,
    embedding_client: EmbeddingClient | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> KnowledgeDocument:
    """Run the chunk → embed → insert pipeline for a single document.

    Always commits the final status (ready / failed) so callers can rely on
    the row reflecting reality even if they don't refresh. Raises only on
    programmer errors (bad args); LLM / network failures land in
    status=failed instead of propagating.
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
        # Splitter / chunk-count guards raise ValueError; treat as failed
        # rather than 500.
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
    """Drop the document's existing chunks + re-run indexing from scratch.

    Used by the manual "重新索引" endpoint after a failed run, or after a
    user edits the source text (future slice). Idempotent: safe to call
    repeatedly on the same doc.
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
    """The "real work" middle of index_document, factored out for clarity."""
    text_chunks = split_text(
        document.raw_text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if not text_chunks:
        # Empty content (after whitespace normalisation) — leave the doc in
        # ready state with zero chunks. The user can edit + reindex if this
        # was unexpected.
        await _drop_chunks(db, document)
        return []

    if len(text_chunks) > MAX_CHUNKS_PER_DOCUMENT:
        raise ValueError(
            f"document would produce {len(text_chunks)} chunks "
            f"(cap {MAX_CHUNKS_PER_DOCUMENT}); please split or shorten it.",
        )

    embeddings = await client.embed([c.text for c in text_chunks])
    if len(embeddings) != len(text_chunks):
        # Defensive: EmbeddingClient already validates this, but the cost
        # of a second check here is zero.
        raise ValueError(
            "embedding count mismatch — refusing to write partial chunks",
        )

    # Idempotent: if the doc is being reindexed, drop the previous chunks
    # first so we never end up with overlapping rows from two runs.
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
    """Bulk-delete existing chunks for the document.

    Separate from reindex_document so the failure path in index_document
    can also clean up partial state without falling back to a full reindex.
    """
    await db.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id),
    )


async def _mark_failed(
    db: AsyncSession, document: KnowledgeDocument, detail: str,
) -> KnowledgeDocument:
    """Persist failure state and return the freshly-loaded row.

    Returning the new instance (instead of patching the caller's stale
    one) sidesteps a MissingGreenlet trap: after ``db.rollback()`` every
    ORM instance attached to this session is expired, so any later sync
    ``.attr`` access on the original ``document`` triggers a lazy SELECT
    that has to run inside an async greenlet (which the API serializer
    isn't in). By returning a fully-hydrated replacement we let
    ``index_document`` hand the caller something safe to serialise.

    Same defensive pattern as ``assistant_service._finalize_failed_run``.
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
        # Document was deleted underneath us — nothing left to mark.
        return document
    # Drop any partial chunks the failing path wrote before the exception.
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
