# 作用：IntentAgent 负责解析中文自然语言预约/售后请求，输出结构化意图。
# Phase 2: 主力使用 LLM + structured output，确定性正则作为降级回退。
import json
import logging
import re
from datetime import datetime, time, timedelta
from decimal import Decimal

from app.schemas.agent import IntentOutput, IntentSlots

logger = logging.getLogger(__name__)

REQUIRED_BOOKING_SLOTS = {"service_type", "preferred_time", "duration_minutes"}

# LLM 系统提示词：告诉模型如何解析按摩预约场景的用户自然语言
INTENT_SYSTEM_PROMPT = """你是一个按摩预约系统的意图解析器。将用户的自然语言消息解析为结构化 JSON。

## 任务类型 (task_type)
- book_appointment：用户想预约按摩/SPA/理疗服务。即使没指定具体项目，只要表达了放松/调理意愿，就是预约类。
- reschedule_order：改期、修改已有预约的时间
- cancel_order：取消已有预约
- refund_request：要求退款、退费
- complaint：投诉技师态度、迟到、环境、手法等
- service_query：咨询了解服务项目或会员优惠，注意区分：如果问"有什么服务/会员优惠"但不表达预约意愿，是 service_query
- store_query：咨询门店地址、营业时间等
- ops_analysis：商家查运营数据
- unknown：无法判断

## 槽位提取（从原文提取，不臆造）
1. service_type: 按摩/SPA/理疗的具体类型。从用户描述推断：脖子不舒服→肩颈按摩，腰酸→全身按摩或腰部理疗。没有提到具体部位或项目则为 null。
2. duration_minutes: 服务时长。"90分钟"→90，"半小时"→30，"一个半小时"→90，"一小时"→60。没有数字则为 null。
3. preferred_time: 结合当前时间将相对时间转为 ISO 8601。"下周三下午3点"→下一个周三15:00，"今晚8点"→今天20:00。注意区分上下午。
4. budget_max: 预算上限数字。"300以内"→300，"不超过500"→500。只提取数字，不要单位。
5. strength_preference: "重一点/力度重/受力"→heavy，"轻一点/轻柔/放松"→light。
6. missing_slots: 预约必需但缺失的字段。service_type 缺失时写 "service_type"，preferred_time 缺失时写 "preferred_time"。

## 重要
- 所有数值字段提取具体数字，不要返回 null 如果原文有明确数字。
- confidence 反映提取置信度。槽位齐全 0.9-1.0，缺关键槽位 0.7-0.89。"""


class IntentAgent:
    """意图识别 Agent。

    策略：LLM 主力（高准确率、覆盖更多表达变体） → 确定性正则回退（LLM 不可用时）。
    """

    name = "IntentAgent"

    # ── 正则回退规则（Phase 1 逻辑保留） ──────────────────────────

    _CANCEL_KEYWORDS = {"取消", "退订", "不做了", "不要了"}
    _RESCHEDULE_KEYWORDS = {"改期", "改时间", "换个时间", "修改预约", "调整到"}
    _REFUND_KEYWORDS = {"退款", "退钱", "退费"}
    _COMPLAINT_KEYWORDS = {"投诉", "态度", "迟到", "不满意", "差评"}
    _STRENGTH_HEAVY = {"重一点", "力度重", "偏重", "受力", "重点"}
    _STRENGTH_LIGHT = {"轻一点", "轻柔", "放松一点", "轻一些", "不要太重"}

    @classmethod
    def _regex_run(cls, message: str) -> IntentOutput:
        """确定性正则解析（LLM 不可用时的回退）。"""
        task_type = "book_appointment"
        for kw in cls._REFUND_KEYWORDS:
            if kw in message:
                task_type = "refund_request"
                break
        else:
            for kw in cls._CANCEL_KEYWORDS:
                if kw in message:
                    task_type = "cancel_order"
                    break
            else:
                for kw in cls._RESCHEDULE_KEYWORDS:
                    if kw in message:
                        task_type = "reschedule_order"
                        break
                else:
                    for kw in cls._COMPLAINT_KEYWORDS:
                        if kw in message:
                            task_type = "complaint"
                            break

        duration = cls._extract_duration(message)
        preferred_time = cls._extract_time(message)
        strength = None
        if any(w in message for w in cls._STRENGTH_HEAVY):
            strength = "heavy"
        elif any(w in message for w in cls._STRENGTH_LIGHT):
            strength = "light"

        service_type = cls._extract_service_type(message)

        budget = cls._extract_budget(message)
        missing: list[str] = []
        if task_type == "book_appointment":
            if not service_type:
                missing.append("service_type")
            if not preferred_time:
                missing.append("preferred_time")
        return IntentOutput(
            task_type=task_type,
            slots=IntentSlots(
                service_type=service_type,
                duration_minutes=duration,
                preferred_time=preferred_time,
                budget_max=budget,
                strength_preference=strength,
            ),
            missing_slots=missing,
            confidence=0.85 if not missing else 0.55,
        )

    # ── LLM 主力方法 ──────────────────────────────────────────────

    async def _llm_run(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        memory_context: dict | None = None,
    ) -> IntentOutput:
        """使用 LLM + structured output 解析意图，带多轮对话上下文。"""
        from app.core.model_provider import ChatMessage, create_model_provider

        provider = create_model_provider()
        now = datetime.now()
        context = (
            f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}，"
            f"星期{['一','二','三','四','五','六','日'][now.weekday()]}。"
        )
        if memory_context:
            # 长期偏好只作为“辅助理解上下文”，真正是否补全槽位由 MemoryService 再做确定性处理。
            context += (
                "\n用户长期偏好画像："
                f"{json.dumps(memory_context.get('defaults', {}), ensure_ascii=False)}。"
                "这些偏好只用于辅助理解，不要覆盖用户本轮明确表达。"
            )
            semantic = memory_context.get("semantic_memories") or []
            if semantic:
                context += (
                    "\n用户相关语义记忆："
                    f"{json.dumps(semantic[:5], ensure_ascii=False)}。"
                    "这些记忆用于理解用户背景，不代表本轮已确认的预约信息。"
                )
        messages = [ChatMessage(role="system", content=INTENT_SYSTEM_PROMPT)]

        # 注入历史对话（最近 6 轮）
        for h in (history or [])[-6:]:
            messages.append(ChatMessage(role=h.get("role", "user"), content=h.get("content", "")))

        # 加上当前消息和指示
        messages.append(ChatMessage(role="user", content=f"{context}\n\n用户输入：{message}\n\n请解析意图并输出 JSON。"))

        result = await provider.chat_structured(
            messages=messages,
            schema=IntentOutput,
            temperature=0.1,
            max_tokens=1024,
        )
        if result.slots.preferred_time is not None:
            result.slots.preferred_time = result.slots.preferred_time.replace(tzinfo=None)
        return result

    # ── 统一入口 ──────────────────────────────────────────────────

    async def run(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        memory_context: dict | None = None,
    ) -> IntentOutput:
        """解析用户自然语言，优先 LLM，不可用时回退正则。

        Args:
            message: 当前用户输入
            history: 对话历史 [{"role": "user"|"assistant", "content": "..."}, ...]
            memory_context: 长期偏好画像，用于辅助理解和槽位补全
        """
        try:
            # LLM 先结合对话历史和长期偏好做语义解析；失败时仍有正则兜底。
            result = await self._llm_run(message, history, memory_context)
            result = self._apply_explicit_slots(message, result)
            logger.info("IntentAgent LLM: task=%s slots=%s missing=%s conf=%.2f",
                        result.task_type, result.slots.model_dump(exclude_none=True),
                        result.missing_slots, result.confidence)
            return result
        except Exception as exc:
            logger.warning("LLM 意图解析失败，回退正则：%s", exc)
            result = self._regex_run(message)
            logger.info("IntentAgent regex: task=%s missing=%s",
                        result.task_type, result.missing_slots)
            return result

    # ── 正则辅助方法（_regex_run 和 _llm_run 共用） ──────────────

    @staticmethod
    def _extract_duration(message: str) -> int | None:
        m = re.search(r"(\d+)\s*分钟", message)
        if m:
            return int(m.group(1))
        # 常见中文表达
        for text, val in [("半小时", 30), ("一个半小时", 90), ("一小时", 60), ("两小时", 120), ("1.5小时", 90), ("2小时", 120)]:
            if text in message:
                return val
        return None

    @staticmethod
    def _extract_service_type(message: str) -> str | None:
        service_map = [
            (("精油", "SPA", "spa", "芳香"), "精油SPA"),
            (("肩颈", "颈肩", "脖子"), "肩颈按摩"),
            (("全身",), "全身按摩"),
            (("足底", "足疗", "足部", "脚"), "足部养护"),
            (("拉伸", "运动", "筋膜"), "运动拉伸"),
            (("推拿", "经络", "中式"), "中式推拿"),
            (("头",), "头部理疗"),
            (("泰式",), "泰式按摩"),
            (("刮痧",), "刮痧理疗"),
            (("拔罐",), "拔罐理疗"),
        ]
        for keywords, service_type in service_map:
            if any(keyword in message for keyword in keywords):
                return service_type
        return None

    @classmethod
    def _apply_explicit_slots(cls, message: str, result: IntentOutput) -> IntentOutput:
        """当前消息里明确出现的槽位优先级最高，避免被历史上下文或长期记忆带偏。"""
        updated = result.model_copy(deep=True)
        filled: list[str] = []
        service_type = cls._extract_service_type(message)
        if service_type:
            updated.slots.service_type = service_type
            filled.append("service_type")
        duration = cls._extract_duration(message)
        if duration:
            updated.slots.duration_minutes = duration
            filled.append("duration_minutes")
        preferred_time = cls._extract_time(message)
        if preferred_time:
            updated.slots.preferred_time = preferred_time
            filled.append("preferred_time")
        budget = cls._extract_budget(message)
        if budget:
            updated.slots.budget_max = budget
        if any(w in message for w in cls._STRENGTH_HEAVY):
            updated.slots.strength_preference = "heavy"
        elif any(w in message for w in cls._STRENGTH_LIGHT):
            updated.slots.strength_preference = "light"
        if filled:
            updated.missing_slots = [slot for slot in updated.missing_slots if slot not in filled]
        updated.missing_slots = [slot for slot in updated.missing_slots if slot in REQUIRED_BOOKING_SLOTS]
        return updated

    @staticmethod
    def _extract_budget(message: str) -> Decimal | None:
        for pat in [r"预算\s*(\d+)", r"(\d+)\s*以内", r"不超过\s*(\d+)", r"(\d+)\s*左右"]:
            m = re.search(pat, message)
            if m:
                return Decimal(m.group(1))
        return None

    @staticmethod
    def _extract_time(message: str) -> datetime | None:
        m = re.search(
            r"(?:(\d{1,2})月(\d{1,2})日)?\s*"
            r"(今晚|今天|明天|后天)?\s*"
            r"(早上|上午|中午|下午|晚上)?\s*"
            r"(\d{1,2}|[一二两三四五六七八九十]{1,3})点",
            message,
        )
        if not m:
            return None
        month_text, day_text, day_word, period, hour_text = m.groups()
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
            hour += 12  # "3点" 大概率是下午3点
        return datetime.combine(day, time(hour, 0))


def _parse_chinese_hour(value: str) -> int:
    """把中文小时转成数字，覆盖“八点/十二点/二十三点”等常见表达。"""
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + digits.get(value[-1], 0)
    if "十" in value:
        left, right = value.split("十", 1)
        return digits.get(left, 0) * 10 + (digits.get(right, 0) if right else 0)
    return digits.get(value, 0)
