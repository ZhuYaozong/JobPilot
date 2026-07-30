"""在 embedding 模型或向量维度迁移后安全批量重建知识库索引。"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import re
import sys

from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.llm.embedding_client import EmbeddingClient
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.user import User
from app.services.knowledge_indexing_service import reindex_document


EXPECTED_BGE_M3_DIMENSIONS = 1024
_VECTOR_TYPE_PATTERN = re.compile(r"^vector\((\d+)\)$")


def parse_vector_dimensions(value: object) -> int:
    """把 PostgreSQL 的 ``vector(n)`` 类型文本解析成维度。"""
    match = _VECTOR_TYPE_PATTERN.fullmatch(str(value or ""))
    if match is None:
        raise RuntimeError(f"无法识别 knowledge_chunks.embedding 类型: {value!r}")
    return int(match.group(1))


async def get_database_dimensions(db: AsyncSession) -> int:
    """读取数据库实际向量列维度，避免配置与 schema 不一致时开始写入。"""
    value = (
        await db.execute(
            text(
                """
                SELECT format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relname = 'knowledge_chunks'
                  AND a.attname = 'embedding'
                  AND NOT a.attisdropped
                """,
            ),
        )
    ).scalar_one_or_none()
    return parse_vector_dimensions(value)


def _document_scope_statement(
    *,
    username: str | None = None,
    include_non_ready: bool = False,
):
    """构造非空文档范围；默认只允许重建此前可用的 ready 文档。"""
    stmt = select(KnowledgeDocument.id).where(
        func.length(func.btrim(KnowledgeDocument.raw_text)) > 0,
    )
    if not include_non_ready:
        stmt = stmt.where(KnowledgeDocument.status == "ready")
    if username is not None:
        stmt = stmt.join(User, User.id == KnowledgeDocument.user_id).where(
            User.username == username,
        )
    return stmt


def _migration_candidate_statement(
    *,
    username: str | None = None,
    include_non_ready: bool = False,
    after_id: int = 0,
):
    """预测维度迁移清空旧向量后，需要重新索引的全部文档。"""
    return _document_scope_statement(
        username=username,
        include_non_ready=include_non_ready,
    ).where(KnowledgeDocument.id > after_id)


def _candidate_statement(
    *,
    username: str | None = None,
    include_non_ready: bool = False,
):
    """选择迁移后缺少完整向量的非空文档。"""
    has_chunk = exists(
        select(KnowledgeChunk.id).where(
            KnowledgeChunk.document_id == KnowledgeDocument.id,
        ),
    )
    has_missing_embedding = exists(
        select(KnowledgeChunk.id).where(
            KnowledgeChunk.document_id == KnowledgeDocument.id,
            KnowledgeChunk.embedding.is_(None),
        ),
    )
    stmt = _document_scope_statement(
        username=username,
        include_non_ready=include_non_ready,
    ).where(
        or_(
            KnowledgeDocument.status != "ready",
            KnowledgeDocument.chunk_count == 0,
            ~has_chunk,
            has_missing_embedding,
        ),
    )
    return stmt


async def count_candidates(
    db: AsyncSession,
    *,
    username: str | None,
    include_non_ready: bool,
    after_id: int,
) -> int:
    """统计本次需要重建的文档数。"""
    subquery = (
        _candidate_statement(
            username=username,
            include_non_ready=include_non_ready,
        )
        .where(KnowledgeDocument.id > after_id)
        .subquery()
    )
    value = (await db.execute(select(func.count()).select_from(subquery))).scalar_one()
    return int(value)


async def count_migration_candidates(
    db: AsyncSession,
    *,
    username: str | None,
    include_non_ready: bool,
    after_id: int,
) -> int:
    """统计迁移会清空旧向量后，需要重建的全部文档数。"""
    subquery = _migration_candidate_statement(
        username=username,
        include_non_ready=include_non_ready,
        after_id=after_id,
    ).subquery()
    value = (await db.execute(select(func.count()).select_from(subquery))).scalar_one()
    return int(value)


async def fetch_candidate_ids(
    db: AsyncSession,
    *,
    username: str | None,
    include_non_ready: bool,
    after_id: int,
    batch_size: int,
) -> list[int]:
    """按主键游标分页，避免重建过程中候选集合变化导致跳页。"""
    rows = (
        await db.execute(
            _candidate_statement(
                username=username,
                include_non_ready=include_non_ready,
            )
            .where(KnowledgeDocument.id > after_id)
            .order_by(KnowledgeDocument.id)
            .limit(batch_size),
        )
    ).scalars().all()
    return [int(value) for value in rows]


async def run_reindex(
    *,
    dry_run: bool,
    username: str | None,
    batch_size: int,
    limit: int | None,
    after_id: int,
    include_non_ready: bool,
    pre_migration_audit: bool,
) -> int:
    """执行预检和顺序重建，返回适合 CLI 的退出码。"""
    async with AsyncSessionLocal() as db:
        database_dimensions = await get_database_dimensions(db)

        if pre_migration_audit:
            if database_dimensions != 1536:
                raise RuntimeError(
                    "迁移前预演要求数据库仍为 vector(1536)，"
                    f"当前为 vector({database_dimensions})",
                )
            total = await count_migration_candidates(
                db,
                username=username,
                include_non_ready=include_non_ready,
                after_id=after_id,
            )
            planned = min(total, limit) if limit is not None else total
            scope = "all statuses" if include_non_ready else "ready only"
            print(
                "Pre-migration dry run: database=vector(1536), "
                f"scope={scope}, after_id={after_id}, "
                f"candidates={total}, planned={planned}",
            )
            print("Migration audit complete; no documents were changed.")
            return 0

        if settings.embedding_dimensions != EXPECTED_BGE_M3_DIMENSIONS:
            raise RuntimeError(
                "EMBEDDING_DIMENSIONS 必须设为 1024 后才能执行 BGE-M3 重建，"
                f"当前为 {settings.embedding_dimensions}",
            )

        if database_dimensions != EXPECTED_BGE_M3_DIMENSIONS:
            raise RuntimeError(
                "数据库仍是 "
                f"vector({database_dimensions})；请先执行 alembic upgrade head",
            )

        client = EmbeddingClient()
        # 在任何数据库写入之前探测端点，并复用客户端自身的严格维度校验。
        probe = await client.embed(["JobPilot BGE-M3 embedding dimension probe"])
        if len(probe) != 1 or len(probe[0]) != EXPECTED_BGE_M3_DIMENSIONS:
            raise RuntimeError("Embedding 端点探测未返回单个 1024 维向量")

        total = await count_candidates(
            db,
            username=username,
            include_non_ready=include_non_ready,
            after_id=after_id,
        )
        planned = min(total, limit) if limit is not None else total
        scope = "all statuses" if include_non_ready else "ready only"
        print(
            "Preflight OK: database=vector(1024), endpoint=1024, "
            f"scope={scope}, after_id={after_id}, "
            f"candidates={total}, planned={planned}",
        )
        if dry_run or planned == 0:
            print("Dry run complete; no documents were changed." if dry_run else "No documents need reindexing.")
            return 0

        succeeded = 0
        failed = 0
        processed = 0
        cursor_id = after_id
        while processed < planned:
            current_batch_size = min(batch_size, planned - processed)
            document_ids = await fetch_candidate_ids(
                db,
                username=username,
                include_non_ready=include_non_ready,
                after_id=cursor_id,
                batch_size=current_batch_size,
            )
            if not document_ids:
                break
            for document_id in document_ids:
                document = (
                    await db.execute(
                        select(KnowledgeDocument).where(
                            KnowledgeDocument.id == document_id,
                        ),
                    )
                ).scalar_one()
                result = await reindex_document(
                    db,
                    document,
                    embedding_client=client,
                )
                processed += 1
                cursor_id = document_id
                if result.status == "ready" and not (
                    result.error_detail or ""
                ).startswith("reindex_failed:"):
                    succeeded += 1
                else:
                    failed += 1
                    print(
                        f"FAILED document_id={document_id}: "
                        f"{result.error_detail or result.status}",
                        file=sys.stderr,
                    )
                print(
                    f"Progress: {processed}/{planned} "
                    f"(succeeded={succeeded}, failed={failed}, "
                    f"last_document_id={cursor_id})",
                )

        print(
            f"Reindex complete: processed={processed}, "
            f"succeeded={succeeded}, failed={failed}, "
            f"last_document_id={cursor_id}",
        )
        return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    def positive_int(value: str) -> int:
        parsed = int(value)
        if parsed <= 0:
            raise argparse.ArgumentTypeError("必须大于 0")
        return parsed

    def non_negative_int(value: str) -> int:
        parsed = int(value)
        if parsed < 0:
            raise argparse.ArgumentTypeError("必须大于等于 0")
        return parsed

    parser = argparse.ArgumentParser(
        description="安全重建 BGE-M3 1024 维知识库向量",
    )
    parser.add_argument("--dry-run", action="store_true", help="只预检和统计，不写数据库")
    parser.add_argument(
        "--pre-migration-audit",
        action="store_true",
        help="在数据库仍为 vector(1536) 时预测迁移后的重建数量；绝不写数据库",
    )
    parser.add_argument("--username", help="只重建指定用户名的数据")
    parser.add_argument("--batch-size", type=positive_int, default=25, help="游标分页大小，默认 25")
    parser.add_argument("--limit", type=positive_int, help="最多处理的文档数，便于灰度验证")
    parser.add_argument(
        "--after-id",
        type=non_negative_int,
        default=0,
        help="只处理大于该文档 ID 的候选项，用于断点续跑",
    )
    parser.add_argument(
        "--include-non-ready",
        action="store_true",
        help="显式扩展到 failed/pending/parsing 文档；默认仅处理 ready 文档",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return asyncio.run(
            run_reindex(
                dry_run=args.dry_run,
                username=args.username,
                batch_size=args.batch_size,
                limit=args.limit,
                after_id=args.after_id,
                include_non_ready=args.include_non_ready,
                pre_migration_audit=args.pre_migration_audit,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — CLI 统一返回安全、简短的失败信息
        print(f"Preflight/reindex failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
