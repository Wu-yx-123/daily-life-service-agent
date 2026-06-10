# 作用：封装服务、门店、技师、房间和排班的查询逻辑。
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Room, Service, Store, Technician, TechnicianSchedule


class CatalogRepository:
    """服务、门店、技师、房间和排班的只读仓储。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_active_services(self) -> list[Service]:
        """查询可预约的服务项目。"""
        return list((await self.db.scalars(select(Service).where(Service.status == "active"))).all())

    async def list_active_stores(self) -> list[Store]:
        """查询营业中的门店。"""
        return list((await self.db.scalars(select(Store).where(Store.status == "active"))).all())

    async def list_active_technicians(self, store_id: str | None = None) -> list[Technician]:
        """查询可接单技师，可按门店过滤。"""
        stmt: Select = select(Technician).where(Technician.status == "active")
        if store_id:
            stmt = stmt.where(Technician.store_id == store_id)
        return list((await self.db.scalars(stmt)).all())

    async def list_active_rooms(self, store_id: str) -> list[Room]:
        """查询门店可用房间。"""
        return list((await self.db.scalars(select(Room).where(Room.store_id == store_id, Room.status == "active"))).all())

    async def get_store(self, store_id: str) -> Store | None:
        return await self.db.get(Store, store_id)

    async def get_service(self, service_id: str) -> Service | None:
        return await self.db.get(Service, service_id)

    async def get_technician(self, technician_id: str) -> Technician | None:
        return await self.db.get(Technician, technician_id)

    async def get_room(self, room_id: str) -> Room | None:
        return await self.db.get(Room, room_id)

    async def list_schedules_covering(self, technician_id: str, start: datetime, end: datetime) -> list[TechnicianSchedule]:
        """查询是否存在覆盖整个预约和清洁时间的技师排班。"""
        stmt = select(TechnicianSchedule).where(
            TechnicianSchedule.technician_id == technician_id,
            TechnicianSchedule.status == "available",
            TechnicianSchedule.start_time <= start,
            TechnicianSchedule.end_time >= end,
        )
        return list((await self.db.scalars(stmt)).all())
