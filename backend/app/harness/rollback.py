# 作用：实现失败回滚动作，当前主要负责释放预约临时时间锁。
from app.core.redis import TimeLockStore
from app.schemas.agent import CandidateOption, OrderDraft, ScheduleOutput


class RollbackManager:
    """回滚管理器。

    Phase 2 先覆盖时间锁释放；后续可扩展订单撤销、审批单状态回滚和通知补偿。
    """

    def __init__(self, lock_store: TimeLockStore):
        self.lock_store = lock_store

    async def release_time_lock(self, draft: OrderDraft | None) -> None:
        """释放订单草稿占用的临时时间锁。"""
        if not draft:
            return
        await self.lock_store.release(
            store_id=draft.store_id,
            technician_id=draft.technician_id,
            start_time=draft.appointment_start.replace(tzinfo=None).isoformat(),
        )

    async def release_schedule_lock(self, *, candidate: CandidateOption | None, schedule: ScheduleOutput | None) -> None:
        """释放排班检查阶段创建的临时时间锁。"""
        if not candidate or not schedule or not schedule.appointment_start:
            return
        await self.lock_store.release(
            store_id=candidate.store_id,
            technician_id=candidate.technician_id,
            start_time=schedule.appointment_start.replace(tzinfo=None).isoformat(),
        )
