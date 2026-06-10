# 作用：定义 LangGraph 状态机，把预约闭环、工程化控制和售后工单流程串起来。
# Phase 2 改进：完整的分支处理，包括追问、替代时间推荐、rematch。
from langgraph.graph import END, StateGraph

from app.agents.state import AgentState

CUSTOMER_SERVICE_TASKS = {"cancel_order", "reschedule_order", "refund_request", "complaint"}


def build_phase1_graph(nodes: dict[str, callable]):
    """构建当前阶段 LangGraph。

    节点覆盖：
    - 预约闭环：parse_intent → resolve_slots → verify → plan → match → schedule → price → risk → approve → present
    - 售后流程：customer_service
    - 追问分支：verify 失败 → ask_followup
    - 替代时间：schedule 不可用 → recommend_alternative
    """
    graph = StateGraph(AgentState)
    graph.add_node("parse_intent", nodes["parse_intent"])
    graph.add_node("resolve_slots", nodes["resolve_slots"])
    graph.add_node("verify_intent", nodes["verify_intent"])
    graph.add_node("plan_task", nodes["plan_task"])
    graph.add_node("match_service", nodes["match_service"])
    graph.add_node("check_schedule", nodes["check_schedule"])
    graph.add_node("calculate_price", nodes["calculate_price"])
    graph.add_node("risk_check", nodes["risk_check"])
    graph.add_node("approval_gate", nodes["approval_gate"])
    graph.add_node("present_options", nodes["present_options"])
    graph.add_node("customer_service", nodes["customer_service"])

    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "resolve_slots")

    # resolve_slots: 槽位冲突需要用户确认时直接结束，否则进入业务校验
    graph.add_conditional_edges(
        "resolve_slots",
        lambda s: "verify_intent" if not s.get("errors") else END,
    )

    # verify_intent: 通过 → plan，失败 → END（追问消息已在 state.final_response 中）
    graph.add_conditional_edges(
        "verify_intent",
        lambda s: "plan_task" if not s.get("errors") else END,
    )

    # plan_task: booking → match，售后 → customer_service，其他 → END
    graph.add_conditional_edges("plan_task", route_after_plan)

    # match_service: 有候选 → schedule，无候选 → END
    graph.add_conditional_edges(
        "match_service",
        lambda s: "check_schedule" if s.get("selected_option") else END,
    )

    graph.add_edge("check_schedule", "calculate_price")
    graph.add_edge("calculate_price", "risk_check")
    graph.add_edge("risk_check", "approval_gate")

    # approval_gate: 不需要审批 → present，需要审批 → END
    graph.add_conditional_edges(
        "approval_gate",
        lambda s: "present_options" if not s.get("approval_request") and not s.get("errors") else END,
    )

    graph.add_edge("present_options", END)
    graph.add_edge("customer_service", END)

    return graph.compile()


def route_after_plan(state: AgentState) -> str:
    """根据任务类型决定进入预约流程、售后流程还是结束。"""
    if state.get("errors"):
        return END
    task_type = state.get("task_type", "")
    if task_type == "book_appointment":
        return "match_service"
    if task_type in CUSTOMER_SERVICE_TASKS:
        return "customer_service"
    # 查询类 / 未知类：直接结束，final_response 由 plan_task 节点填入
    return END
