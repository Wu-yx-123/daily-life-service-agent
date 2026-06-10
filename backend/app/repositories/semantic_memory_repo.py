# 作用：封装 pgvector 语义长期记忆的写入和相似度召回。
from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import vector_to_pg_literal


class SemanticMemoryRepository:
    """用户语义记忆仓储。

    这里使用原生 SQL，是因为 pgvector 的距离操作符 `<=>` 和 vector 类型转换
    比 ORM 表达式更直接，也避免引入额外 Python 依赖。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_chunk(
        self,
        *,
        user_id: str,
        memory_type: str,
        content: str,
        embedding: list[float],
        source: str,
        evidence: dict[str, Any] | None = None,
        importance: Decimal = Decimal("0.60"),
    ) -> dict[str, Any]:
        """写入一条语义记忆片段。"""
        chunk_id = uuid.uuid4()
        stmt = text(
            """
            INSERT INTO user_memory_chunks
                (id, user_id, memory_type, content, embedding, source, evidence, importance)
            VALUES
                (:id, :user_id, :memory_type, :content, CAST(:embedding AS vector),
                 :source, CAST(:evidence AS JSON), :importance)
            RETURNING id, user_id, memory_type, content, source, evidence, importance, created_at
            """
        )
        row = (await self.db.execute(stmt, {
            "id": chunk_id,
            "user_id": _to_uuid(user_id),
            "memory_type": memory_type,
            "content": content,
            "embedding": vector_to_pg_literal(embedding),
            "source": source,
            "evidence": json.dumps(evidence or {}, ensure_ascii=False),
            "importance": importance,
        })).mappings().one()
        return dict(row)

    async def search(
        self,
        *,
        user_id: str,
        query_embedding: list[float],
        memory_type: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """按向量相似度召回当前用户的语义记忆。"""
        where_type = "AND memory_type = :memory_type" if memory_type else ""
        stmt = text(
            f"""
            SELECT
                id, user_id, memory_type, content, source, evidence, importance, created_at,
                1 - (embedding <=> CAST(:query_embedding AS vector)) AS score
            FROM user_memory_chunks
            WHERE user_id = :user_id
            {where_type}
            ORDER BY embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
            """
        )
        params: dict[str, Any] = {
            "user_id": _to_uuid(user_id),
            "query_embedding": vector_to_pg_literal(query_embedding),
            "limit": limit,
        }
        if memory_type:
            params["memory_type"] = memory_type
        rows = (await self.db.execute(stmt, params)).mappings().all()
        return [dict(row) for row in rows]

    async def count_prunable_chunks(
        self,
        *,
        older_than,
        max_importance: Decimal,
        user_id: str | None = None,
    ) -> int:
        """统计可清理的低重要性语义记忆。"""
        where_user = "AND user_id = :user_id" if user_id else ""
        stmt = text(
            f"""
            SELECT count(*) AS count
            FROM user_memory_chunks
            WHERE created_at < :older_than
              AND importance < :max_importance
              {where_user}
            """
        )
        params: dict[str, Any] = {"older_than": older_than, "max_importance": max_importance}
        if user_id:
            params["user_id"] = _to_uuid(user_id)
        return int((await self.db.execute(stmt, params)).scalar_one())

    async def prune_chunks(
        self,
        *,
        older_than,
        max_importance: Decimal,
        user_id: str | None = None,
    ) -> int:
        """删除长期保存且重要性较低的 pgvector 语义记忆。"""
        where_user = "AND user_id = :user_id" if user_id else ""
        stmt = text(
            f"""
            DELETE FROM user_memory_chunks
            WHERE created_at < :older_than
              AND importance < :max_importance
              {where_user}
            """
        )
        params: dict[str, Any] = {"older_than": older_than, "max_importance": max_importance}
        if user_id:
            params["user_id"] = _to_uuid(user_id)
        result = await self.db.execute(stmt, params)
        return int(result.rowcount or 0)

    async def delete_user_chunks(self, *, user_id: str) -> int:
        """隐私删除：删除某个用户的全部语义长期记忆。"""
        result = await self.db.execute(
            text("DELETE FROM user_memory_chunks WHERE user_id = :user_id"),
            {"user_id": _to_uuid(user_id)},
        )
        return int(result.rowcount or 0)


def _to_uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
