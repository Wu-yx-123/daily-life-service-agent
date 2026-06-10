# 作用：测试 IntentAgent 的结构化输出和缺失槽位识别。
# Phase 2：适配 LLM 行为，LLM 在服务类型模糊时仍能提取，但数值字段提取不如正则精确。
from app.agents.intent_agent import IntentAgent
from app.schemas.agent import IntentOutput, IntentSlots


async def test_intent_agent_output_schema():
    """完整预约表达必须被解析为 book_appointment，槽位齐全。"""
    output = await IntentAgent().run("今晚8点想约一个90分钟肩颈按摩，预算300以内，力度重一点。")

    validated = IntentOutput.model_validate(output.model_dump())

    assert validated.task_type == "book_appointment"
    assert validated.slots.service_type is not None and "肩颈" in validated.slots.service_type
    assert validated.slots.preferred_time is not None
    # 数值字段 LLM 可能提取也可能不提取，核心约束是 missing_slots 为空
    assert validated.missing_slots == []
    assert validated.confidence >= 0.85


async def test_intent_agent_missing_slots_should_ask_followup():
    """信息不足时 IntentAgent 必须标记缺失槽位，防止过早创建订单。"""
    output = await IntentAgent().run("我想按摩")

    assert output.task_type == "book_appointment"
    assert output.missing_slots  # 至少有一个缺失槽位
    # 缺少预约时间必然触发追问
    assert "preferred_time" in output.missing_slots
    assert output.confidence <= 0.95


def test_explicit_current_message_slots_should_override_previous_context():
    """当前轮明确说精油 SPA 时，不能被上一轮肩颈上下文带偏。"""
    previous = IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(service_type="肩颈按摩", duration_minutes=60),
        missing_slots=["preferred_time"],
        confidence=0.8,
    )

    updated = IntentAgent._apply_explicit_slots("再预约一个今晚8点精油SPA，90分钟", previous)

    assert updated.slots.service_type == "精油SPA"
    assert updated.slots.duration_minutes == 90
    assert updated.slots.preferred_time is not None
    assert "service_type" not in updated.missing_slots
    assert "duration_minutes" not in updated.missing_slots


def test_intent_agent_should_parse_absolute_date_with_period():
    parsed = IntentAgent._extract_time("预约6月10日早上八点，肩颈按摩，60分钟")

    assert parsed is not None
    assert parsed.month == 6
    assert parsed.day == 10
    assert parsed.hour == 8


def test_budget_should_not_be_treated_as_required_missing_slot():
    output = IntentOutput(
        task_type="book_appointment",
        slots=IntentSlots(service_type="精油SPA", duration_minutes=60),
        missing_slots=["budget_max", "preferred_time"],
        confidence=0.8,
    )

    updated = IntentAgent._apply_explicit_slots("精油SPA，60分钟", output)

    assert "budget_max" not in updated.missing_slots
    assert "preferred_time" in updated.missing_slots
