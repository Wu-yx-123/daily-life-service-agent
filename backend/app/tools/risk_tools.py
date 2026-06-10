# 作用：风控检查和风险记录工具，供 RiskAgent 调用。
from app.repositories.order_repo import OrderRepository
from app.schemas.agent import RiskOutput


async def check_user_risk(
    *,
    order_repo: OrderRepository,
    user_id: str,
    **kwargs,
) -> dict:
    """查询用户历史风险指标：7 天取消 / 30 天退款次数等。

    返回结果供 RiskAgent 做规则判断；RiskAgent 不直接写库。
    """
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select, func
    from app.models.order import Order

    db = order_repo.db
    now = datetime.now(UTC).replace(tzinfo=None)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    cancel_count = int(
        await db.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order.user_id == user_id,
                Order.status == "cancelled",
                Order.updated_at >= seven_days_ago,
            )
        ) or 0
    )

    refund_count = int(
        await db.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order.user_id == user_id,
                Order.status == "refunded",
                Order.updated_at >= thirty_days_ago,
            )
        ) or 0
    )

    total_orders = int(
        await db.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.user_id == user_id)
        ) or 0
    )

    # 24h 预约频率
    one_day_ago = now - timedelta(hours=24)
    booking_24h = int(
        await db.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.user_id == user_id, Order.created_at >= one_day_ago)
        ) or 0
    )

    return {
        "user_id": user_id,
        "cancel_count_7d": cancel_count,
        "refund_count_30d": refund_count,
        "total_orders": total_orders,
        "booking_24h": booking_24h,
    }


async def check_technician_risk(
    *,
    order_repo: OrderRepository,
    technician_id: str,
    **kwargs,
) -> dict:
    """查询技师近 30 天投诉/差评次数。"""
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select, func
    from app.models.after_sales import AfterSalesTicket
    from app.models.business import Review

    db = order_repo.db
    thirty_days_ago = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)

    complaint_count = int(
        await db.scalar(
            select(func.count())
            .select_from(AfterSalesTicket)
            .where(
                AfterSalesTicket.ticket_type.in_(["complaint"]),
                AfterSalesTicket.created_at >= thirty_days_ago,
            )
        ) or 0
    )

    negative_reviews = int(
        await db.scalar(
            select(func.count())
            .select_from(Review)
            .where(Review.sentiment == "negative", Review.created_at >= thirty_days_ago)
        ) or 0
    )

    return {
        "technician_id": technician_id,
        "complaint_count_30d": complaint_count,
        "negative_reviews_30d": negative_reviews,
    }


async def check_price_anomaly(
    *,
    order_repo: OrderRepository,
    service_id: str,
    final_price: float,
    **kwargs,
) -> dict:
    """检测价格异常：与数据库原价偏差超过 50% 视为异常。"""
    from app.models.business import Service
    from decimal import Decimal

    db = order_repo.db
    svc = await db.get(Service, service_id)
    if not svc:
        return {"anomaly": True, "reason": "service not found"}
    base = Decimal(str(svc.base_price))
    price = Decimal(str(final_price))
    if price <= Decimal("0"):
        return {"anomaly": True, "reason": "zero or negative price", "db_price": float(base)}
    ratio = abs(price - base) / base
    return {
        "anomaly": ratio > Decimal("0.5"),
        "ratio": float(ratio),
        "db_price": float(base),
        "final_price": float(price),
    }


async def create_risk_record(
    *,
    order_repo: OrderRepository,
    trace_id: str,
    risk_level: str,
    reasons: list[str],
    user_id: str,
    metadata: dict | None = None,
    **kwargs,
) -> dict:
    """创建风控记录（写入 harness.risk_records 表）。"""
    from app.models.harness import RiskRecord

    db = order_repo.db
    record = RiskRecord(
        trace_id=trace_id,
        risk_level=risk_level,
        reasons=reasons,
        user_id=user_id,
        metadata=metadata or {},
    )
    db.add(record)
    await db.flush()
    return {
        "id": str(record.id),
        "trace_id": record.trace_id,
        "risk_level": record.risk_level,
        "reasons": record.reasons,
    }
