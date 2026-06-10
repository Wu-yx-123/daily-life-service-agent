"""add pgvector semantic memory

Revision ID: 0009_add_pgvector_memory
Revises: 0008_add_user_preferences
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.embeddings import EMBEDDING_DIMENSION
from app.core.types import GUID

revision: str = "0009_add_pgvector_memory"
down_revision: str | None = "0008_add_user_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector 扩展由 pgvector/pgvector:pg16 镜像提供，用来存储和检索语义长期记忆。
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "user_memory_chunks",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # Alembic 没有内置 vector 类型，先建 TEXT，再用原生 SQL 转成 pgvector 列。
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("importance", sa.Numeric(3, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "ALTER TABLE user_memory_chunks "
        f"ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSION}) USING embedding::vector"
    )
    op.create_index("ix_user_memory_chunks_user_type", "user_memory_chunks", ["user_id", "memory_type"])
    # ivfflat 索引用于加速向量相似度查询；数据量小时 PostgreSQL 也可以直接顺序扫描。
    op.execute(
        "CREATE INDEX ix_user_memory_chunks_embedding "
        "ON user_memory_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_memory_chunks_embedding")
    op.drop_index("ix_user_memory_chunks_user_type", table_name="user_memory_chunks")
    op.drop_table("user_memory_chunks")
