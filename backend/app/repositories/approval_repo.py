# 作用：封装人工审批单的创建、查询和决策更新。
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalRequest


class ApprovalRepository:
    """人工审批仓储。

    仓储只负责数据库访问，审批决策的业务语义由 ApprovalGate 和 API 层控制。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **data) -> ApprovalRequest:
        """创建一张待处理审批单。"""
        request = ApprovalRequest(**data)
        self.db.add(request)
        await self.db.flush()
        return request

    async def list(self, status: str | None = None) -> list[ApprovalRequest]:
        """查询审批单，默认返回全部，按创建时间倒序排列。"""
        stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
        if status:
            stmt = stmt.where(ApprovalRequest.status == status)
        return list((await self.db.scalars(stmt)).all())

    async def get(self, approval_id: str) -> ApprovalRequest | None:
        """根据 ID 查询审批单。"""
        return await self.db.get(ApprovalRequest, approval_id)

    async def decide(self, request: ApprovalRequest, *, status: str, reviewer_note: str | None, order_id: str | None = None) -> ApprovalRequest:
        """更新审批结果。"""
        request.status = status
        request.reviewer_note = reviewer_note
        request.order_id = order_id
        request.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.flush()
        return request
