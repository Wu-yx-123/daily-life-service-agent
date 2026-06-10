# 作用：Agent 工具权限白名单 + 越权拒绝日志。
import logging

logger = logging.getLogger(__name__)

AGENT_TOOL_PERMISSIONS: dict[str, list[str]] = {
    "IntentAgent": [],
    "MatchAgent": ["search_services", "get_service_detail", "search_technicians",
                   "search_stores", "search_services_by_keyword"],
    "ScheduleAgent": ["check_schedule", "create_time_lock", "release_time_lock", "check_order_conflicts"],
    "PriceAgent": ["calculate_price", "calculate_discounted_price", "list_available_coupons"],
    "RiskAgent": ["check_user_risk", "create_risk_record"],
    "OrderAgent": ["create_order", "get_order", "list_user_orders", "send_booking_confirmation"],
    "CustomerServiceAgent": ["get_order", "list_user_orders",
                             "send_after_sales_notification", "notify_admin"],
    "OpsAgent": [],
    "KnowledgeAgent": ["search_knowledge", "search_services_by_keyword"],
    "PlannerAgent": [],
}


class PermissionManager:
    """工具权限校验 + 越权审计。"""

    def check(self, agent_name: str, tool_name: str) -> None:
        allowed = AGENT_TOOL_PERMISSIONS.get(agent_name, [])
        if tool_name not in allowed:
            logger.warning(
                "PERMISSION_DENIED agent=%s tool=%s allowed=%s",
                agent_name, tool_name, allowed,
            )
            raise PermissionError(f"{agent_name} cannot call {tool_name}")
