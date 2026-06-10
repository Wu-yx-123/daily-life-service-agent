# 作用：CustomerServiceAgent 负责取消、改期、退款和投诉的售后建议生成。
# Phase 3: LLM 主力生成精准建议，整合知识库政策上下文，确定性规则兜底。
import logging

from app.schemas.agent import CustomerServiceOutput, IntentOutput

logger = logging.getLogger(__name__)

# LLM 系统提示词
CS_SYSTEM_PROMPT = """你是按摩门店的售后处理专家。根据用户诉求和相关政策，生成售后工单建议。

## 输出 JSON 格式
{"ticket_type": "complaint|refund_request|reschedule_order|cancel_order",
 "priority": "normal|high|urgent",
 "summary": "用户诉求一句话摘要",
 "suggested_action": "具体处理建议，引用政策条款，分步骤列出"}

## 规则
- 投诉 → urgent，退款 → high，改期/取消 → normal
- summary 简洁概括用户诉求，不超过 30 字
- suggested_action 分步骤列出具体处理动作，引用相关政策条款"""


class CustomerServiceAgent:
    """售后 Agent。

    策略：
    1. LLM 主力：结合用户消息 + 意图 + 知识库政策 → 精准建议
    2. 确定性规则兜底：LLM 不可用时
    """

    name = "CustomerServiceAgent"

    async def run(
        self,
        *,
        message: str,
        intent: IntentOutput,
        knowledge_context: str | None = None,
    ) -> CustomerServiceOutput:
        policy_text = knowledge_context or ""

        # 尝试 LLM
        try:
            return await self._llm_run(message, intent, policy_text)
        except Exception as exc:
            logger.warning("CS Agent LLM 失败，回退规则：%s", exc)

        # 确定性回退
        if intent.task_type == "complaint":
            return self._fallback_complaint(message, policy_text)
        if intent.task_type == "refund_request":
            return self._fallback_refund(message, policy_text)
        if intent.task_type == "reschedule_order":
            return self._fallback_reschedule(message, policy_text)
        return self._fallback_cancel(message, policy_text)

    # ── LLM 路径 ───────────────────────────────────────────────────

    @staticmethod
    async def _llm_run(message: str, intent: IntentOutput, policy: str) -> CustomerServiceOutput:
        from app.core.model_provider import ChatMessage, create_model_provider

        task_map = {
            "complaint": "complaint", "refund_request": "refund_request",
            "reschedule_order": "reschedule_order", "cancel_order": "cancel_order",
        }
        ticket_type = task_map.get(intent.task_type, "cancel_order")

        user_prompt = f"""用户诉求：{message}
任务类型：{intent.task_type}（{ticket_type}）
相关政策：{policy if policy else "无相关政策文档"}"""

        provider = create_model_provider()
        result = await provider.chat_structured(
            messages=[
                ChatMessage(role="system", content=CS_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_prompt),
            ],
            schema=CustomerServiceOutput,
            temperature=0.3,
            max_tokens=512,
        )
        logger.info("CS Agent LLM: type=%s priority=%s", result.ticket_type, result.priority)
        return result

    # ── 确定性回退 ─────────────────────────────────────────────────

    @staticmethod
    def _fallback_complaint(message: str, policy: str) -> CustomerServiceOutput:
        action = "请管理员优先联系用户，查看关联订单和技师记录。"
        if policy:
            action = f"根据投诉处理标准：{policy[:120]}... 请管理员优先联系用户致歉并核实详情。"
        return CustomerServiceOutput(ticket_type="complaint", priority="urgent",
                                     summary=f"用户投诉：{message}", suggested_action=action)

    @staticmethod
    def _fallback_refund(message: str, policy: str) -> CustomerServiceOutput:
        action = "请核对订单状态和退款金额，高金额退款需人工审批。"
        if policy:
            action = f"根据退款政策：{policy[:150]}... 请核实后按标准处理。"
        return CustomerServiceOutput(ticket_type="refund_request", priority="high",
                                     summary=f"用户申请退款：{message}", suggested_action=action)

    @staticmethod
    def _fallback_reschedule(message: str, policy: str) -> CustomerServiceOutput:
        action = "请确认原订单和用户期望时间，重新检查排班后改期。"
        if policy:
            action = f"根据门店规则：{policy[:120]}... 请确认是否在允许改期的窗口内。"
        return CustomerServiceOutput(ticket_type="reschedule_order", priority="normal",
                                     summary=f"用户申请改期：{message}", suggested_action=action)

    @staticmethod
    def _fallback_cancel(message: str, policy: str) -> CustomerServiceOutput:
        action = "请确认订单是否在可取消窗口内。"
        if policy:
            action = f"根据门店规则：{policy[:120]}... 请确认是否符合取消条件。"
        return CustomerServiceOutput(ticket_type="cancel_order", priority="normal",
                                     summary=f"用户申请取消：{message}", suggested_action=action)
