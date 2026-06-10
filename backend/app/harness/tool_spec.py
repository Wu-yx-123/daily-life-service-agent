# 作用：ToolSpec——统一定义每个工具的元数据。ToolRegistry 基于此做权限、超时、重试和审计。
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

RiskLevel = Literal["low", "medium", "high"]


@dataclass
class ToolSpec:
    """工具元数据规范。

    每个注册到 ToolRegistry 的工具必须有对应的 ToolSpec，
    声明其权限、Schema、超时、是否可重试、风险等级等。
    """

    name: str
    description: str = ""
    allowed_agents: list[str] = field(default_factory=list)
    # Agent 调用工具时允许传入的业务参数。依赖对象如 repo / db / lock_store 不应暴露给 Agent。
    allowed_args: list[str] = field(default_factory=list)

    # 输入/输出 Schema（用于校验和文档生成）
    input_schema: type[BaseModel] | None = None
    output_schema: type[BaseModel] | None = None

    # 执行约束
    timeout_seconds: float = 10.0
    retryable: bool = False
    max_retries: int = 1

    # 风险分级
    risk_level: RiskLevel = "low"
    mutating: bool = False  # 是否修改业务状态（写操作）


# ── 22 个工具的完整 ToolSpec 定义 ────────────────────────────────────

ALL_TOOL_SPECS: dict[str, ToolSpec] = {
    # ── 服务/技师查询（只读，低风险） ──
    "search_services": ToolSpec(
        name="search_services", description="匹配候选服务与技师",
        allowed_agents=["MatchAgent"], allowed_args=["intent"], risk_level="low",
        timeout_seconds=5.0,
    ),
    "get_service_detail": ToolSpec(
        name="get_service_detail", description="查询单个服务详情",
        allowed_agents=["MatchAgent"], allowed_args=["service_id"], risk_level="low",
        timeout_seconds=3.0,
    ),
    "search_technicians": ToolSpec(
        name="search_technicians", description="查询可接单技师",
        allowed_agents=["MatchAgent"], allowed_args=["store_id", "skill_tags"], risk_level="low",
        timeout_seconds=3.0,
    ),
    "search_stores": ToolSpec(
        name="search_stores", description="查询活跃门店",
        allowed_agents=["MatchAgent"], allowed_args=[], risk_level="low",
        timeout_seconds=3.0,
    ),
    "search_services_by_keyword": ToolSpec(
        name="search_services_by_keyword", description="关键词搜索服务项目",
        allowed_agents=["MatchAgent", "KnowledgeAgent"], allowed_args=["knowledge_repo", "query"],
        risk_level="low",
        timeout_seconds=5.0,
    ),

    # ── 排班/时间锁（写操作，中风险） ──
    "check_schedule": ToolSpec(
        name="check_schedule", description="校验时间可用性并创建时间锁",
        allowed_agents=["ScheduleAgent"],
        allowed_args=["candidate", "preferred_time", "user_id", "trace_id"],
        risk_level="medium", mutating=True,
        timeout_seconds=5.0,
    ),
    "create_time_lock": ToolSpec(
        name="create_time_lock", description="创建 Redis 临时时间锁",
        allowed_agents=["ScheduleAgent"],
        allowed_args=["store_id", "technician_id", "start_time", "user_id", "trace_id"],
        risk_level="medium", mutating=True,
        timeout_seconds=3.0,
    ),
    "release_time_lock": ToolSpec(
        name="release_time_lock", description="释放时间锁",
        allowed_agents=["ScheduleAgent"], allowed_args=["store_id", "technician_id", "start_time"],
        risk_level="medium", mutating=True,
        timeout_seconds=3.0,
    ),
    "check_order_conflicts": ToolSpec(
        name="check_order_conflicts", description="检查订单冲突",
        allowed_agents=["ScheduleAgent"],
        allowed_args=["technician_id", "room_id", "start", "end"],
        risk_level="low",
        timeout_seconds=5.0,
    ),

    # ── 价格/优惠券（只读，低风险） ──
    "calculate_price": ToolSpec(
        name="calculate_price", description="计算服务价格",
        allowed_agents=["PriceAgent"], allowed_args=["service_id", "user_id"], risk_level="low",
        timeout_seconds=3.0,
    ),
    "calculate_discounted_price": ToolSpec(
        name="calculate_discounted_price", description="计算叠加折扣后的价格",
        allowed_agents=["PriceAgent"], allowed_args=["service_id", "user_id", "coupon_id"], risk_level="low",
        timeout_seconds=5.0,
    ),
    "list_available_coupons": ToolSpec(
        name="list_available_coupons", description="查询用户可用优惠券",
        allowed_agents=["PriceAgent"], allowed_args=["user_id"], risk_level="low",
        timeout_seconds=3.0,
    ),

    # ── 风控（读写，高风险） ──
    "check_user_risk": ToolSpec(
        name="check_user_risk", description="查询用户历史风险指标",
        allowed_agents=["RiskAgent"], allowed_args=["user_id"], risk_level="medium",
        timeout_seconds=5.0,
    ),
    "create_risk_record": ToolSpec(
        name="create_risk_record", description="创建风控记录",
        allowed_agents=["RiskAgent"],
        allowed_args=["trace_id", "risk_level", "reasons", "user_id", "metadata"],
        risk_level="high", mutating=True,
        timeout_seconds=3.0,
    ),

    # ── 订单（写操作，高风险） ──
    "create_order": ToolSpec(
        name="create_order", description="创建正式订单",
        allowed_agents=["OrderAgent"], allowed_args=["draft", "user_id"],
        risk_level="high", mutating=True,
        timeout_seconds=5.0, retryable=False,
    ),
    "get_order": ToolSpec(
        name="get_order", description="查询订单详情",
        allowed_agents=["OrderAgent", "CustomerServiceAgent"], allowed_args=["order_id"],
        risk_level="low",
        timeout_seconds=3.0,
    ),
    "list_user_orders": ToolSpec(
        name="list_user_orders", description="查询用户历史订单",
        allowed_agents=["OrderAgent", "CustomerServiceAgent"], allowed_args=["user_id", "status"],
        risk_level="low",
        timeout_seconds=5.0,
    ),

    # ── 知识检索（只读，低风险） ──
    "search_knowledge": ToolSpec(
        name="search_knowledge", description="搜索知识库文档",
        allowed_agents=["KnowledgeAgent"],
        allowed_args=["knowledge_repo", "query", "category", "top_k"],
        risk_level="low",
        timeout_seconds=10.0,
    ),

    # ── 通知（写操作，低风险） ──
    "send_booking_confirmation": ToolSpec(
        name="send_booking_confirmation", description="发送预约确认通知",
        allowed_agents=["OrderAgent"],
        allowed_args=["user_id", "order_id", "appointment_start", "service_name", "technician_name"],
        risk_level="low", mutating=True,
        timeout_seconds=5.0, retryable=True, max_retries=2,
    ),
    "notify_admin": ToolSpec(
        name="notify_admin", description="通知管理员",
        allowed_agents=["CustomerServiceAgent"],
        allowed_args=["trace_id", "event", "detail"],
        risk_level="low", mutating=True,
        timeout_seconds=5.0, retryable=True, max_retries=2,
    ),
    "send_after_sales_notification": ToolSpec(
        name="send_after_sales_notification", description="发送售后进度通知",
        allowed_agents=["CustomerServiceAgent"],
        allowed_args=["user_id", "ticket_id", "ticket_type", "suggested_action"],
        risk_level="low", mutating=True,
        timeout_seconds=5.0, retryable=True, max_retries=2,
    ),
}
