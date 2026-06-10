# 作用：封装用户长期偏好的查询和更新。
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import UserPreference


class MemoryRepository:
    """长期记忆仓储。

    写入使用“查询后更新/插入”的方式，保持逻辑清晰，也方便测试环境直接 create_all。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_user_preferences(
        self,
        *,
        user_id: str,
        min_confidence: Decimal = Decimal("0.50"),
        limit: int = 20,
    ) -> list[UserPreference]:
        # PostgreSQL UUID 列需要 UUID 对象；API/Agent 层通常传字符串，所以仓储入口统一转换。
        uid = _to_uuid(user_id)
        # 只召回达到最低置信度的偏好，避免把噪声记忆注入 Agent 上下文。
        stmt = (
            select(UserPreference)
            .where(UserPreference.user_id == uid, UserPreference.confidence >= min_confidence)
            # 优先返回高置信度、最近出现的偏好，供 MemoryService 生成 defaults。
            .order_by(UserPreference.confidence.desc(), UserPreference.last_seen_at.desc())
            .limit(limit)
        )
        return list((await self.db.scalars(stmt)).all())

    async def upsert_preference(
        self,
        *,
        user_id: str,
        preference_type: str,
        preference_value: str,
        source: str,
        evidence: dict[str, Any] | None = None,
        base_confidence: Decimal = Decimal("0.55"),
    ) -> UserPreference:
        # upsert 前先做 UUID 归一化，避免不同调用方传入类型不一致。
        uid = _to_uuid(user_id)
        stmt = select(UserPreference).where(
            UserPreference.user_id == uid,
            UserPreference.preference_type == preference_type,
            UserPreference.preference_value == preference_value,
        )
        existing = await self.db.scalar(stmt)
        now = datetime.now()
        if existing:
            # 同一偏好重复出现时不新建记录，而是增强置信度和出现次数。
            existing.seen_count += 1
            existing.confidence = min(Decimal("0.95"), Decimal(existing.confidence) + Decimal("0.10"))
            existing.source = source
            existing.evidence = evidence
            existing.last_seen_at = now
            return existing

        # 新偏好以较低置信度写入，后续重复确认后再逐步变成强偏好。
        pref = UserPreference(
            user_id=uid,
            preference_type=preference_type,
            preference_value=preference_value,
            confidence=base_confidence,
            seen_count=1,
            source=source,
            evidence=evidence,
        )
        self.db.add(pref)
        await self.db.flush()
        return pref

    async def count_prunable_preferences(
        self,
        *,
        older_than: datetime,
        max_confidence: Decimal,
        user_id: str | None = None,
    ) -> int:
        """统计可清理的低置信度结构化偏好。"""
        stmt = select(UserPreference).where(
            UserPreference.last_seen_at < older_than,
            UserPreference.confidence < max_confidence,
        )
        if user_id:
            stmt = stmt.where(UserPreference.user_id == _to_uuid(user_id))
        return len((await self.db.scalars(stmt)).all())

    async def prune_preferences(
        self,
        *,
        older_than: datetime,
        max_confidence: Decimal,
        user_id: str | None = None,
    ) -> int:
        """删除长期未出现且置信度较低的结构化偏好。"""
        stmt = delete(UserPreference).where(
            UserPreference.last_seen_at < older_than,
            UserPreference.confidence < max_confidence,
        )
        if user_id:
            stmt = stmt.where(UserPreference.user_id == _to_uuid(user_id))
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)

    async def delete_user_preferences(self, *, user_id: str) -> int:
        """隐私删除：删除某个用户的全部结构化长期记忆。"""
        result = await self.db.execute(delete(UserPreference).where(UserPreference.user_id == _to_uuid(user_id)))
        return int(result.rowcount or 0)


def _to_uuid(value: str | uuid.UUID) -> uuid.UUID:
    """把 API 层传入的字符串 user_id 统一转换为 PostgreSQL UUID 类型。"""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
