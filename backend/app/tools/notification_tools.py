# 作用：通知工具，供 OrderAgent、CustomerServiceAgent 调用。
# Phase 1 用日志模拟；Phase 4+ 可接入真实短信 / 邮件 / 站内信。
import logging

logger = logging.getLogger("massageops.notification")


async def send_booking_confirmation(
    *,
    user_id: str,
    order_id: str,
    appointment_start: str | None = None,
    service_name: str | None = None,
    technician_name: str | None = None,
    **kwargs,
) -> dict:
    """发送预约确认通知。

    Phase 1: 日志模拟。Phase 4+: 接入短信/邮件/微信模板消息。
    """
    logger.info(
        "📩 [MOCK] 预约确认通知 → user=%s order=%s time=%s service=%s tech=%s",
        user_id, order_id, appointment_start, service_name, technician_name,
    )
    return {"sent": True, "channel": "log", "order_id": order_id}


async def notify_admin(
    *,
    trace_id: str,
    event: str,
    detail: str | None = None,
    **kwargs,
) -> dict:
    """通知管理员（高风险订单、投诉等需要人工介入的场景）。

    Phase 1: 日志模拟。Phase 4+: 接入钉钉/飞书/企微机器人。
    """
    logger.warning(
        "🔔 [MOCK] 管理员通知 → trace=%s event=%s detail=%s",
        trace_id, event, detail,
    )
    return {"sent": True, "channel": "log", "trace_id": trace_id}


async def send_after_sales_notification(
    *,
    user_id: str,
    ticket_id: str,
    ticket_type: str,
    suggested_action: str | None = None,
    **kwargs,
) -> dict:
    """发送售后处理进度通知。

    Phase 1: 日志模拟。
    """
    logger.info(
        "📩 [MOCK] 售后通知 → user=%s ticket=%s type=%s action=%s",
        user_id, ticket_id, ticket_type, suggested_action,
    )
    return {"sent": True, "channel": "log", "ticket_id": ticket_id}
