# 作用：验证同一时间段连续预约时，系统会自动切换到其他可用技师。
from datetime import datetime, timedelta

from app.repositories.catalog_repo import CatalogRepository
from app.schemas.agent import IntentOutput, IntentSlots
from app.services.match_service import MatchService


async def test_same_time_booking_should_switch_to_another_available_technician(client):
    """同一时间段还有其他技师/房间可用时，第二次预约不应直接冲突失败。"""
    target = datetime.now() + timedelta(days=3)
    message = f"预约{target.month}月{target.day}日早上八点，肩颈按摩，60分钟"

    first = await client.post(
        "/api/v1/conversations/message",
        json={"session_id": "parallel_1", "user_id": "00000000-0000-0000-0000-000000000001", "message": message},
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["response_type"] == "booking_options"
    first_option = first_body["options"][0]
    first_confirm = await client.post(
        "/api/v1/orders/confirm",
        json={"trace_id": first_body["trace_id"], "option_id": first_option["option_id"], "user_confirmed": True},
    )
    assert first_confirm.status_code == 200

    second = await client.post(
        "/api/v1/conversations/message",
        json={"session_id": "parallel_2", "user_id": "00000000-0000-0000-0000-000000000001", "message": message},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["response_type"] == "booking_options"
    second_option = second_body["options"][0]

    assert second_option["appointment_start"] == first_option["appointment_start"]
    assert second_option["technician_name"] != first_option["technician_name"]

    second_confirm = await client.post(
        "/api/v1/orders/confirm",
        json={"trace_id": second_body["trace_id"], "option_id": second_option["option_id"], "user_confirmed": True},
    )
    assert second_confirm.status_code == 200
    assert second_confirm.json()["status"] == "confirmed"


async def test_match_should_produce_multiple_technician_candidates(db_session):
    """匹配阶段应该保留多个技师候选，供排班阶段自动兜底。"""
    intent = IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(
            service_type="肩颈按摩",
            duration_minutes=60,
            preferred_time=datetime.now() + timedelta(days=3),
        ),
        missing_slots=[],
        confidence=0.95,
    )
    match = await MatchService(CatalogRepository(db_session)).match(intent)
    technician_names = {item.technician_name for item in match.candidates}

    assert len(technician_names) >= 2
