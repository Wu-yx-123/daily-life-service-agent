# 作用：验证长期记忆可写入、召回，并能辅助补全安全槽位。
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.core.embeddings import EmbeddingService, vector_to_pg_literal
from app.models.memory import UserPreference
from app.repositories.memory_repo import MemoryRepository
from app.schemas.agent import IntentOutput, IntentSlots
from app.services.memory_service import MemoryService
from app.services.memory_retention_service import MemoryRetentionService
from app.services.semantic_memory_service import SemanticMemoryService


async def test_confirmed_booking_records_long_term_preferences(client, db_session):
    """确认预约成功后，应把本次真实成交行为沉淀为长期偏好。"""
    response = await client.post(
        "/api/v1/conversations/message",
        json={
            "session_id": "session_memory_001",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "message": "明天20点想约一个90分钟肩颈按摩，预算300以内，力度重一点。",
        },
    )
    body = response.json()
    confirm = await client.post(
        "/api/v1/orders/confirm",
        json={
            "trace_id": body["trace_id"],
            "option_id": body["options"][0]["option_id"],
            "user_confirmed": True,
        },
    )

    assert confirm.status_code == 200
    # 直接查长期记忆仓储，验证 API 主链路已经完成写回。
    prefs = await MemoryRepository(db_session).list_user_preferences(
        user_id="00000000-0000-0000-0000-000000000001",
        min_confidence=Decimal("0.50"),
    )
    by_type = {item.preference_type: item.preference_value for item in prefs}
    # 服务、力度、常用时段是当前最小长期记忆版本必须沉淀的核心偏好。
    assert by_type["service_type"] == "肩颈按摩"
    assert by_type["strength"] == "heavy"
    assert by_type["time_window"] == "evening"


async def test_memory_defaults_can_fill_missing_safe_slots():
    """强偏好可以补全服务类型，但不能替用户补全具体预约时间。"""
    # 模拟已经被多次确认过的强偏好画像。
    memory = {
        "preferences": {
            "service_type": [{"value": "肩颈按摩", "confidence": 0.75, "seen_count": 2}],
        },
        "defaults": {"service_type": "肩颈按摩"},
    }
    intent = IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(preferred_time=None),
        missing_slots=["service_type", "preferred_time"],
        confidence=0.55,
    )
    # 这里不依赖数据库，专门验证确定性补全策略本身。
    enriched = MemoryService.apply_to_intent(intent, memory)

    assert enriched.slots.service_type == "肩颈按摩"
    # service_type 可以由长期偏好补全，所以不再需要追问。
    assert "service_type" not in enriched.missing_slots
    # preferred_time 属于强确认字段，不能由“常约时段”或其他记忆代替用户确认。
    assert "preferred_time" in enriched.missing_slots


def test_memory_budget_should_not_become_hard_constraint():
    """历史成交价/预算偏好不能自动变成本轮预算上限。"""
    memory = {
        "preferences": {
            "budget_max": [{"value": "198", "confidence": 0.9, "seen_count": 3}],
        },
        "defaults": {"budget_max": "198"},
    }
    intent = IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(service_type="精油SPA"),
        missing_slots=["preferred_time"],
        confidence=0.7,
    )

    enriched = MemoryService.apply_to_intent(intent, memory)

    assert enriched.slots.budget_max is None


async def test_semantic_memory_records_and_retrieves_with_pgvector(db_session):
    """pgvector 语义记忆可以写入自然语言摘要，并按当前消息相似度召回。"""
    service = SemanticMemoryService(db_session)
    user_id = "00000000-0000-0000-0000-000000000001"
    state = {
        "trace_id": "trace_semantic_001",
        "session_id": "session_semantic_001",
        "user_message": "明天20点想约肩颈按摩，力度重一点，预算300以内。",
        "intent": {
            "task_type": "book_appointment",
            "slots": {
                "service_type": "肩颈按摩",
                "duration_minutes": 90,
                "preferred_time": None,
                "budget_max": "300",
                "strength_preference": "heavy",
            },
            "missing_slots": [],
            "confidence": 0.9,
        },
        "selected_option": {"technician_name": "小李", "service_name": "肩颈舒缓 90 分钟"},
        "order_draft": {"appointment_start": "2026-06-02T20:00:00"},
    }

    await service.record_booking_memory(user_id=user_id, state=state, order_id="order_semantic_001")
    memories = await service.retrieve_for_user(user_id=user_id, query="还想约肩颈，力度重点")

    assert memories
    assert "肩颈按摩" in memories[0]["content"]
    assert memories[0]["memory_type"] == "booking_experience"


async def test_memory_retention_prunes_only_stale_weak_memories(db_session):
    """清理任务只删除过期弱记忆，保留强偏好和重要语义记忆。"""
    user_id = "00000000-0000-0000-0000-000000000001"
    old_time = datetime.now() - timedelta(days=220)
    recent_time = datetime.now()

    weak_pref = UserPreference(
        user_id=user_id,
        preference_type="service_type",
        preference_value="临时体验",
        confidence=Decimal("0.40"),
        seen_count=1,
        source="test",
        last_seen_at=old_time,
    )
    strong_pref = UserPreference(
        user_id=user_id,
        preference_type="service_type",
        preference_value="肩颈按摩",
        confidence=Decimal("0.90"),
        seen_count=5,
        source="test",
        last_seen_at=old_time,
    )
    db_session.add_all([weak_pref, strong_pref])
    await db_session.flush()

    embedding = await EmbeddingService().embed_query("用户临时体验过不常用服务")
    await db_session.execute(
        text(
            """
            INSERT INTO user_memory_chunks
                (id, user_id, memory_type, content, embedding, source, evidence, importance, created_at)
            VALUES
                (gen_random_uuid(), :user_id, 'booking_experience', :old_content,
                 CAST(:embedding AS vector), 'test', CAST('{}' AS JSON), 0.40, :old_time),
                (gen_random_uuid(), :user_id, 'booking_experience', :recent_content,
                 CAST(:embedding AS vector), 'test', CAST('{}' AS JSON), 0.90, :recent_time)
            """
        ),
        {
            "user_id": user_id,
            "old_content": "低重要性且很久没有出现的语义记忆",
            "recent_content": "高重要性语义记忆",
            "embedding": vector_to_pg_literal(embedding),
            "old_time": old_time,
            "recent_time": recent_time,
        },
    )
    await db_session.commit()

    service = MemoryRetentionService(db_session)
    preview = await service.prune_stale_memories(dry_run=True)
    assert preview.structured_preferences == 1
    assert preview.semantic_chunks == 1

    result = await service.prune_stale_memories(dry_run=False)
    assert result.structured_preferences == 1
    assert result.semantic_chunks == 1

    remaining_prefs = await MemoryRepository(db_session).list_user_preferences(user_id=user_id, min_confidence=Decimal("0"))
    assert {pref.preference_value for pref in remaining_prefs} == {"肩颈按摩"}
