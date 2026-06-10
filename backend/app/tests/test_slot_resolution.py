# 作用：验证多轮槽位冲突消解和下游状态失效策略。
from datetime import datetime, timedelta

from app.harness.slot_resolution import SlotResolutionGate
from app.schemas.agent import IntentOutput, IntentSlots


def _booking_intent(**slots):
    return IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(**slots),
        missing_slots=[],
        confidence=0.9,
    )


def test_slot_resolution_requires_confirmation_for_multiple_times_without_correction():
    gate = SlotResolutionGate()
    current = _booking_intent(
        service_type="肩颈按摩",
        duration_minutes=60,
        preferred_time=datetime.now() + timedelta(days=1),
    )

    result = gate.resolve(
        current=current,
        previous_raw=None,
        message="明天晚上8点或者后天晚上8点都行",
    )

    assert result["requires_confirmation"] is True
    assert result["slot_resolution"]["conflicts"][0]["slot"] == "preferred_time"
    assert "多个预约时间" in result["confirmation_question"]


def test_slot_resolution_uses_corrected_time_after_marker():
    gate = SlotResolutionGate()
    current = _booking_intent(
        service_type="肩颈按摩",
        duration_minutes=60,
        preferred_time=datetime.now() + timedelta(days=1),
    )

    result = gate.resolve(
        current=current,
        previous_raw=None,
        message="明天晚上8点，不对，后天晚上8点",
    )

    resolved = result["intent"]
    assert result["requires_confirmation"] is False
    assert resolved.slots.preferred_time.date() == (datetime.now().date() + timedelta(days=2))
    assert resolved.slots.preferred_time.hour == 20


def test_slot_resolution_invalidates_downstream_state_when_time_changes():
    gate = SlotResolutionGate()
    previous = _booking_intent(
        service_type="肩颈按摩",
        duration_minutes=60,
        preferred_time=datetime.now() + timedelta(days=1),
    )
    current = _booking_intent(
        service_type="肩颈按摩",
        duration_minutes=60,
        preferred_time=datetime.now() + timedelta(days=2),
    )

    result = gate.resolve(
        current=current,
        previous_raw=previous.model_dump(mode="json"),
        message="改成后天晚上8点",
    )

    assert "preferred_time" in result["slot_resolution"]["changed_slots"]
    assert set(result["invalidated_state_keys"]) == {
        "approval_request",
        "order_draft",
        "risk_result",
        "schedule_check",
    }


def test_slot_resolution_invalidates_match_chain_when_service_changes():
    gate = SlotResolutionGate()
    previous = _booking_intent(
        service_type="肩颈按摩",
        duration_minutes=60,
        preferred_time=datetime.now() + timedelta(days=1),
    )
    current = _booking_intent(
        service_type="足部养护",
        duration_minutes=60,
        preferred_time=previous.slots.preferred_time,
    )

    result = gate.resolve(
        current=current,
        previous_raw=previous.model_dump(mode="json"),
        message="换成足疗",
    )

    assert "service_type" in result["slot_resolution"]["changed_slots"]
    assert "candidates" in result["invalidated_state_keys"]
    assert "selected_option" in result["invalidated_state_keys"]
    assert "order_draft" in result["invalidated_state_keys"]
