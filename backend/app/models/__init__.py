# 作用：集中导出 ORM 模型，确保建表和迁移时能加载所有表定义。
from app.models.agent_trace import AgentTrace
from app.models.after_sales import AfterSalesTicket
from app.models.approval import ApprovalRequest
from app.models.business import Coupon, KnowledgeDocument, Review, Room, Service, Store, Technician, TechnicianSchedule, User
from app.models.harness import RiskRecord, RollbackLog, ToolCallLog
from app.models.memory import UserPreference
from app.models.order import Order
from app.models.ops import OpsReport
from app.models.semantic_memory import UserMemoryChunk

__all__ = [
    "AgentTrace",
    "AfterSalesTicket",
    "ApprovalRequest",
    "Coupon",
    "KnowledgeDocument",
    "Order",
    "Review",
    "RiskRecord",
    "Room",
    "RollbackLog",
    "Service",
    "Store",
    "Technician",
    "TechnicianSchedule",
    "ToolCallLog",
    "User",
    "UserMemoryChunk",
    "UserPreference",
    "OpsReport",
]
