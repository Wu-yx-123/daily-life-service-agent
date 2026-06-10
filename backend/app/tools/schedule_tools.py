# 作用：排班查询和时间锁工具，供 ScheduleAgent 调用。
# 工具函数保持无状态，所有业务逻辑仍在 ScheduleService 中。
from datetime import datetime

from app.core.redis import TimeLockStore
from app.repositories.catalog_repo import CatalogRepository
from app.repositories.order_repo import OrderRepository
from app.schemas.agent import CandidateOption, ScheduleOutput


async def check_schedule(
    *,
    catalog_repo: CatalogRepository,
    order_repo: OrderRepository,
    lock_store: TimeLockStore,
    candidate: dict,
    preferred_time: str,
    user_id: str,
    trace_id: str,
    **kwargs,
) -> ScheduleOutput:
    """检查候选方案的时间可用性并创建临时时间锁。

    此工具是 ScheduleAgent 的确定性执行体：
    1. 校验营业时间、技师排班、订单冲突、房间冲突
    2. 有空闲时创建 Redis 时间锁
    3. 返回结构化 ScheduleOutput
    """
    from app.services.schedule_service import ScheduleService

    parsed_candidate = CandidateOption.model_validate(candidate)
    parsed_time = datetime.fromisoformat(preferred_time)

    service = ScheduleService(catalog_repo, order_repo, lock_store)
    return await service.check_and_lock(
        candidate=parsed_candidate,
        preferred_time=parsed_time,
        user_id=user_id,
        trace_id=trace_id,
    )


async def create_time_lock(
    *,
    lock_store: TimeLockStore,
    store_id: str,
    technician_id: str,
    start_time: str,
    user_id: str,
    trace_id: str,
    **kwargs,
) -> dict:
    """为指定技师在指定时间创建临时锁。"""
    from uuid import uuid4

    lock_id = f"lock_{uuid4().hex[:12]}"
    acquired = await lock_store.acquire(
        store_id=store_id,
        technician_id=technician_id,
        start_time=start_time,
        payload={"lock_id": lock_id, "user_id": user_id, "trace_id": trace_id},
    )
    return {"lock_id": lock_id, "acquired": acquired}


async def release_time_lock(
    *,
    lock_store: TimeLockStore,
    store_id: str,
    technician_id: str,
    start_time: str,
    **kwargs,
) -> dict:
    """释放指定技师在指定时间的临时锁。"""
    await lock_store.release(
        store_id=store_id,
        technician_id=technician_id,
        start_time=start_time,
    )
    return {"released": True}
