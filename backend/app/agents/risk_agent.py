# 作用：RiskAgent 基于 6 维业务历史规则做综合风险评估。
# 从关键词匹配升级为：用户历史 + 技师风险 + 价格异常 + 频率检测 + 关键词 + 知识库。
import logging
from decimal import Decimal

from app.schemas.agent import IntentOutput, PriceOutput, RiskOutput

logger = logging.getLogger(__name__)

# ── 评分权重 ──────────────────────────────────────────────────────
WEIGHTS = {
    "user_cancel": 0.25,       # 用户 7 天取消
    "user_refund": 0.20,       # 用户 30 天退款
    "booking_frequency": 0.10, # 24h 预约频率
    "technician_complaint": 0.15, # 技师投诉
    "price_anomaly": 0.15,     # 价格异常
    "keywords": 0.15,          # 关键词
}
# 阈值
CANCEL_THRESHOLD = 3       # 7 天取消 >= 3 → medium+
REFUND_THRESHOLD = 3       # 30 天退款 >= 3 → high
FREQUENCY_THRESHOLD = 5    # 24h 预约 >= 5 → medium
COMPLAINT_THRESHOLD = 2    # 30 天投诉 >= 2 → medium+
PRICE_THRESHOLD = Decimal("500")  # 订单金额 ≥ 500 → medium


class RiskAgent:
    """风控 Agent——6 维业务历史规则。

    输入来源（由 Orchestrator 注入）：
    - user_message / intent / price：基本上下文
    - user_history：check_user_risk 的返回（cancel/refund/frequency）
    - tech_history：check_technician_risk 的返回（complaints/reviews）
    - price_check：check_price_anomaly 的返回（偏差检测）
    - knowledge_context：MCP RAG 查到的风控政策
    """

    name = "RiskAgent"

    async def run(
        self,
        *,
        user_message: str,
        intent: IntentOutput,
        price: PriceOutput,
        knowledge_context: str | None = None,
        user_history: dict | None = None,
        tech_history: dict | None = None,
        price_check: dict | None = None,
    ) -> RiskOutput:
        reasons: list[str] = []
        score = 0.0

        # ── 1. 用户取消历史 (weight: 0.25) ──
        if user_history:
            cancels = user_history.get("cancel_count_7d", 0)
            if cancels >= CANCEL_THRESHOLD:
                added = min(WEIGHTS["user_cancel"], cancels * 0.08)
                score += added
                reasons.append(f"用户近 7 天取消 {cancels} 次（阈值≥{CANCEL_THRESHOLD}）")

        # ── 2. 用户退款历史 (weight: 0.20) ──
        if user_history:
            refunds = user_history.get("refund_count_30d", 0)
            if refunds >= REFUND_THRESHOLD:
                added = min(WEIGHTS["user_refund"], refunds * 0.07)
                score += added
                reasons.append(f"用户近 30 天退款 {refunds} 次（阈值≥{REFUND_THRESHOLD}）")

        # ── 3. 24h 预约频率 (weight: 0.10) ──
        if user_history:
            freq = user_history.get("booking_24h", 0)
            if freq >= FREQUENCY_THRESHOLD:
                score += WEIGHTS["booking_frequency"]
                reasons.append(f"用户 24 小时内预约 {freq} 次（阈值≥{FREQUENCY_THRESHOLD}）")

        # ── 4. 技师投诉历史 (weight: 0.15) ──
        if tech_history:
            complaints = tech_history.get("complaint_count_30d", 0)
            if complaints >= COMPLAINT_THRESHOLD:
                score += WEIGHTS["technician_complaint"]
                reasons.append(f"相关技师近 30 天投诉 {complaints} 次（阈值≥{COMPLAINT_THRESHOLD}）")

        # ── 5. 价格异常 (weight: 0.15) ──
        if price_check and price_check.get("anomaly"):
            score += WEIGHTS["price_anomaly"]
            reasons.append(f"价格异常：数据库价格 ¥{price_check.get('db_price', '?')}，实际 ¥{price_check.get('final_price', '?')}")
        elif price.final_price >= PRICE_THRESHOLD:
            score += WEIGHTS["price_anomaly"] * 0.5  # 高价减半权
            reasons.append(f"订单金额 ¥{price.final_price} ≥ ¥{PRICE_THRESHOLD}，建议复核")

        # ── 6. 关键词风控 (weight: 0.15, 触红线直接 high) ──
        red_line_keywords = ["特殊服务", "加钟不登记", "现金私下", "不要记录"]
        if any(w in user_message for w in red_line_keywords):
            reasons.append("用户消息含风控敏感关键词，触发红线规则")
            return RiskOutput(risk_level="high", risk_score=0.95, reasons=reasons, requires_approval=True)

        # ── 7. 售后类任务加基础分 ──
        if intent.task_type in {"refund_request", "complaint"}:
            score += 0.3
            reasons.append("当前请求为售后或投诉类型")

        # ── 8. 知识库附加 ──
        if knowledge_context and score >= 0.3:
            reasons.append("风控政策库已匹配，详见审计记录")

        # ── 归一化 + 分级 ──
        score = round(min(score, 1.0), 2)
        if score >= 0.6:
            risk_level = "high"
        elif score >= 0.3:
            risk_level = "medium"
        else:
            risk_level = "low"

        return RiskOutput(
            risk_level=risk_level,
            risk_score=score,
            reasons=reasons,
            requires_approval=score >= 0.3,
        )
