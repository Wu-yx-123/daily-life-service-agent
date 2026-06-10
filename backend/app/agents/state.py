# 作用：定义 LangGraph 节点之间传递的共享 AgentState。
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """LangGraph 在各节点之间传递的共享状态。

    这里尽量保存可序列化数据，方便写 Trace 和给前端查看。
    """

    trace_id: str
    session_id: str
    user_id: str
    user_message: str
    conversation_history: list[dict[str, str]]  # 多轮对话：最近 N 条消息
    long_term_memory: dict[str, Any]  # 长期偏好画像：服务、力度、预算、常用时段等
    semantic_memories: list[dict[str, Any]]  # pgvector 召回的用户私有语义记忆
    task_type: str
    intent: dict[str, Any]
    previous_intent: dict[str, Any]
    slot_resolution: dict[str, Any]
    plan: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    selected_option: dict[str, Any] | None
    schedule_check: dict[str, Any]
    price_result: dict[str, Any]
    verification: dict[str, Any]
    risk_result: dict[str, Any]
    approval_request: dict[str, Any] | None
    customer_service_result: dict[str, Any]
    after_sales_ticket: dict[str, Any]
    order_draft: dict[str, Any]
    order_id: str | None
    final_response: str
    errors: list[dict[str, Any]]
