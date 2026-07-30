"""将知识库向量维度迁移到 BGE-M3 的 1024 维

修订 ID: e8f3a1c9d204
上一修订: d4a7c9e2b610
创建时间: 2026-07-30 10:00:00.000000
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e8f3a1c9d204"
down_revision: Union[str, Sequence[str], None] = "d4a7c9e2b610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VECTOR_TYPE_PATTERN = re.compile(r"^vector\((\d+)\)$")
_INDEX_NAME = "ix_knowledge_chunks_embedding_hnsw"


def _current_dimensions() -> int:
    """读取数据库真实列类型，拒绝在未知 schema 上猜测迁移。"""
    value = op.get_bind().execute(
        sa.text(
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
    ).scalar_one_or_none()
    match = _VECTOR_TYPE_PATTERN.fullmatch(str(value or ""))
    if match is None:
        raise RuntimeError(
            "knowledge_chunks.embedding 必须是带固定维度的 pgvector 列，"
            f"实际类型为 {value!r}",
        )
    return int(match.group(1))


def _create_hnsw_index() -> None:
    """使用与原索引一致的 cosine HNSW 参数，支持幂等恢复。"""
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {_INDEX_NAME} "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)",
    )


def _change_dimensions(*, source: int, target: int) -> None:
    """清空不可复用的旧向量后修改固定维度，并重建 ANN 索引。"""
    current = _current_dimensions()
    if current == target:
        _create_hnsw_index()
        return
    if current != source:
        raise RuntimeError(
            "拒绝迁移未知向量维度: "
            f"expected vector({source}) or vector({target}), got vector({current})",
        )

    op.execute(f"DROP INDEX IF EXISTS {_INDEX_NAME}")
    # 不同维度的 embedding 不能截断或补零复用；保留 chunk 文本供 BM25 和批量重建使用。
    op.execute(
        "UPDATE knowledge_chunks SET embedding = NULL "
        "WHERE embedding IS NOT NULL",
    )
    op.execute(
        "ALTER TABLE knowledge_chunks "
        f"ALTER COLUMN embedding TYPE vector({target}) "
        f"USING NULL::vector({target})",
    )
    _create_hnsw_index()


def upgrade() -> None:
    """从旧 1536 维迁移到 BGE-M3 的 1024 维。"""
    _change_dimensions(source=1536, target=1024)


def downgrade() -> None:
    """仅回滚 schema 到 1536 维；旧向量不可恢复，仍需重新索引。"""
    _change_dimensions(source=1024, target=1536)
