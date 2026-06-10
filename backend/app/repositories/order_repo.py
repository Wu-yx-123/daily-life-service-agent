# 作用：封装订单查询和创建，尤其是时间段冲突查询。
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


class OrderRepository:
    """订单仓储。

    写操作仍由 OrderService 编排，仓储只负责最小数据库访问。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_overlapping_orders(self, *, technician_id: str | None = None, room_id: str | None = None, start: datetime, end: datetime) -> list[Order]:
        """查询同一技师或房间在目标时间段内的重叠订单。"""
        stmt = select(Order).where(
            Order.status.in_(["confirmed", "pending"]),
            Order.appointment_start < end,
            Order.appointment_end > start,
        )
        if technician_id and room_id:
            stmt = stmt.where(or_(Order.technician_id == technician_id, Order.room_id == room_id))
        elif technician_id:
            stmt = stmt.where(Order.technician_id == technician_id)
        elif room_id:
            stmt = stmt.where(Order.room_id == room_id)
        return list((await self.db.scalars(stmt)).all())

    async def create(self, **data) -> Order:
        """创建订单记录；提交事务由 service 层统一控制。"""
        order = Order(**data)
        self.db.add(order)
        await self.db.flush()
        return order
