# 作用：封装售后工单的创建和查询。
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.after_sales import AfterSalesTicket


class AfterSalesRepository:
    """售后工单仓储。

    仓储只做数据库访问，售后分类和建议由 Agent/service 层负责。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **data) -> AfterSalesTicket:
        """创建售后工单。"""
        ticket = AfterSalesTicket(**data)
        self.db.add(ticket)
        await self.db.flush()
        return ticket

    async def list(self, status: str | None = None) -> list[AfterSalesTicket]:
        """查询售后工单，默认按创建时间倒序返回。"""
        stmt = select(AfterSalesTicket).order_by(AfterSalesTicket.created_at.desc())
        if status:
            stmt = stmt.where(AfterSalesTicket.status == status)
        return list((await self.db.scalars(stmt)).all())
