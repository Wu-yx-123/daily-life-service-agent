# 作用：封装订单写入逻辑，确保确认预约前再次检查数据库冲突。
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.order_repo import OrderRepository
from app.schemas.agent import OrderDraft


class OrderService:
    """订单写服务。

    Agent 不能直接写订单；确认预约时必须通过这里做事务层冲突复查。
    """

    def __init__(self, db: AsyncSession, order_repo: OrderRepository):
        self.db = db
        self.order_repo = order_repo

    async def create_confirmed_order(self, *, user_id: str, draft: OrderDraft):
        """基于用户确认后的订单草稿创建正式订单。"""
        # 即使 ScheduleAgent 已经创建过时间锁，写订单前仍要查数据库。
        # 这是最后一道防线，用来挡住并发确认、接口重试或锁失效造成的重复预约。
        conflicts = await self.order_repo.list_overlapping_orders(
            technician_id=draft.technician_id,
            room_id=draft.room_id,
            start=draft.appointment_start.replace(tzinfo=None),
            end=draft.appointment_end.replace(tzinfo=None),
        )
        if conflicts:
            raise ValueError("time slot already occupied")
        # 订单价格来自后端草稿中的价格快照，不接受前端自行提交价格。
        order = await self.order_repo.create(
            user_id=user_id,
            store_id=draft.store_id,
            service_id=draft.service_id,
            technician_id=draft.technician_id,
            room_id=draft.room_id,
            appointment_start=draft.appointment_start.replace(tzinfo=None),
            appointment_end=draft.appointment_end.replace(tzinfo=None),
            original_price=Decimal(draft.original_price),
            final_price=Decimal(draft.final_price),
            status="confirmed",
            source="agent",
        )
        await self.db.commit()
        return order
