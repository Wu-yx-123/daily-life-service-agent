# 作用：多轮对话槽位冲突消解，确保当前用户显式修改能覆盖旧 State 并清理下游结果。
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from app.schemas.agent import IntentOutput


CORRECTION_MARKERS = ("不对", "不是", "改成", "换成", "改到", "调整到", "还是", "算了")

DOWNSTREAM_INVALIDATION: dict[str, set[str]] = {
    "service_type": {
        "candidates", "selected_option", "schedule_check", "price_result",
        "risk_result", "order_draft", "approval_request",
    },
    "duration_minutes": {
        "candidates", "selected_option", "schedule_check", "price_result",
        "risk_result", "order_draft", "approval_request",
    },
    "preferred_time": {
        "schedule_check", "risk_result", "order_draft", "approval_request",
    },
    "budget_max": {
        "candidates", "selected_option", "price_result", "risk_result", "order_draft",
    },
    "technician_preference": {
        "candidates", "selected_option", "schedule_check", "risk_result", "order_draft",
    },
}


@dataclass(frozen=True)
class TimeMention:
    text: str
    value: datetime
    start: int
    end: int


class SlotResolutionGate:
    """确定性槽位消解器。

    规则：
    - 当前用户显式修正优先于上一轮 State。
    - 当前消息出现多个同类槽位且无修正词时，要求用户确认。
    - 关键槽位变化时，清理依赖它的下游结果，避免旧草稿/旧时间锁污染本轮。
    """

    def resolve(
        self,
        *,
        current: IntentOutput,
        previous_raw: Any | None,
        message: str,
    ) -> dict[str, Any]:
        previous = self._parse_previous(previous_raw)
        resolved = current.model_copy(deep=True)
        conflicts: list[dict[str, Any]] = []
        changed_slots: list[str] = []

        time_mentions = self._extract_time_mentions(message)
        if len(time_mentions) > 1:
            if self._has_correction_marker_between(message, time_mentions):
                chosen = time_mentions[-1]
                resolved.slots.preferred_time = chosen.value
                resolved.missing_slots = [
                    slot for slot in resolved.missing_slots if slot != "preferred_time"
                ]
            else:
                conflicts.append({
                    "slot": "preferred_time",
                    "conflict_type": "multiple_values",
                    "candidates": [m.value.isoformat() for m in time_mentions],
                    "question": self._time_confirmation_question(time_mentions),
                })

        if previous and previous.task_type == resolved.task_type == "book_appointment":
            changed_slots = self._changed_slots(previous, resolved)

        invalidated = sorted({
            key
            for slot in changed_slots
            for key in DOWNSTREAM_INVALIDATION.get(slot, set())
        })

        requires_confirmation = bool(conflicts)
        return {
            "intent": resolved,
            "slot_resolution": {
                "changed_slots": changed_slots,
                "conflicts": conflicts,
                "requires_confirmation": requires_confirmation,
                "invalidated_state_keys": invalidated,
            },
            "requires_confirmation": requires_confirmation,
            "confirmation_question": conflicts[0]["question"] if conflicts else None,
            "invalidated_state_keys": invalidated,
        }

    @staticmethod
    def _parse_previous(previous_raw: Any | None) -> IntentOutput | None:
        if not previous_raw:
            return None
        try:
            return IntentOutput.model_validate(previous_raw)
        except Exception:
            return None

    @staticmethod
    def _changed_slots(previous: IntentOutput, current: IntentOutput) -> list[str]:
        changed: list[str] = []
        for slot in (
            "service_type",
            "duration_minutes",
            "preferred_time",
            "budget_max",
            "technician_preference",
        ):
            before = getattr(previous.slots, slot)
            after = getattr(current.slots, slot)
            if before is not None and after is not None and _normalize_slot_value(before) != _normalize_slot_value(after):
                changed.append(slot)
        return changed

    @staticmethod
    def _extract_time_mentions(message: str) -> list[TimeMention]:
        pattern = re.compile(
            r"(?:(\d{1,2})月(\d{1,2})日)?\s*"
            r"(今晚|今天|明天|后天)?\s*"
            r"(早上|上午|中午|下午|晚上)?\s*"
            r"(\d{1,2}|[一二两三四五六七八九十]{1,3})点"
        )
        mentions: list[TimeMention] = []
        for match in pattern.finditer(message):
            value = _parse_time_match(match)
            if value:
                mentions.append(TimeMention(
                    text=match.group(0).strip(),
                    value=value,
                    start=match.start(),
                    end=match.end(),
                ))
        return mentions

    @staticmethod
    def _has_correction_marker_between(message: str, mentions: list[TimeMention]) -> bool:
        if len(mentions) < 2:
            return False
        between = message[mentions[0].end:mentions[-1].start]
        return any(marker in between for marker in CORRECTION_MARKERS)

    @staticmethod
    def _time_confirmation_question(mentions: list[TimeMention]) -> str:
        choices = "，还是".join(m.value.strftime("%m月%d日 %H:%M") for m in mentions[:3])
        return f"您提到了多个预约时间，请确认是 {choices}？"


def _normalize_slot_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _parse_time_match(match: re.Match[str]) -> datetime | None:
    month_text, day_text, day_word, period, hour_text = match.groups()
    now = datetime.now()
    day = now.date()
    if month_text and day_text:
        day = datetime(now.year, int(month_text), int(day_text)).date()
        if day < now.date():
            day = datetime(now.year + 1, int(month_text), int(day_text)).date()
    offset_map = {"明天": 1, "后天": 2}
    if day_word in offset_map:
        day += timedelta(days=offset_map[day_word])
    hour = int(hour_text) if hour_text.isdigit() else _parse_chinese_hour(hour_text)
    if ((day_word or "") == "今晚" or period in {"下午", "晚上"}) and hour < 12:
        hour += 12
    if period == "中午" and hour < 11:
        hour += 12
    if hour < 6:
        hour += 12
    if not 0 <= hour <= 23:
        return None
    return datetime.combine(day, time(hour, 0))


def _parse_chinese_hour(value: str) -> int:
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + digits.get(value[-1], 0)
    if "十" in value:
        left, right = value.split("十", 1)
        return digits.get(left, 0) * 10 + (digits.get(right, 0) if right else 0)
    return digits.get(value, 0)
