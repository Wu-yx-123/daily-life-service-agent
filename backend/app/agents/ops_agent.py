# 作用：OpsAgent 负责根据经营指标生成运营建议。
from decimal import Decimal

from app.schemas.agent import OpsReportResponse


class OpsAgent:
    """运营分析 Agent。

    当前基于结构化统计生成建议，后续可接入 Elasticsearch 日志和更完整的经营指标。
    """

    name = "OpsAgent"

    async def run(
        self,
        *,
        order_count: int,
        revenue_total: Decimal,
        after_sales_open_count: int,
        pending_approval_count: int,
        review_count: int,
        average_rating: float | None,
        negative_review_count: int,
    ) -> OpsReportResponse:
        """生成运营报表和建议。"""
        suggestions: list[str] = []
        if order_count == 0:
            suggestions.append("当前暂无订单，可先验证预约入口和 Demo 数据。")
        if after_sales_open_count > 0:
            suggestions.append("存在开放售后工单，请优先处理取消、退款、投诉等用户请求。")
        if pending_approval_count > 0:
            suggestions.append("存在待审批风险请求，请管理员及时复核，避免用户长时间等待。")
        if average_rating is not None and average_rating < 4:
            suggestions.append("平均评分低于 4 分，建议查看差评标签并复盘服务体验。")
        if negative_review_count > 0:
            suggestions.append("存在负向评价，建议重点检查技师手法、等待时间和服务态度。")
        if not suggestions:
            suggestions.append("当前核心指标稳定，可继续观察预约转化和复购表现。")
        return OpsReportResponse(
            order_count=order_count,
            revenue_total=revenue_total,
            after_sales_open_count=after_sales_open_count,
            pending_approval_count=pending_approval_count,
            review_count=review_count,
            average_rating=average_rating,
            negative_review_count=negative_review_count,
            suggestions=suggestions,
        )
