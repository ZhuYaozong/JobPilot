"""创建 knowledge_bases / documents / chunks 表（RAG 7'c1）

修订 ID: b71f4c8a92e1
上一修订: adee26c60e7e
创建时间: 2026-05-13 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import settings


# Alembic 使用的修订标识。
revision: str = "b71f4c8a92e1"
down_revision: Union[str, Sequence[str], None] = "adee26c60e7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """启用 pgvector，并创建三张 RAG 表。

    embedding 列的维度会在迁移运行时读取 settings.embedding_dimensions。
    新环境跑迁移前要先固定这个值，确保列维度与该环境使用的 embedding 模型一致。
    如果后续要改维度，需要再补一条迁移。
    """
    # 托管 Postgres（Neon、Supabase）可能已经启用了扩展，这条语句保持幂等。
    # 裸 RDS 上运行 alembic 的角色需要数据库级 ``CREATE`` 权限，部署说明里要标清楚。
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_bases_user_id"),
        "knowledge_bases",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("extra_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_documents_knowledge_base_id"),
        "knowledge_documents",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_user_id"),
        "knowledge_documents",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_content_hash"),
        "knowledge_documents",
        ["content_hash"],
        unique=False,
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # 创建时允许 embedding 为空：7'c1 只做数据层，会先写入没有 embedding 的 chunks。
        # 7'c2 再通过索引服务回填。可空也方便失败后 reset+reindex，而不用删除整行。
        sa.Column(
            "embedding",
            Vector(settings.embedding_dimensions),
            nullable=True,
        ),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("extra_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_chunks_document_id"),
        "knowledge_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_chunks_user_id"),
        "knowledge_chunks",
        ["user_id"],
        unique=False,
    )
    # HNSW 向量索引用于快速 ANN 检索。cosine_ops 对应当前目标相似度指标；
    # 多数 provider 会输出 L2-normalized embedding，此时 cosine 与 inner-product 排序一致，
    # 但如果归一化有漂移，cosine 更宽容。
    # m=16 / ef_construction=64 是 pgvector 默认值，按当前预估量级
    #（单用户 <100k chunks）够用，后续有需要再调参。
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)",
    )


def downgrade() -> None:
    """降级 schema。"""
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.drop_index(
        op.f("ix_knowledge_chunks_user_id"), table_name="knowledge_chunks",
    )
    op.drop_index(
        op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks",
    )
    op.drop_table("knowledge_chunks")

    op.drop_index(
        op.f("ix_knowledge_documents_content_hash"),
        table_name="knowledge_documents",
    )
    op.drop_index(
        op.f("ix_knowledge_documents_user_id"),
        table_name="knowledge_documents",
    )
    op.drop_index(
        op.f("ix_knowledge_documents_knowledge_base_id"),
        table_name="knowledge_documents",
    )
    op.drop_table("knowledge_documents")

    op.drop_index(
        op.f("ix_knowledge_bases_user_id"),
        table_name="knowledge_bases",
    )
    op.drop_table("knowledge_bases")
    # 这里刻意不删除 vector 扩展，部分降级后其他代码仍可能依赖它。
