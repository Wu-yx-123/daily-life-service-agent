# 作用：定义 Agent 合同和 Phase 1 API 请求/响应的 Pydantic Schema。
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


# IntentAgent 支持识别的任务类型；Phase 1 只完整执行 book_appointment。
TaskType = Literal[
    "book_appointment",
    "reschedule_order",
    "cancel_order",
    "refund_request",
    "complaint",
    "service_query",
    "store_query",
    "ops_analysis",
    "unknown",
]


# ══════════════════════════════════════════════════════════════════
# Agent 通用错误与 Trace
# ══════════════════════════════════════════════════════════════════


class AgentError(BaseModel):
    """Agent 执行失败时的结构化错误信息。"""
    agent: str
    code: str  # schema_validation | llm_failure | tool_error | timeout
    message: str
    retries_attempted: int = 0
    fallback_used: bool = False


# ══════════════════════════════════════════════════════════════════
# IntentAgent
# ══════════════════════════════════════════════════════════════════

class IntentAgentInput(BaseModel):
    """IntentAgent 输入合同。"""
    message: str
    history: list[dict[str, str]] | None = None


class IntentSlots(BaseModel):
    """预约语义槽位 - LLM 从这里提取用户需求中的结构化字段。"""

    service_type: str | None = Field(
        default=None,
        description="用户想要的服务类型，如'肩颈按摩'、'全身放松'、'精油SPA'、'泰式按摩'、'头部理疗'、'足部养护'。从用户描述中推断，不要生造。",
    )
    duration_minutes: int | None = Field(
        default=None,
        description="期望的服务时长（分钟），如60、90、120。从用户原文中提取确切数字或从'半小时'→30、'一个半小时'→90推断。",
    )
    preferred_time: datetime | None = Field(
        default=None,
        description="用户期望的预约开始时间。将'今晚8点'→今天20:00、'明天下午3点'→明天15:00、'下周三上午10点'→下周三10:00。当前日期时间会从上下文中提供。",
    )
    budget_max: Decimal | None = Field(
        default=None,
        description="用户预算上限（元）。从'预算300以内'→300、'不超过500'→500、'200左右'→200提取。",
    )
    strength_preference: str | None = Field(
        default=None,
        description="手法力度偏好：'heavy'（力度偏重/受力）、'medium'（适中）、'light'（轻柔/放松）。从'重一点'→heavy、'轻一点'→light、'放松一下'→light 推断。",
    )
    store_preference: str | None = Field(
        default=None,
        description="用户偏好的门店名称或位置，如'Tokyo店'、'离家近的门店'。没有则为null。",
    )
    technician_preference: str | None = Field(
        default=None,
        description="用户偏好或指定的技师名字，如'小李'、'上次那个技师'。没有则为null。",
    )


class IntentOutput(BaseModel):
    """IntentAgent 的输出合同 - 由 LLM 或规则解析器填充。"""

    task_type: TaskType = Field(
        description="任务类型分类。book_appointment=预约服务，reschedule_order=改期，cancel_order=取消，refund_request=退款，complaint=投诉，service_query=咨询服务，store_query=咨询门店，ops_analysis=运营分析，unknown=无法识别",
    )
    slots: IntentSlots = Field(
        description="从用户消息中提取的结构化槽位。预约类任务至少需要 service_type 和 preferred_time。",
    )
    missing_slots: list[str] = Field(
        description="预约必需的缺失槽位列表。选项：service_type / preferred_time / duration_minutes。如果信息足够完成预约，则为空列表。",
    )
    confidence: float = Field(
        ge=0, le=1,
        description="意图识别的置信度（0-1）。槽位提取不完整时适当降低，如0.65；完全明确为0.9以上。",
    )


# ══════════════════════════════════════════════════════════════════
# PlannerAgent
# ══════════════════════════════════════════════════════════════════

class PlannerAgentInput(BaseModel):
    """PlannerAgent 输入合同。"""
    task_type: str


class PlannerAgentOutput(BaseModel):
    """PlannerAgent 输出合同：执行步骤计划。"""
    plan: list[dict[str, str]]


# ══════════════════════════════════════════════════════════════════
# MatchAgent
# ══════════════════════════════════════════════════════════════════

class MatchAgentInput(BaseModel):
    """MatchAgent 输入合同。"""
    intent: "IntentOutput"


class CandidateOption(BaseModel):
    """MatchAgent 输出的候选预约方案。"""

    option_id: str
    store_id: str
    service_id: str
    technician_id: str
    service_name: str
    technician_name: str
    base_price: Decimal
    duration_minutes: int
    match_score: float
    reason: str


class MatchOutput(BaseModel):
    """MatchAgent 输出合同：候选项按匹配分从高到低排列。"""

    candidates: list[CandidateOption]


# ══════════════════════════════════════════════════════════════════
# ScheduleAgent
# ══════════════════════════════════════════════════════════════════

class ScheduleAgentInput(BaseModel):
    """ScheduleAgent 输入合同。"""
    candidate: "CandidateOption"
    intent: "IntentOutput"
    user_id: str
    trace_id: str


class ScheduleOutput(BaseModel):
    """ScheduleAgent 输出合同：包含可用性、房间和 Redis 时间锁。"""

    available: bool
    room_id: str | None = None
    lock_id: str | None = None
    appointment_start: datetime | None = None
    appointment_end: datetime | None = None
    cleanup_end: datetime | None = None
    reason: str | None = None


# ══════════════════════════════════════════════════════════════════
# PriceAgent
# ══════════════════════════════════════════════════════════════════

class PriceAgentInput(BaseModel):
    """PriceAgent 输入合同。"""
    service_id: str
    user_id: str


class PriceOutput(BaseModel):
    """PriceAgent 输出合同。"""

    original_price: Decimal
    member_discount: Decimal = Decimal("0")
    coupon_discount: Decimal = Decimal("0")
    promotion_discount: Decimal = Decimal("0")
    final_price: Decimal
    price_snapshot: dict[str, Any]


class VerificationOutput(BaseModel):
    """VerificationGate 输出合同：决定当前状态是否允许继续执行。"""

    passed: bool
    errors: list[dict[str, Any]] = []


# ══════════════════════════════════════════════════════════════════
# RiskAgent
# ══════════════════════════════════════════════════════════════════

class RiskAgentInput(BaseModel):
    """RiskAgent 输入合同。"""
    user_message: str
    intent: "IntentOutput"
    price: "PriceOutput"
    knowledge_context: str | None = None
    user_history: dict[str, Any] | None = None


class RiskOutput(BaseModel):
    """RiskAgent 输出合同：基于 6 维业务历史规则的综合风险评估。"""

    risk_level: Literal["low", "medium", "high"]
    risk_score: float = Field(ge=0, le=1, description="综合风险评分 0-1")
    reasons: list[str] = []
    requires_approval: bool = False


# ══════════════════════════════════════════════════════════════════
# CustomerServiceAgent
# ══════════════════════════════════════════════════════════════════

class CustomerServiceAgentInput(BaseModel):
    """CustomerServiceAgent 输入合同。"""
    message: str
    intent: "IntentOutput"
    knowledge_context: str | None = None


class CustomerServiceOutput(BaseModel):
    """CustomerServiceAgent 输出合同：给出售后类型、优先级和处理建议。"""

    ticket_type: Literal["cancel_order", "reschedule_order", "refund_request", "complaint"]
    priority: Literal["normal", "high", "urgent"]
    summary: str
    suggested_action: str


# ══════════════════════════════════════════════════════════════════
# ReviewAgent
# ══════════════════════════════════════════════════════════════════

class ReviewAgentInput(BaseModel):
    """ReviewAgent 输入合同。"""
    rating: int = Field(ge=1, le=5)
    content: str | None = None


class ReviewAnalysisOutput(BaseModel):
    """ReviewAgent 输出合同：分析评价情绪和差评原因。"""

    sentiment: Literal["positive", "neutral", "negative"]
    reason_tags: list[str] = []
    summary: str


class EvidenceChunk(BaseModel):
    """RAG 检索返回的可追溯证据片段。"""

    source_file: str = Field(description="来源文件名，如 03_after_sales_refund_policy.pdf")
    doc_type: str = Field(description="文档类型：refund_policy / complaint_policy / store_rule 等")
    chunk_id: str = Field(description="chunk 唯一标识")
    score: float = Field(ge=0, le=1, description="相关度 0-1")
    text: str = Field(description="证据片段文本")


class KnowledgeAnswer(BaseModel):
    """KnowledgeAgent 输出合同：回答 + 可追溯证据链。"""

    query: str
    answer: str
    evidence: list[EvidenceChunk] = []
    hits: list[dict] = []  # 兼容旧接口
    source: str = "mcp_rag"  # mcp_rag | sql | fallback


# ══════════════════════════════════════════════════════════════════
# KnowledgeAgent
# ══════════════════════════════════════════════════════════════════

class KnowledgeAgentInput(BaseModel):
    """KnowledgeAgent 输入合同。"""
    query: str
    category: str | None = None


class KnowledgeQueryRequest(BaseModel):
    """知识库查询请求。"""

    query: str
    category: str | None = None


class ApprovalRequestSnapshot(BaseModel):
    """人工审批单快照，保存 Agent 给出的高风险上下文。"""

    user_message: str
    intent: dict[str, Any] | None = None
    selected_option: dict[str, Any] | None = None
    schedule_check: dict[str, Any] | None = None
    price_result: dict[str, Any] | None = None
    risk_result: dict[str, Any] | None = None


# ══════════════════════════════════════════════════════════════════
# OrderAgent
# ══════════════════════════════════════════════════════════════════

class OrderAgentInput(BaseModel):
    """OrderAgent 输入合同。"""
    candidate: "CandidateOption"
    schedule: "ScheduleOutput"
    price: "PriceOutput"
    user_id: str


class OrderDraft(BaseModel):
    """待确认订单草稿。

    只有包含时间锁和价格快照的草稿，才允许进入确认创建订单流程。
    VerificationGate 会逐字段校验草稿完整性，Agent 不能绕过。
    """

    user_id: str
    option_id: str
    store_id: str
    service_id: str
    technician_id: str
    room_id: str
    appointment_start: datetime
    appointment_end: datetime
    original_price: Decimal
    final_price: Decimal
    lock_id: str
    price_snapshot: dict[str, Any]
    user_confirmed: bool = False


class ConversationRequest(BaseModel):
    """用户聊天预约接口请求。"""

    session_id: str
    user_id: str
    message: str


class BookingOptionResponse(BaseModel):
    """返回给前端展示的预约候选卡片。"""

    option_id: str
    service_name: str
    technician_name: str
    appointment_start: datetime
    appointment_end: datetime
    final_price: Decimal
    reason: str


class ConversationResponse(BaseModel):
    """聊天接口响应：可能是候选方案，也可能是追问缺失槽位。"""

    trace_id: str
    session_id: str
    response_type: str
    message: str
    options: list[BookingOptionResponse] = []


class AfterSalesTicketResponse(BaseModel):
    """售后工单响应，供聊天入口和售后页面展示。"""

    id: str
    trace_id: str
    session_id: str | None = None
    user_id: str
    ticket_type: str
    status: str
    priority: str
    summary: str
    suggested_action: str
    created_at: datetime
    updated_at: datetime | None = None


class ReviewAnalyzeRequest(BaseModel):
    """评价分析请求。"""

    user_id: str
    order_id: str | None = None
    rating: int = Field(ge=1, le=5)
    content: str | None = None


class ReviewAnalyzeResponse(BaseModel):
    """评价分析响应。"""

    id: str
    sentiment: str
    reason_tags: list[str]
    summary: str


# ══════════════════════════════════════════════════════════════════
# OpsAgent
# ══════════════════════════════════════════════════════════════════

class OpsAgentInput(BaseModel):
    """OpsAgent 输入合同。"""
    order_count: int
    revenue_total: Decimal
    after_sales_open_count: int
    pending_approval_count: int
    review_count: int
    average_rating: float | None = None
    negative_review_count: int


class OpsReportResponse(BaseModel):
    """运营报表响应，展示经营和服务风险摘要。"""

    order_count: int
    revenue_total: Decimal
    after_sales_open_count: int
    pending_approval_count: int
    review_count: int
    average_rating: float | None = None
    negative_review_count: int
    suggestions: list[str]


class OrderConfirmRequest(BaseModel):
    """用户确认预约请求。"""

    trace_id: str
    option_id: str
    user_confirmed: bool


class OrderConfirmResponse(BaseModel):
    """用户确认预约响应。"""

    order_id: str | None = None
    status: str
    message: str


class ApprovalListItem(BaseModel):
    """审批列表项，供平台运营端查看待处理高风险 Agent 请求。"""

    id: str
    trace_id: str
    session_id: str | None = None
    user_id: str
    approval_type: str
    status: str
    risk_level: str
    reason: str
    snapshot: dict[str, Any]
    order_id: str | None = None
    reviewer_note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class ApprovalDecisionRequest(BaseModel):
    """审批决策请求：管理员可以批准、驳回或要求修改。"""

    decision: Literal["approved", "rejected", "needs_change"]
    reviewer_note: str | None = None


class ApprovalDecisionResponse(BaseModel):
    """审批决策响应。"""

    id: str
    status: str
    message: str
    order_id: str | None = None
