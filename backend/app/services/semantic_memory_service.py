# 作用：语义长期记忆服务，负责生成自然语言记忆摘要、向量化并通过 pgvector 召回。
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import EmbeddingService
from app.repositories.semantic_memory_repo import SemanticMemoryRepository
from app.schemas.agent import IntentOutput


class SemanticMemoryService:
    """用户私有语义记忆服务。

    结构化偏好适合保存“字段型事实”，语义记忆适合保存“自然语言经验”，例如身体状态、
    房间偏好、服务体验和投诉细节。所有召回都按 user_id 隔离。
    """

    def __init__(
        self,
        db: AsyncSession,
        repo: SemanticMemoryRepository | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.db = db
        self.repo = repo or SemanticMemoryRepository(db)
        self.embedding_service = embedding_service or EmbeddingService()

    async def retrieve_for_user(self, *, user_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """根据当前用户消息召回相关语义记忆。"""
        query_embedding = await self.embedding_service.embed_query(query)
        rows = await self.repo.search(user_id=user_id, query_embedding=query_embedding, limit=limit)
        return [
            {
                "memory_type": row["memory_type"],
                "content": row["content"],
                "score": float(row["score"] or 0),
                "source": row["source"],
                "evidence": row["evidence"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ]

    async def record_booking_memory(
        self,
        *,
        user_id: str,
        state: dict[str, Any],
        order_id: str | None = None,
    ) -> None:
        """在预约确认后写入一条自然语言语义记忆。"""
        content = _booking_memory_content(state)
        if not content:
            return
        embedding = await self.embedding_service.embed_query(content)
        await self.repo.add_chunk(
            user_id=user_id,
            memory_type="booking_experience",
            content=content,
            embedding=embedding,
            source="booking_confirmed",
            evidence={
                "trace_id": state.get("trace_id"),
                "session_id": state.get("session_id"),
                "order_id": order_id,
                "message": state.get("user_message"),
            },
            importance=Decimal("0.70"),
        )
        await self.db.commit()


def _booking_memory_content(state: dict[str, Any]) -> str:
    """从已确认预约状态中生成适合向量检索的自然语言摘要。"""
    intent_raw = state.get("intent") or {}
    selected = state.get("selected_option") or {}
    draft = state.get("order_draft") or {}
    intent = IntentOutput.model_validate(intent_raw) if intent_raw else None

    parts: list[str] = []
    if intent and intent.slots.service_type:
        parts.append(f"用户确认预约过{intent.slots.service_type}")
    elif selected.get("service_name"):
        parts.append(f"用户确认预约过{selected['service_name']}")
    if intent and intent.slots.strength_preference:
        parts.append(f"用户偏好力度为{intent.slots.strength_preference}")
    if intent and intent.slots.budget_max:
        parts.append(f"用户预算上限约为{intent.slots.budget_max}")
    if selected.get("technician_name"):
        parts.append(f"用户本次选择技师{selected['technician_name']}")
    if draft.get("appointment_start"):
        parts.append(f"用户本次预约时间为{draft['appointment_start']}")
    message = state.get("user_message")
    if message:
        parts.append(f"用户原始表达：{message}")
    return "；".join(parts)
