# 作用：实现 Verification Gate，在 Agent 输出进入下一步前做确定性校验。
# Phase 2 增强：接入数据库，校验实体存在性、状态、排班冲突和价格来源。
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, TYPE_CHECKING

from app.schemas.agent import (
    CandidateOption,
    CustomerServiceOutput,
    IntentOutput,
    MatchOutput,
    OrderDraft,
    PriceOutput,
    RiskOutput,
    ScheduleOutput,
    VerificationOutput,
)
from app.utils.service_match import matches_service_type

if TYPE_CHECKING:
    from app.repositories.after_sales_repo import AfterSalesRepository
    from app.repositories.catalog_repo import CatalogRepository
    from app.repositories.order_repo import OrderRepository

CUSTOMER_SERVICE_TASKS = {"cancel_order", "reschedule_order", "refund_request", "complaint"}
# 查询/未知类意图直接放行到 plan_task 做即时回复，不需要预约校验
PASSTHROUGH_TASKS = {"service_query", "store_query", "ops_analysis", "unknown"}

# 服务时长合理范围（分钟）
MIN_DURATION_MINUTES = 5
MAX_DURATION_MINUTES = 480

# 预约最少提前量（分钟）：用户不能预约 30 分钟之内开始的时段
MIN_ADVANCE_MINUTES = 30

# 折扣异常阈值：总折扣超过原价 50% 视为异常
MAX_DISCOUNT_RATIO = Decimal("0.5")

# price_snapshot 必须包含的字段
REQUIRED_SNAPSHOT_FIELDS = {"service_id", "calculated_at", "original_price", "final_price"}
REQUIRED_BOOKING_SLOTS = {"service_type", "preferred_time", "duration_minutes"}


class VerificationGate:
    """Phase 2 校验闸门。

    Agent 可以给出建议，但关键业务状态必须先通过这里的确定性规则。
    接入 CatalogRepository / OrderRepository 后，所有实体存在性和状态校验都会查数据库，
    确保 Agent 不能通过幻觉或错误输出来绕过业务约束。
    """

    def __init__(
        self,
        catalog_repo: CatalogRepository | None = None,
        order_repo: OrderRepository | None = None,
        after_sales_repo: AfterSalesRepository | None = None,
    ):
        self.catalog_repo = catalog_repo
        self.order_repo = order_repo
        self.after_sales_repo = after_sales_repo

    # ── 预约意图校验 ──────────────────────────────────────────────

    async def verify_intent(self, intent: IntentOutput) -> VerificationOutput:
        """校验预约意图是否具备继续执行的最低条件。

        规则：
        1. 售后类任务直接放行
        2. task_type 必须是 book_appointment
        3. missing_slots 为空才能继续
        4. preferred_time 必须晚于「当前时间 + 30 分钟」
        5. duration_minutes 必须在合理范围内（5-480 分钟）
        6. budget_max 必须为正数
        7. （DB）service_type 必须在数据库中存在（匹配 category 或 name）
        """
        errors: list[dict[str, Any]] = []

        # 1. 售后/查询/未知类任务不阻塞，交给 plan_task 分发
        if intent.task_type in CUSTOMER_SERVICE_TASKS | PASSTHROUGH_TASKS:
            return VerificationOutput(passed=True, errors=[])

        # 2. 任务类型
        if intent.task_type != "book_appointment":
            errors.append({"code": "unsupported_task_type", "task_type": intent.task_type})

        # 3. 缺失槽位 → 需要追问
        for slot in intent.missing_slots:
            if slot not in REQUIRED_BOOKING_SLOTS:
                continue
            errors.append({"code": "missing_slot", "slot": slot})

        # 4. 预约时间 ≥ 当前时间 + 30 分钟
        preferred_time = intent.slots.preferred_time
        now = datetime.now().replace(tzinfo=None)
        if preferred_time is not None:
            if preferred_time.replace(tzinfo=None) < now + timedelta(minutes=MIN_ADVANCE_MINUTES):
                errors.append({
                    "code": "appointment_time_too_soon",
                    "min_advance_minutes": MIN_ADVANCE_MINUTES,
                    "preferred_time": preferred_time.isoformat(),
                })
        # preferred_time 为 None 也是合法的——后续 Agent 可以提议时间

        # 5. 服务时长合法范围
        duration = intent.slots.duration_minutes
        if duration is not None:
            if duration < MIN_DURATION_MINUTES or duration > MAX_DURATION_MINUTES:
                errors.append({
                    "code": "invalid_duration",
                    "duration": duration,
                    "min": MIN_DURATION_MINUTES,
                    "max": MAX_DURATION_MINUTES,
                })

        # 6. 预算为正数
        budget = intent.slots.budget_max
        if budget is not None and budget <= Decimal("0"):
            errors.append({"code": "invalid_budget", "budget": str(budget)})

        # 7. （DB）service_type 存在性
        if self.catalog_repo and intent.slots.service_type:
            services = await self.catalog_repo.list_active_services()
            matching = [
                s for s in services
                if matches_service_type(
                    intent.slots.service_type,
                    " ".join([s.name, s.category or "", " ".join(s.tags or [])]),
                )
            ]
            if not matching:
                errors.append({
                    "code": "service_type_not_found",
                    "service_type": intent.slots.service_type,
                })

        return VerificationOutput(passed=not errors, errors=errors)

    # ── 候选方案校验 ──────────────────────────────────────────────

    async def verify_candidates(self, *, intent: IntentOutput, match: MatchOutput) -> VerificationOutput:
        """校验 MatchAgent 返回的候选方案是否满足用户硬约束。

        规则：
        1. 至少有一个候选
        2. 无重复 option_id
        3. 关键业务 ID 齐全
        4. 价格 / 时长 / 评分范围合法
        5. 时长和用户意图一致
        6. 价格不超用户预算
        7. （DB）service 存在且 active
        8. （DB）technician 存在、active 且属于对应门店
        """
        errors: list[dict[str, Any]] = []

        if not match.candidates:
            errors.append({"code": "no_candidates"})
            return VerificationOutput(passed=False, errors=errors)

        seen_option_ids: set[str] = set()
        for candidate in match.candidates:
            _oid = candidate.option_id

            # 2. 去重
            if _oid in seen_option_ids:
                errors.append({"code": "duplicate_option_id", "option_id": _oid})
            seen_option_ids.add(_oid)

            # 3. 关键业务 ID
            if not candidate.store_id or not candidate.service_id or not candidate.technician_id:
                errors.append({"code": "candidate_missing_business_id", "option_id": _oid})

            # 4. 价格 / 时长 / 评分
            if candidate.base_price <= Decimal("0"):
                errors.append({"code": "candidate_invalid_price", "option_id": _oid})
            if candidate.duration_minutes <= 0:
                errors.append({"code": "candidate_invalid_duration", "option_id": _oid})
            if not 0 <= candidate.match_score <= 1:
                errors.append({"code": "candidate_invalid_score", "option_id": _oid})

            # 5. 时长匹配用户意图
            if intent.slots.duration_minutes and candidate.duration_minutes != intent.slots.duration_minutes:
                errors.append({"code": "candidate_duration_mismatch", "option_id": _oid})

            # 6. 预算
            if intent.slots.budget_max and candidate.base_price > intent.slots.budget_max:
                errors.append({"code": "candidate_over_budget", "option_id": _oid})

        # 7-8. DB 校验（批量）
        if self.catalog_repo:
            for candidate in match.candidates:
                _oid = candidate.option_id

                # 7. service 存在且 active
                svc = await self.catalog_repo.get_service(candidate.service_id)
                if not svc:
                    errors.append({"code": "candidate_service_not_found", "option_id": _oid, "service_id": candidate.service_id})
                elif svc.status != "active":
                    errors.append({"code": "candidate_service_inactive", "option_id": _oid, "service_id": candidate.service_id})

                # 8. technician 存在、active 且属于该门店
                tech = await self.catalog_repo.get_technician(candidate.technician_id)
                if not tech:
                    errors.append({"code": "candidate_technician_not_found", "option_id": _oid, "technician_id": candidate.technician_id})
                else:
                    if tech.status != "active":
                        errors.append({"code": "candidate_technician_inactive", "option_id": _oid, "technician_id": candidate.technician_id})
                    if str(tech.store_id) != candidate.store_id:
                        errors.append({
                            "code": "candidate_technician_wrong_store",
                            "option_id": _oid,
                            "technician_id": candidate.technician_id,
                            "expected_store": candidate.store_id,
                            "actual_store": str(tech.store_id),
                        })

        return VerificationOutput(passed=not errors, errors=errors)

    # ── 排班校验 ──────────────────────────────────────────────────

    async def verify_schedule(
        self, *, candidate: CandidateOption, intent: IntentOutput, schedule: ScheduleOutput
    ) -> VerificationOutput:
        """校验 ScheduleAgent 返回的排班结果是否可用于生成订单草稿。

        规则：
        1. 排班结果为 available
        2. room_id / lock_id 存在
        3. appointment_start / appointment_end 存在且合法
        4. 开始时间不早于当前时间
        5. 结束晚于开始
        6. 时长与候选方案一致
        7. cleanup_end ≥ appointment_end
        8. （DB）技师存在、active 且属于该门店
        9. （DB）房间存在且 active
        10.（DB）预约时间在门店营业时间内（含清洁时间）
        11.（DB）技师在目标时间段有排班
        12.（DB）技师无订单冲突（含清洁时间）
        13.（DB）房间无订单冲突（含清洁时间）
        """
        errors: list[dict[str, Any]] = []

        # 1. 可用性
        if not schedule.available:
            errors.append({"code": "schedule_unavailable", "reason": schedule.reason})
            return VerificationOutput(passed=False, errors=errors)

        # 2. room / lock
        if not schedule.room_id:
            errors.append({"code": "schedule_missing_room"})
        if not schedule.lock_id:
            errors.append({"code": "schedule_missing_lock"})

        # 3. 时间字段存在
        if not schedule.appointment_start or not schedule.appointment_end:
            errors.append({"code": "schedule_missing_time"})
            return VerificationOutput(passed=False, errors=errors)

        start = schedule.appointment_start.replace(tzinfo=None)
        end = schedule.appointment_end.replace(tzinfo=None)
        now = datetime.now().replace(tzinfo=None)

        # 4. 不早于当前时间
        if start < now:
            errors.append({"code": "schedule_time_in_past"})

        # 5. 结束晚于开始
        if end <= start:
            errors.append({"code": "schedule_invalid_range"})

        # 6. 时长匹配
        duration_minutes = int((end - start).total_seconds() // 60)
        if duration_minutes != candidate.duration_minutes:
            errors.append({
                "code": "schedule_duration_mismatch",
                "expected": candidate.duration_minutes,
                "actual": duration_minutes,
            })

        # 7. cleanup_end 合法性
        cleanup = schedule.cleanup_end.replace(tzinfo=None) if schedule.cleanup_end else None
        if cleanup and cleanup < end:
            errors.append({"code": "schedule_invalid_cleanup"})

        # 8-13. DB 校验
        if self.catalog_repo:
            # 8. 技师存在、active、属于该门店
            tech = await self.catalog_repo.get_technician(candidate.technician_id)
            if not tech:
                errors.append({"code": "technician_not_found", "technician_id": candidate.technician_id})
            else:
                if tech.status != "active":
                    errors.append({"code": "technician_inactive", "technician_id": candidate.technician_id})
                if str(tech.store_id) != candidate.store_id:
                    errors.append({
                        "code": "technician_wrong_store",
                        "technician_id": candidate.technician_id,
                        "expected_store": candidate.store_id,
                        "actual_store": str(tech.store_id),
                    })

            # 9. 房间存在且 active
            if schedule.room_id:
                room = await self.catalog_repo.get_room(schedule.room_id)
                if not room:
                    errors.append({"code": "room_not_found", "room_id": schedule.room_id})
                elif room.status != "active":
                    errors.append({"code": "room_inactive", "room_id": schedule.room_id})

            # 10. 门店营业时间
            store = await self.catalog_repo.get_store(candidate.store_id)
            if store:
                effective_end = cleanup if cleanup else end
                if start.time() < store.opening_time or effective_end.time() > store.closing_time:
                    errors.append({
                        "code": "schedule_outside_store_hours",
                        "appointment_start": start.time().isoformat(),
                        "effective_end": effective_end.time().isoformat(),
                        "store_opening": store.opening_time.isoformat(),
                        "store_closing": store.closing_time.isoformat(),
                    })

            # 11. 技师排班覆盖
            effective_end = cleanup if cleanup else end
            schedules = await self.catalog_repo.list_schedules_covering(
                candidate.technician_id, start, effective_end
            )
            if not schedules:
                errors.append({
                    "code": "technician_not_scheduled",
                    "technician_id": candidate.technician_id,
                    "start": start.isoformat(),
                    "end": effective_end.isoformat(),
                })

            # 12-13. 订单冲突（含清洁时间）
            if self.order_repo:
                conflict_range_end = cleanup if cleanup else end
                conflicts = await self.order_repo.list_overlapping_orders(
                    technician_id=candidate.technician_id,
                    room_id=schedule.room_id,
                    start=start,
                    end=conflict_range_end,
                )
                for conflict in conflicts:
                    conflict_tech_id = str(conflict.technician_id) if conflict.technician_id else None
                    conflict_room_id = str(conflict.room_id) if conflict.room_id else None
                    if conflict_tech_id == candidate.technician_id:
                        errors.append({
                            "code": "technician_order_conflict",
                            "technician_id": candidate.technician_id,
                            "conflict_order_id": str(conflict.id),
                        })
                    if schedule.room_id and conflict_room_id == schedule.room_id:
                        errors.append({
                            "code": "room_order_conflict",
                            "room_id": schedule.room_id,
                            "conflict_order_id": str(conflict.id),
                        })

        return VerificationOutput(passed=not errors, errors=errors)

    # ── 价格校验 ──────────────────────────────────────────────────

    async def verify_price(self, *, candidate: CandidateOption, price: PriceOutput) -> VerificationOutput:
        """校验 PriceAgent 返回的价格快照没有越权或不一致。

        规则：
        1. original_price 为正
        2. final_price 非负
        3. 各类折扣不为负
        4. final_price ≤ original_price
        5. original_price 与候选方案一致
        6. price_snapshot.service_id 匹配
        7. （DB）original_price 与数据库中的服务价格一致
        8. 折扣总额不超过原价 50%
        9. price_snapshot 必备字段完整
        """
        errors: list[dict[str, Any]] = []

        # 1-2. 价格本身合法
        if price.original_price <= Decimal("0"):
            errors.append({"code": "price_invalid_original"})
        if price.final_price < Decimal("0"):
            errors.append({"code": "price_invalid_final"})

        # 3. 折扣不为负
        for field_name, value in {
            "member_discount": price.member_discount,
            "coupon_discount": price.coupon_discount,
            "promotion_discount": price.promotion_discount,
        }.items():
            if value < Decimal("0"):
                errors.append({"code": "price_negative_discount", "field": field_name})

        # 4. final ≤ original
        if price.final_price > price.original_price:
            errors.append({
                "code": "price_final_exceeds_original",
                "original": str(price.original_price),
                "final": str(price.final_price),
            })

        # 5. 与候选方案一致
        if price.original_price != candidate.base_price:
            errors.append({
                "code": "price_candidate_mismatch",
                "price_original": str(price.original_price),
                "candidate_base": str(candidate.base_price),
            })

        # 6. snapshot 中的 service_id
        if price.price_snapshot.get("service_id") != candidate.service_id:
            errors.append({"code": "price_snapshot_service_mismatch"})

        # 7. （DB）价格来源校验
        if self.catalog_repo:
            svc = await self.catalog_repo.get_service(candidate.service_id)
            if svc:
                db_price = Decimal(svc.base_price)
                if price.original_price != db_price:
                    errors.append({
                        "code": "price_not_from_database",
                        "price_original": str(price.original_price),
                        "db_price": str(db_price),
                    })

        # 8. 折扣是否异常（总折扣 > 50%）
        total_discount = price.member_discount + price.coupon_discount + price.promotion_discount
        if price.original_price > Decimal("0") and total_discount > price.original_price * MAX_DISCOUNT_RATIO:
            errors.append({
                "code": "price_discount_abnormal",
                "total_discount": str(total_discount),
                "original_price": str(price.original_price),
                "max_allowed_ratio": str(MAX_DISCOUNT_RATIO),
            })

        # 9. price_snapshot 完整性
        missing_snapshot_fields = REQUIRED_SNAPSHOT_FIELDS - set(price.price_snapshot.keys())
        if missing_snapshot_fields:
            errors.append({
                "code": "price_snapshot_incomplete",
                "missing_fields": sorted(missing_snapshot_fields),
            })

        return VerificationOutput(passed=not errors, errors=errors)

    # ── 订单草稿校验 ──────────────────────────────────────────────

    async def verify_order_draft(
        self, *, candidate: CandidateOption, schedule: ScheduleOutput, price: PriceOutput, draft: OrderDraft
    ) -> VerificationOutput:
        """校验 OrderAgent 生成的订单草稿是否和上游结果一致且字段完整。

        规则：
        1. user_id 必须存在
        2. store_id / service_id / technician_id / room_id 必须存在
        3. appointment_start / appointment_end 必须存在
        4. lock_id 必须存在
        5. price_snapshot 必须存在且完整
        6. user_confirmed 必须已设置（Boolean 字段，至少不为 None）
        7. 草稿字段与上游 candidate / schedule / price 一致
        8. 价格合法
        """
        errors: list[dict[str, Any]] = []

        # 1. user_id
        if not draft.user_id:
            errors.append({"code": "draft_missing_user_id"})

        # 2. 关键业务 ID
        if not draft.store_id:
            errors.append({"code": "draft_missing_store_id"})
        if not draft.service_id:
            errors.append({"code": "draft_missing_service_id"})
        if not draft.technician_id:
            errors.append({"code": "draft_missing_technician_id"})
        if not draft.room_id:
            errors.append({"code": "draft_missing_room_id"})

        # 3. 时间字段
        if not draft.appointment_start:
            errors.append({"code": "draft_missing_appointment_start"})
        if not draft.appointment_end:
            errors.append({"code": "draft_missing_appointment_end"})
        if draft.appointment_start and draft.appointment_end:
            if draft.appointment_end <= draft.appointment_start:
                errors.append({"code": "draft_invalid_time_range"})

        # 4. lock_id
        if not draft.lock_id:
            errors.append({"code": "draft_missing_lock_id"})

        # 5. price_snapshot
        if not draft.price_snapshot:
            errors.append({"code": "draft_missing_price_snapshot"})
        else:
            missing = REQUIRED_SNAPSHOT_FIELDS - set(draft.price_snapshot.keys())
            if missing:
                errors.append({
                    "code": "draft_price_snapshot_incomplete",
                    "missing_fields": sorted(missing),
                })

        # 6. 价格合法
        if draft.original_price <= Decimal("0"):
            errors.append({"code": "draft_invalid_original_price"})
        if draft.final_price < Decimal("0"):
            errors.append({"code": "draft_invalid_final_price"})

        # 7. 与上游一致性
        if draft.option_id != candidate.option_id:
            errors.append({"code": "draft_option_mismatch"})
        if draft.store_id != candidate.store_id:
            errors.append({"code": "draft_store_mismatch"})
        if draft.service_id != candidate.service_id:
            errors.append({"code": "draft_service_mismatch"})
        if draft.technician_id != candidate.technician_id:
            errors.append({"code": "draft_technician_mismatch"})
        if draft.room_id != schedule.room_id:
            errors.append({"code": "draft_room_mismatch"})
        if draft.lock_id != schedule.lock_id:
            errors.append({"code": "draft_lock_mismatch"})
        if draft.appointment_start != schedule.appointment_start or draft.appointment_end != schedule.appointment_end:
            errors.append({"code": "draft_schedule_time_mismatch"})
        if draft.original_price != price.original_price or draft.final_price != price.final_price:
            errors.append({"code": "draft_price_mismatch"})

        return VerificationOutput(passed=not errors, errors=errors)

    # ── 风控结果校验 ──────────────────────────────────────────────

    async def verify_risk_result(self, risk: RiskOutput) -> VerificationOutput:
        """确保 RiskAgent 输出的风控结果合法。

        规则：
        1. risk_level 只能是 low / medium / high
        2. requires_approval=true 时 reasons 不能为空
        3. low 风险不应标记 requires_approval
        """
        errors: list[dict[str, Any]] = []
        if risk.requires_approval and not risk.reasons:
            errors.append({"code": "risk_approval_without_reasons"})
        if risk.risk_level == "low" and risk.requires_approval:
            errors.append({"code": "risk_low_but_requires_approval"})
        return VerificationOutput(passed=not errors, errors=errors)

    # ── 售后请求校验 ──────────────────────────────────────────────

    async def verify_after_sale_request(
        self, *, intent: IntentOutput, output: CustomerServiceOutput
    ) -> VerificationOutput:
        """售后工单创建前的业务门禁。

        规则：
        1. ticket_type 必须与 intent.task_type 一致
        2. priority 必须与任务类型匹配（complaint→urgent, refund→high）
        3. summary 和 suggested_action 不能为空
        """
        errors: list[dict[str, Any]] = []
        type_map = {
            "complaint": "complaint", "refund_request": "refund_request",
            "cancel_order": "cancel_order", "reschedule_order": "reschedule_order",
        }
        expected = type_map.get(intent.task_type)
        if expected and output.ticket_type != expected:
            errors.append({"code": "ticket_type_mismatch", "expected": expected, "actual": output.ticket_type})
        if intent.task_type == "complaint" and output.priority != "urgent":
            errors.append({"code": "complaint_priority_should_be_urgent"})
        if intent.task_type == "refund_request" and output.priority not in ("high", "urgent"):
            errors.append({"code": "refund_priority_should_be_high"})
        if not output.summary.strip():
            errors.append({"code": "empty_summary"})
        if not output.suggested_action.strip():
            errors.append({"code": "empty_suggested_action"})
        return VerificationOutput(passed=not errors, errors=errors)

    # ── 审批操作校验 ──────────────────────────────────────────────

    async def verify_approval_action(
        self, *, decision: str, reviewer_note: str | None
    ) -> VerificationOutput:
        """审批决策的合法性校验。

        规则：
        1. decision 只能是 approved / rejected / needs_change
        2. rejected 时建议填写 reviewer_note
        """
        errors: list[dict[str, Any]] = []
        if decision not in ("approved", "rejected", "needs_change"):
            errors.append({"code": "invalid_decision", "decision": decision})
        if decision == "rejected" and not reviewer_note:
            errors.append({"code": "rejected_without_note"})
        return VerificationOutput(passed=not errors, errors=errors)

    # ── 订单创建终极门禁 ──────────────────────────────────────────

    async def verify_order_creation(
        self,
        *,
        draft: OrderDraft,
        risk: RiskOutput | None = None,
    ) -> VerificationOutput:
        """订单写入数据库前的最后一道防线。

        规则（缺一不可）：
        1. 用户已确认（user_confirmed = True）
        2. lock_id 和 price_snapshot 必须存在且完整
        3. 风控要求审批时，审批必须已通过（risk.requires_approval = False）
        4. service_id / technician_id / room_id 在数据库中必须存在且 active
        5. appointment_start / end 合法且未过期
        6. 数据库事务层：无技师/房间时间冲突
        """
        errors: list[dict[str, Any]] = []

        # 1. 用户已确认
        if not draft.user_confirmed:
            errors.append({"code": "user_not_confirmed"})

        # 2. lock_id + price_snapshot
        if not draft.lock_id:
            errors.append({"code": "missing_lock_id"})
        if not draft.price_snapshot:
            errors.append({"code": "missing_price_snapshot"})
        else:
            missing = REQUIRED_SNAPSHOT_FIELDS - set(draft.price_snapshot.keys())
            if missing:
                errors.append({"code": "snapshot_incomplete", "missing": sorted(missing)})

        # 3. 风控审批状态
        if risk and risk.requires_approval:
            errors.append({"code": "approval_required_not_fulfilled"})

        # 4. 实体存在性 + active 状态
        if self.catalog_repo:
            for entity_type, entity_id in [
                ("service", draft.service_id),
                ("technician", draft.technician_id),
                ("room", draft.room_id),
            ]:
                getter = getattr(self.catalog_repo, f"get_{entity_type}", None)
                if getter:
                    entity = await getter(entity_id)
                    if not entity:
                        errors.append({"code": f"{entity_type}_not_found", "id": entity_id})
                    elif getattr(entity, "status", None) != "active":
                        errors.append({"code": f"{entity_type}_inactive", "id": entity_id})

        # 5. 时间合法性
        now = datetime.now().replace(tzinfo=None)
        start = draft.appointment_start.replace(tzinfo=None) if draft.appointment_start else None
        end = draft.appointment_end.replace(tzinfo=None) if draft.appointment_end else None
        if start is None or end is None:
            errors.append({"code": "missing_appointment_time"})
        else:
            if start < now:
                errors.append({"code": "appointment_in_past"})
            if end <= start:
                errors.append({"code": "invalid_time_range"})

        # 6. DB 冲突复查（最后一道事务防线）
        if self.order_repo and start and end:
            conflicts = await self.order_repo.list_overlapping_orders(
                technician_id=draft.technician_id,
                room_id=draft.room_id,
                start=start,
                end=end,
            )
            for c in conflicts:
                errors.append({
                    "code": "creation_order_conflict",
                    "conflict_order_id": str(c.id),
                })

        return VerificationOutput(passed=not errors, errors=errors)
