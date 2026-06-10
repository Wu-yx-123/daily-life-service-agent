# 作用：OrderAgent 负责把候选、排班、价格结果合成待确认订单草稿。
from app.schemas.agent import CandidateOption, OrderDraft, PriceOutput, ScheduleOutput


class OrderAgent:
    """订单 Agent：Phase 1 只生成待确认订单草稿。"""

    name = "OrderAgent"

    async def draft(self, *, candidate: CandidateOption, schedule: ScheduleOutput, price: PriceOutput, user_id: str) -> OrderDraft:
        """把匹配、排班和价格结果合并为可确认的订单草稿。"""
        if not schedule.available or not schedule.room_id or not schedule.lock_id or not schedule.appointment_start or not schedule.appointment_end:
            raise ValueError("cannot create order draft without a valid schedule lock")
        return OrderDraft(
            user_id=user_id,
            option_id=candidate.option_id,
            store_id=candidate.store_id,
            service_id=candidate.service_id,
            technician_id=candidate.technician_id,
            room_id=schedule.room_id,
            appointment_start=schedule.appointment_start,
            appointment_end=schedule.appointment_end,
            original_price=price.original_price,
            final_price=price.final_price,
            lock_id=schedule.lock_id,
            price_snapshot=price.price_snapshot,
        )
