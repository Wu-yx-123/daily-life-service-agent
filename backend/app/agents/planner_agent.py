# 作用：PlannerAgent 根据任务类型生成预约或售后流程计划。
CUSTOMER_SERVICE_TASKS = {"cancel_order", "reschedule_order", "refund_request", "complaint"}


class PlannerAgent:
    """流程规划 Agent。

    Phase 1 规划预约闭环，Phase 3 增加售后工单流程。
    """

    name = "PlannerAgent"

    async def run(self, task_type: str) -> list[dict[str, str]]:
        """根据任务类型返回后续 Agent 节点计划。"""
        if task_type in CUSTOMER_SERVICE_TASKS:
            return [{"step": "customer_service", "agent": "CustomerServiceAgent"}]
        if task_type != "book_appointment":
            return []
        return [
            {"step": "match_service", "agent": "MatchAgent"},
            {"step": "check_schedule", "agent": "ScheduleAgent"},
            {"step": "calculate_price", "agent": "PriceAgent"},
            {"step": "present_options", "agent": "OrderAgent"},
        ]
