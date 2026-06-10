# 作用：测试 VerificationGate 对关键业务对象的确定性校验。
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.harness.verification import VerificationGate
from app.schemas.agent import CandidateOption, IntentOutput, MatchOutput, OrderDraft, PriceOutput, ScheduleOutput


def _intent() -> IntentOutput:
    """构造完整预约意图，供后续业务对象校验复用。"""
    return IntentOutput.model_validate(
        {
            "task_type": "book_appointment",
            "slots": {
                "service_type": "肩颈按摩",
                "duration_minutes": 90,
                "preferred_time": (datetime.now() + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0),
                "budget_max": "300",
                "strength_preference": "heavy",
            },
            "missing_slots": [],
            "confidence": 0.9,
        }
    )


def _candidate() -> CandidateOption:
    """构造合法候选方案。"""
    return CandidateOption(
        option_id="option_001",
        store_id="store_001",
        service_id="service_001",
        technician_id="tech_001",
        service_name="肩颈舒缓 90 分钟",
        technician_name="小李",
        base_price=Decimal("298"),
        duration_minutes=90,
        match_score=0.9,
        reason="符合预算和时长",
    )


# ── 原有测试（无 DB 连接，VerificationGate() 纯结构校验） ──────────────────


@pytest.mark.asyncio
async def test_verification_gate_rejects_candidate_over_budget():
    """候选方案超过预算时必须被拦截。"""
    intent = _intent()
    candidate = _candidate().model_copy(update={"base_price": Decimal("328")})
    result = await VerificationGate().verify_candidates(intent=intent, match=MatchOutput(candidates=[candidate]))

    assert result.passed is False
    assert any(error["code"] == "candidate_over_budget" for error in result.errors)


@pytest.mark.asyncio
async def test_verification_gate_rejects_schedule_duration_mismatch():
    """排班时长和候选服务时长不一致时必须被拦截。"""
    intent = _intent()
    candidate = _candidate()
    start = intent.slots.preferred_time
    schedule = ScheduleOutput(
        available=True,
        room_id="room_001",
        lock_id="lock_001",
        appointment_start=start,
        appointment_end=start + timedelta(minutes=60),
        cleanup_end=start + timedelta(minutes=70),
    )
    result = await VerificationGate().verify_schedule(candidate=candidate, intent=intent, schedule=schedule)

    assert result.passed is False
    assert any(error["code"] == "schedule_duration_mismatch" for error in result.errors)


@pytest.mark.asyncio
async def test_verification_gate_rejects_price_snapshot_service_mismatch():
    """价格快照服务 ID 和候选服务 ID 不一致时必须被拦截。"""
    candidate = _candidate()
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        price_snapshot={"service_id": "another_service"},
    )
    result = await VerificationGate().verify_price(candidate=candidate, price=price)

    assert result.passed is False
    assert any(error["code"] == "price_snapshot_service_mismatch" for error in result.errors)


@pytest.mark.asyncio
async def test_verification_gate_rejects_order_draft_tampering():
    """订单草稿价格和后端计价结果不一致时必须被拦截。"""
    candidate = _candidate()
    start = _intent().slots.preferred_time
    schedule = ScheduleOutput(
        available=True,
        room_id="room_001",
        lock_id="lock_001",
        appointment_start=start,
        appointment_end=start + timedelta(minutes=90),
        cleanup_end=start + timedelta(minutes=100),
    )
    price = PriceOutput(original_price=Decimal("298"), final_price=Decimal("298"), price_snapshot={"service_id": candidate.service_id})
    draft = OrderDraft(
        user_id="user_001",
        option_id=candidate.option_id,
        store_id=candidate.store_id,
        service_id=candidate.service_id,
        technician_id=candidate.technician_id,
        room_id=schedule.room_id,
        appointment_start=schedule.appointment_start,
        appointment_end=schedule.appointment_end,
        original_price=Decimal("298"),
        final_price=Decimal("1"),
        lock_id=schedule.lock_id,
        price_snapshot=price.price_snapshot,
    )
    result = await VerificationGate().verify_order_draft(candidate=candidate, schedule=schedule, price=price, draft=draft)

    assert result.passed is False
    assert any(error["code"] == "draft_price_mismatch" for error in result.errors)


# ── 新增测试：意图校验 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_intent_rejects_past_time():
    """预约时间早于当前+30分钟时必须被拦截。"""
    intent = IntentOutput.model_validate(
        {
            "task_type": "book_appointment",
            "slots": {
                "service_type": "肩颈按摩",
                "duration_minutes": 90,
                "preferred_time": (datetime.now() + timedelta(minutes=10)).isoformat(),
                "budget_max": "300",
            },
            "missing_slots": [],
            "confidence": 0.9,
        }
    )
    result = await VerificationGate().verify_intent(intent)
    assert result.passed is False
    assert any(error["code"] == "appointment_time_too_soon" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_intent_rejects_invalid_duration():
    """服务时长不在 5-480 分钟范围内时必须被拦截。"""
    intent = IntentOutput.model_validate(
        {
            "task_type": "book_appointment",
            "slots": {
                "service_type": "肩颈按摩",
                "duration_minutes": 1000,
                "preferred_time": (datetime.now() + timedelta(hours=3)).isoformat(),
                "budget_max": "300",
            },
            "missing_slots": [],
            "confidence": 0.9,
        }
    )
    result = await VerificationGate().verify_intent(intent)
    assert result.passed is False
    assert any(error["code"] == "invalid_duration" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_intent_rejects_negative_budget():
    """预算为负数时必须被拦截。"""
    intent = IntentOutput.model_validate(
        {
            "task_type": "book_appointment",
            "slots": {
                "service_type": "肩颈按摩",
                "duration_minutes": 90,
                "preferred_time": (datetime.now() + timedelta(hours=3)).isoformat(),
                "budget_max": "-100",
            },
            "missing_slots": [],
            "confidence": 0.9,
        }
    )
    result = await VerificationGate().verify_intent(intent)
    assert result.passed is False
    assert any(error["code"] == "invalid_budget" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_intent_allows_valid_intent():
    """合法意图应通过校验。"""
    intent = _intent()
    result = await VerificationGate().verify_intent(intent)
    assert result.passed is True


@pytest.mark.asyncio
async def test_verify_intent_allows_customer_service():
    """售后任务直接放行，不做预约字段校验。"""
    intent = IntentOutput.model_validate(
        {
            "task_type": "cancel_order",
            "slots": {},
            "missing_slots": ["order_id"],
            "confidence": 0.8,
        }
    )
    result = await VerificationGate().verify_intent(intent)
    assert result.passed is True


# ── 新增测试：候选方案校验 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_candidates_rejects_duplicate_ids():
    """重复 option_id 必须被拦截。"""
    intent = _intent()
    candidate = _candidate()
    dup = candidate.model_copy(update={"option_id": candidate.option_id})
    result = await VerificationGate().verify_candidates(intent=intent, match=MatchOutput(candidates=[candidate, dup]))
    assert result.passed is False
    assert any(error["code"] == "duplicate_option_id" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_candidates_rejects_invalid_score():
    """评分超出 0-1 范围时必须被拦截。"""
    intent = _intent()
    candidate = _candidate().model_copy(update={"match_score": 1.5})
    result = await VerificationGate().verify_candidates(intent=intent, match=MatchOutput(candidates=[candidate]))
    assert result.passed is False
    assert any(error["code"] == "candidate_invalid_score" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_candidates_rejects_missing_business_id():
    """候选人缺少关键 business ID 时必须被拦截。"""
    intent = _intent()
    candidate = _candidate().model_copy(update={"store_id": ""})
    result = await VerificationGate().verify_candidates(intent=intent, match=MatchOutput(candidates=[candidate]))
    assert result.passed is False
    assert any(error["code"] == "candidate_missing_business_id" for error in result.errors)


# ── 新增测试：排班校验 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_schedule_rejects_unavailable():
    """排班不可用时应直接返回失败。"""
    intent = _intent()
    candidate = _candidate()
    schedule = ScheduleOutput(available=False, reason="无可用技师")
    result = await VerificationGate().verify_schedule(candidate=candidate, intent=intent, schedule=schedule)
    assert result.passed is False
    assert any(error["code"] == "schedule_unavailable" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_schedule_rejects_missing_lock():
    """缺少时间锁时必须被拦截。"""
    intent = _intent()
    candidate = _candidate()
    start = intent.slots.preferred_time
    schedule = ScheduleOutput(
        available=True,
        room_id="room_001",
        appointment_start=start,
        appointment_end=start + timedelta(minutes=90),
    )
    result = await VerificationGate().verify_schedule(candidate=candidate, intent=intent, schedule=schedule)
    assert result.passed is False
    assert any(error["code"] == "schedule_missing_lock" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_schedule_rejects_time_in_past():
    """预约时间在过去时必须被拦截。"""
    intent = _intent()
    candidate = _candidate()
    past = datetime.now() - timedelta(hours=1)
    schedule = ScheduleOutput(
        available=True,
        room_id="room_001",
        lock_id="lock_001",
        appointment_start=past,
        appointment_end=past + timedelta(minutes=90),
    )
    result = await VerificationGate().verify_schedule(candidate=candidate, intent=intent, schedule=schedule)
    assert result.passed is False
    assert any(error["code"] == "schedule_time_in_past" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_schedule_accepts_valid_schedule():
    """合法排班结果应通过校验。"""
    intent = _intent()
    candidate = _candidate()
    start = intent.slots.preferred_time
    schedule = ScheduleOutput(
        available=True,
        room_id="room_001",
        lock_id="lock_001",
        appointment_start=start,
        appointment_end=start + timedelta(minutes=90),
        cleanup_end=start + timedelta(minutes=100),
    )
    result = await VerificationGate().verify_schedule(candidate=candidate, intent=intent, schedule=schedule)
    assert result.passed is True


# ── 新增测试：价格校验 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_price_rejects_negative_discount():
    """折扣为负数时必须被拦截。"""
    candidate = _candidate()
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        member_discount=Decimal("-10"),
        price_snapshot={"service_id": candidate.service_id},
    )
    result = await VerificationGate().verify_price(candidate=candidate, price=price)
    assert result.passed is False
    assert any(error["code"] == "price_negative_discount" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_price_rejects_final_exceeds_original():
    """最终价格高于原价时必须被拦截。"""
    candidate = _candidate()
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("398"),
        price_snapshot={"service_id": candidate.service_id},
    )
    result = await VerificationGate().verify_price(candidate=candidate, price=price)
    assert result.passed is False
    assert any(error["code"] == "price_final_exceeds_original" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_price_rejects_abnormal_discount():
    """折扣超过原价 50% 时必须被拦截。"""
    candidate = _candidate()
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("100"),
        promotion_discount=Decimal("198"),
        price_snapshot={"service_id": candidate.service_id},
    )
    result = await VerificationGate().verify_price(candidate=candidate, price=price)
    assert result.passed is False
    assert any(error["code"] == "price_discount_abnormal" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_price_rejects_incomplete_snapshot():
    """price_snapshot 缺少必备字段时必须被拦截。"""
    candidate = _candidate()
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        price_snapshot={"service_id": candidate.service_id},
    )
    result = await VerificationGate().verify_price(candidate=candidate, price=price)
    assert result.passed is False
    assert any(error["code"] == "price_snapshot_incomplete" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_price_accepts_valid_price():
    """合法价格应通过校验。"""
    candidate = _candidate()
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("268"),
        member_discount=Decimal("30"),
        price_snapshot={
            "service_id": candidate.service_id,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "original_price": "298",
            "final_price": "268",
        },
    )
    result = await VerificationGate().verify_price(candidate=candidate, price=price)
    assert result.passed is True


# ── 新增测试：订单草稿校验 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_order_draft_rejects_missing_user_id():
    """订单草稿缺少 user_id 时必须被拦截。"""
    candidate = _candidate()
    start = _intent().slots.preferred_time
    schedule = ScheduleOutput(
        available=True,
        room_id="room_001",
        lock_id="lock_001",
        appointment_start=start,
        appointment_end=start + timedelta(minutes=90),
    )
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        price_snapshot={"service_id": candidate.service_id},
    )
    draft = OrderDraft(
        user_id="",
        option_id=candidate.option_id,
        store_id=candidate.store_id,
        service_id=candidate.service_id,
        technician_id=candidate.technician_id,
        room_id=schedule.room_id,
        appointment_start=schedule.appointment_start,
        appointment_end=schedule.appointment_end,
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        lock_id=schedule.lock_id,
        price_snapshot=price.price_snapshot,
    )
    result = await VerificationGate().verify_order_draft(candidate=candidate, schedule=schedule, price=price, draft=draft)
    assert result.passed is False
    assert any(error["code"] == "draft_missing_user_id" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_order_draft_rejects_missing_price_snapshot():
    """订单草稿缺少 price_snapshot 时必须被拦截。"""
    candidate = _candidate()
    start = _intent().slots.preferred_time
    schedule = ScheduleOutput(
        available=True,
        room_id="room_001",
        lock_id="lock_001",
        appointment_start=start,
        appointment_end=start + timedelta(minutes=90),
    )
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        price_snapshot={"service_id": candidate.service_id},
    )
    draft = OrderDraft(
        user_id="user_001",
        option_id=candidate.option_id,
        store_id=candidate.store_id,
        service_id=candidate.service_id,
        technician_id=candidate.technician_id,
        room_id=schedule.room_id,
        appointment_start=schedule.appointment_start,
        appointment_end=schedule.appointment_end,
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        lock_id=schedule.lock_id,
        price_snapshot={},
    )
    result = await VerificationGate().verify_order_draft(candidate=candidate, schedule=schedule, price=price, draft=draft)
    assert result.passed is False
    assert any(error["code"] == "draft_missing_price_snapshot" for error in result.errors)


@pytest.mark.asyncio
async def test_verify_order_draft_accepts_valid_draft():
    """完整订单草稿应通过校验。"""
    candidate = _candidate()
    start = _intent().slots.preferred_time
    schedule = ScheduleOutput(
        available=True,
        room_id="room_001",
        lock_id="lock_001",
        appointment_start=start,
        appointment_end=start + timedelta(minutes=90),
        cleanup_end=start + timedelta(minutes=100),
    )
    price = PriceOutput(
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        price_snapshot={
            "service_id": candidate.service_id,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "original_price": "298",
            "final_price": "298",
        },
    )
    draft = OrderDraft(
        user_id="user_001",
        option_id=candidate.option_id,
        store_id=candidate.store_id,
        service_id=candidate.service_id,
        technician_id=candidate.technician_id,
        room_id=schedule.room_id,
        appointment_start=schedule.appointment_start,
        appointment_end=schedule.appointment_end,
        original_price=Decimal("298"),
        final_price=Decimal("298"),
        lock_id=schedule.lock_id,
        price_snapshot=price.price_snapshot,
    )
    result = await VerificationGate().verify_order_draft(candidate=candidate, schedule=schedule, price=price, draft=draft)
    assert result.passed is True
