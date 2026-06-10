# 作用：封装运营报表需要的跨表统计查询。
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.after_sales import AfterSalesTicket
from app.models.approval import ApprovalRequest
from app.models.order import Order


class OpsRepository:
    """运营统计仓储。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def order_count(self) -> int:
        """统计已确认订单数量。"""
        return int(await self.db.scalar(select(func.count()).select_from(Order).where(Order.status == "confirmed")) or 0)

    async def revenue_total(self) -> Decimal:
        """统计已确认订单收入。"""
        value = await self.db.scalar(select(func.coalesce(func.sum(Order.final_price), 0)).where(Order.status == "confirmed"))
        return Decimal(value or 0)

    async def open_after_sales_count(self) -> int:
        """统计开放售后工单数量。"""
        return int(await self.db.scalar(select(func.count()).select_from(AfterSalesTicket).where(AfterSalesTicket.status == "open")) or 0)

    async def pending_approval_count(self) -> int:
        """统计待审批请求数量。"""
        return int(await self.db.scalar(select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.status == "pending")) or 0)
