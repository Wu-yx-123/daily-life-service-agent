# 作用：校验预约时间、技师排班、房间冲突，并创建 Redis 临时时间锁。
from datetime import datetime, time, timedelta
from uuid import uuid4

from app.core.redis import TimeLockStore
from app.repositories.catalog_repo import CatalogRepository
from app.repositories.order_repo import OrderRepository
from app.schemas.agent import CandidateOption, ScheduleOutput


class ScheduleService:
    """排班与时间锁服务。

    Phase 1 会校验营业时间、技师排班、订单冲突和房间冲突，并创建 Redis 临时锁。
    """

    cleanup_minutes = 10

    def __init__(self, catalog_repo: CatalogRepository, order_repo: OrderRepository, lock_store: TimeLockStore):
        self.catalog_repo = catalog_repo
        self.order_repo = order_repo
        self.lock_store = lock_store

    async def check_and_lock(self, *, candidate: CandidateOption, preferred_time: datetime, user_id: str, trace_id: str) -> ScheduleOutput:
        """检查候选方案是否可约，成功时锁定该技师的目标开始时间。"""
        service = await self.catalog_repo.get_service(candidate.service_id)
        store = await self.catalog_repo.get_store(candidate.store_id)
        if not service or not store:
            return ScheduleOutput(available=False, reason="服务或门店不存在")

        # 数据库中统一保存 naive datetime，避免 SQLite 测试和 PostgreSQL Demo 行为不一致。
        appointment_start = preferred_time.replace(tzinfo=None)
        appointment_end = appointment_start + timedelta(minutes=service.duration_minutes)
        cleanup_end = appointment_end + timedelta(minutes=self.cleanup_minutes)

        # 服务结束后预留清洁时间，清洁结束也不能超过门店营业时间。
        # closing_time=23:59:59 表示“营业到当天24点”，允许清洁时间落到次日00:10以内。
        closing_at = datetime.combine(appointment_start.date(), store.closing_time)
        if store.closing_time >= time(23, 59):
            closing_at = datetime.combine(appointment_start.date() + timedelta(days=1), time(0, 10))
        if appointment_start.time() < store.opening_time or cleanup_end > closing_at:
            return ScheduleOutput(available=False, reason="预约时间不在门店营业时间内")

        schedules = await self.catalog_repo.list_schedules_covering(candidate.technician_id, appointment_start, cleanup_end)
        if not schedules:
            return ScheduleOutput(available=False, reason="技师该时间段未排班")

        # 先查技师冲突：同一技师同一时间只能服务一个订单。
        tech_conflicts = await self.order_repo.list_overlapping_orders(
            technician_id=candidate.technician_id, start=appointment_start, end=cleanup_end
        )
        if tech_conflicts:
            return ScheduleOutput(available=False, reason="技师该时间段已被预约")

        # 按可用房间逐个尝试；只要有一个房间空闲，就可以生成方案。
        for room in await self.catalog_repo.list_active_rooms(candidate.store_id):
            room_conflicts = await self.order_repo.list_overlapping_orders(room_id=str(room.id), start=appointment_start, end=cleanup_end)
            if room_conflicts:
                continue
            lock_id = f"lock_{uuid4().hex[:12]}"
            acquired = await self.lock_store.acquire(
                store_id=candidate.store_id,
                technician_id=candidate.technician_id,
                start_time=appointment_start.isoformat(),
                payload={"lock_id": lock_id, "user_id": user_id, "trace_id": trace_id},
            )
            if acquired:
                # 锁成功后才把方案暴露给用户，避免两个用户同时拿到同一技师同一时段。
                return ScheduleOutput(
                    available=True,
                    room_id=str(room.id),
                    lock_id=lock_id,
                    appointment_start=appointment_start,
                    appointment_end=appointment_end,
                    cleanup_end=cleanup_end,
                )
        return ScheduleOutput(available=False, reason="房间该时间段已被占用")
