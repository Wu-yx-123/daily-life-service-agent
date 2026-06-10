# 作用：统一管理长期记忆生命周期，包括低价值记忆清理和按用户隐私删除。
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.memory_repo import MemoryRepository
from app.repositories.semantic_memory_repo import SemanticMemoryRepository


@dataclass(frozen=True)
class MemoryRetentionResult:
    """记忆清理结果，脚本和测试都用这个结构输出统计。"""

    structured_preferences: int
    semantic_chunks: int
    dry_run: bool

    @property
    def total(self) -> int:
        return self.structured_preferences + self.semantic_chunks


class MemoryRetentionService:
    """长期记忆清理服务。

    默认策略比较保守：只清理低置信度、低重要性且长期未出现的记忆；
    强偏好和重要语义经验会继续保留。
    """

    def __init__(
        self,
        db: AsyncSession,
        memory_repo: MemoryRepository | None = None,
        semantic_repo: SemanticMemoryRepository | None = None,
    ):
        self.db = db
        self.memory_repo = memory_repo or MemoryRepository(db)
        self.semantic_repo = semantic_repo or SemanticMemoryRepository(db)

    async def prune_stale_memories(
        self,
        *,
        preference_days: int = 90,
        semantic_days: int = 180,
        max_preference_confidence: Decimal = Decimal("0.65"),
        max_semantic_importance: Decimal = Decimal("0.60"),
        user_id: str | None = None,
        dry_run: bool = True,
    ) -> MemoryRetentionResult:
        """清理过期弱记忆。

        dry_run=True 时只统计将被删除的数量，不真正删除，适合 cron 前预览。
        """
        now = datetime.now()
        preference_cutoff = now - timedelta(days=preference_days)
        semantic_cutoff = now - timedelta(days=semantic_days)

        if dry_run:
            structured = await self.memory_repo.count_prunable_preferences(
                older_than=preference_cutoff,
                max_confidence=max_preference_confidence,
                user_id=user_id,
            )
            semantic = await self.semantic_repo.count_prunable_chunks(
                older_than=semantic_cutoff,
                max_importance=max_semantic_importance,
                user_id=user_id,
            )
            return MemoryRetentionResult(structured_preferences=structured, semantic_chunks=semantic, dry_run=True)

        structured = await self.memory_repo.prune_preferences(
            older_than=preference_cutoff,
            max_confidence=max_preference_confidence,
            user_id=user_id,
        )
        semantic = await self.semantic_repo.prune_chunks(
            older_than=semantic_cutoff,
            max_importance=max_semantic_importance,
            user_id=user_id,
        )
        await self.db.commit()
        return MemoryRetentionResult(structured_preferences=structured, semantic_chunks=semantic, dry_run=False)

    async def delete_user_memories(self, *, user_id: str, dry_run: bool = True) -> MemoryRetentionResult:
        """按用户删除全部长期记忆，用于隐私删除或账号注销。"""
        if dry_run:
            structured = len(await self.memory_repo.list_user_preferences(user_id=user_id, min_confidence=Decimal("0"), limit=10000))
            semantic = await self.semantic_repo.count_prunable_chunks(
                older_than=datetime.now() + timedelta(days=1),
                max_importance=Decimal("100.00"),
                user_id=user_id,
            )
            return MemoryRetentionResult(structured_preferences=structured, semantic_chunks=semantic, dry_run=True)

        structured = await self.memory_repo.delete_user_preferences(user_id=user_id)
        semantic = await self.semantic_repo.delete_user_chunks(user_id=user_id)
        await self.db.commit()
        return MemoryRetentionResult(structured_preferences=structured, semantic_chunks=semantic, dry_run=False)
