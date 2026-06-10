# 作用：长期记忆服务，负责召回用户偏好和在业务成功后沉淀偏好。
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.memory_repo import MemoryRepository
from app.schemas.agent import IntentOutput

STRONG_CONFIDENCE = Decimal("0.65")
# 置信度达到该阈值后才会进入 defaults，用于补全 Intent 或影响推荐。


class MemoryService:
    """用户长期记忆服务。

    当前版本只沉淀结构化偏好，先保证可解释、可测试、可删除；语义向量记忆可以后续并行扩展。
    """

    def __init__(self, db: AsyncSession, repo: MemoryRepository | None = None):
        self.db = db
        self.repo = repo or MemoryRepository(db)

    async def retrieve_for_user(self, *, user_id: str) -> dict[str, Any]:
        """召回用户长期偏好，返回可直接放入 AgentState 的 JSON。"""
        # 仓储层返回按置信度和时间排好序的偏好记录。
        prefs = await self.repo.list_user_preferences(user_id=user_id)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pref in prefs:
            # 这里转成纯 JSON，保证 AgentState、Trace 和 Redis 缓存都能直接序列化。
            item = {
                "value": pref.preference_value,
                "confidence": float(pref.confidence),
                "seen_count": pref.seen_count,
                "source": pref.source,
                "evidence": pref.evidence,
                "last_seen_at": pref.last_seen_at.isoformat() if pref.last_seen_at else None,
            }
            grouped[pref.preference_type].append(item)

        # 每个偏好类型只把最高置信度的值作为默认值，低置信度仍保留在 preferences 里供展示/分析。
        defaults = {
            key: values[0]["value"]
            for key, values in grouped.items()
            if values and Decimal(str(values[0]["confidence"])) >= STRONG_CONFIDENCE
        }
        return {"preferences": dict(grouped), "defaults": defaults}

    @staticmethod
    def apply_to_intent(intent: IntentOutput, memory: dict[str, Any] | None) -> IntentOutput:
        """用强偏好补全 Intent 中缺失的非时间槽位。

        时间偏好只用于推荐排序和提示，不直接生成具体预约时间，避免把“常约晚上”误当成用户本次确认时间。
        """
        if not memory:
            return intent
        defaults = memory.get("defaults") or {}
        if not defaults:
            return intent

        # 不直接修改原始 Intent，避免 Trace 中输入输出对象互相污染。
        updated = intent.model_copy(deep=True)
        slots = updated.slots
        filled: list[str] = []
        # 服务类型、力度和技师是“偏好槽位”，适合在用户本轮没说时补全。
        # 历史预算不能自动变成本轮硬约束，否则会把更贵但用户明确要求的项目过滤掉。
        if not slots.service_type and defaults.get("service_type"):
            slots.service_type = defaults["service_type"]
            filled.append("service_type")
        if not slots.strength_preference and defaults.get("strength"):
            slots.strength_preference = defaults["strength"]
            filled.append("strength_preference")
        if not slots.technician_preference and defaults.get("technician_name"):
            slots.technician_preference = defaults["technician_name"]
            filled.append("technician_preference")
        if filled:
            # 只移除被长期记忆补全的缺槽，preferred_time 等强确认字段仍需要用户本轮明确给出。
            updated.missing_slots = [slot for slot in updated.missing_slots if slot not in filled]
            updated.confidence = min(1.0, updated.confidence + 0.05)
        return updated

    async def record_booking_preferences(
        self,
        *,
        user_id: str,
        state: dict[str, Any],
        order_id: str | None = None,
    ) -> None:
        """在预约确认成功后沉淀用户偏好。"""
        # 只在订单确认成功后写长期记忆，避免用户随口咨询就污染画像。
        intent_raw = state.get("intent") or {}
        selected = state.get("selected_option") or {}
        draft = state.get("order_draft") or {}
        intent = IntentOutput.model_validate(intent_raw) if intent_raw else None

        # evidence 是记忆的证据链，后续可以用于用户画像解释、审计和删除。
        evidence = {
            "trace_id": state.get("trace_id"),
            "session_id": state.get("session_id"),
            "order_id": order_id,
            "message": state.get("user_message"),
        }

        writes: list[tuple[str, str]] = []
        # 服务偏好优先取用户明确意图；没有意图时退回到最终选中的服务名称。
        if intent and intent.slots.service_type:
            writes.append(("service_type", intent.slots.service_type))
        elif selected.get("service_name"):
            writes.append(("service_type", selected["service_name"]))

        # 力度和预算来自 Intent，是用户自然语言中表达出的稳定偏好候选。
        if intent and intent.slots.strength_preference:
            writes.append(("strength", intent.slots.strength_preference))
        if intent and intent.slots.budget_max:
            writes.append(("budget_max", str(intent.slots.budget_max)))
        elif draft.get("final_price"):
            # 用户没说预算时，用实际成交价作为弱预算记忆。
            writes.append(("budget_max", str(draft["final_price"])))

        # 最终选择的技师可以作为后续个性化推荐的排序信号。
        if selected.get("technician_name"):
            writes.append(("technician_name", selected["technician_name"]))
        if draft.get("appointment_start"):
            # 时间只沉淀为粗粒度时段，避免下次直接臆造具体日期时间。
            time_window = _time_window(draft["appointment_start"])
            if time_window:
                writes.append(("time_window", time_window))

        for pref_type, value in writes:
            # 仓储层负责同类偏好去重和置信度累加。
            await self.repo.upsert_preference(
                user_id=user_id,
                preference_type=pref_type,
                preference_value=value,
                source="booking_confirmed",
                evidence=evidence,
            )
        await self.db.commit()


def _time_window(value: Any) -> str | None:
    """把具体预约时间归纳成早/午/晚偏好，不保存过细时间点。"""
    dt: datetime | None = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            # 时间格式异常时不写时间偏好，保证记忆写入失败不会影响订单确认。
            return None
    if not dt:
        return None
    hour = dt.hour
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    return "evening"
