# 作用：验证预约信息不完整时，Orchestrator 会明确说明缺少哪些信息。
from datetime import datetime, timedelta

from app.harness.orchestrator import _build_intent_followup, _merge_booking_intent_with_previous
from app.schemas.agent import IntentOutput, IntentSlots


def test_intent_followup_should_list_missing_slots_and_invalid_time():
    """缺少时长且预约时间太近时，追问必须明确给出可补充项。"""
    intent = IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(
            service_type="肩颈按摩",
            preferred_time=datetime.now() + timedelta(minutes=5),
            strength_preference="heavy",
        ),
        missing_slots=["duration_minutes"],
        confidence=0.9,
    )

    followup = _build_intent_followup(
        intent,
        [
            {
                "code": "missing_slot",
                "slot": "duration_minutes",
            },
            {
                "code": "appointment_time_too_soon",
                "min_advance_minutes": 30,
            },
        ],
    )

    assert "服务时长" in followup
    assert "60分钟" in followup
    assert "至少提前30分钟" in followup


def test_booking_intent_should_merge_previous_slots_for_followup_answer():
    """用户第二轮只补充时间时，应继承上一轮已说过的服务类型和时长。"""
    previous = IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(
            service_type="肩颈按摩",
            duration_minutes=60,
            strength_preference="heavy",
        ),
        missing_slots=["preferred_time"],
        confidence=0.9,
    )
    current = IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(preferred_time=datetime(2026, 6, 10, 8, 0)),
        missing_slots=["service_type", "duration_minutes"],
        confidence=0.75,
    )

    merged = _merge_booking_intent_with_previous(current, previous.model_dump(mode="json"))

    assert merged.slots.service_type == "肩颈按摩"
    assert merged.slots.duration_minutes == 60
    assert merged.slots.preferred_time == datetime(2026, 6, 10, 8, 0)
    assert merged.missing_slots == []
