# 作用：测试排班服务对技师冲突和时间锁的处理。
from datetime import datetime

from app.repositories.catalog_repo import CatalogRepository
from app.repositories.order_repo import OrderRepository
from app.schemas.agent import CandidateOption, IntentOutput, OrderDraft
from app.services.match_service import MatchService
from app.services.order_service import OrderService
from app.services.price_service import PriceService
from app.services.schedule_service import ScheduleService


async def test_schedule_conflict_should_fail(db_session, memory_lock_store):
    """同一技师同一时间已有订单时，排班检查必须返回不可用。"""
    preferred_time = datetime.combine(datetime.now().date(), datetime.strptime("20:00", "%H:%M").time())
    catalog_repo = CatalogRepository(db_session)
    order_repo = OrderRepository(db_session)
    match = await MatchService(catalog_repo).match(
        intent=IntentOutput.model_validate(
            {
                "task_type": "book_appointment",
                "slots": {"service_type": "肩颈按摩", "duration_minutes": 90, "preferred_time": preferred_time.isoformat(), "budget_max": "300", "strength_preference": "heavy"},
                "missing_slots": [],
                "confidence": 0.9,
            }
        )
    )
    candidate = match.candidates[0]
    price = await PriceService(catalog_repo).calculate(service_id=candidate.service_id, user_id="00000000-0000-0000-0000-000000000001")
    first = await ScheduleService(catalog_repo, order_repo, memory_lock_store).check_and_lock(
        candidate=candidate, preferred_time=preferred_time, user_id="00000000-0000-0000-0000-000000000001", trace_id="trace_1"
    )
    await OrderService(db_session, order_repo).create_confirmed_order(
        user_id="00000000-0000-0000-0000-000000000001",
        draft=OrderDraft(
            user_id="00000000-0000-0000-0000-000000000001",
            option_id=candidate.option_id,
            store_id=candidate.store_id,
            service_id=candidate.service_id,
            technician_id=candidate.technician_id,
            room_id=first.room_id,
            appointment_start=first.appointment_start,
            appointment_end=first.appointment_end,
            original_price=price.original_price,
            final_price=price.final_price,
            lock_id=first.lock_id,
            price_snapshot=price.price_snapshot,
        ),
    )

    second = await ScheduleService(catalog_repo, order_repo, memory_lock_store).check_and_lock(
        candidate=CandidateOption.model_validate(candidate.model_dump()),
        preferred_time=preferred_time,
        user_id="00000000-0000-0000-0000-000000000002",
        trace_id="trace_2",
    )

    assert second.available is False
    assert "技师" in second.reason
