# 作用：定义人工审批 ORM 模型，用于承接 Phase 2 高风险 Agent 请求。
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID


class ApprovalRequest(Base):
    """人工审批单表。

    高风险 Agent 流程不会直接进入业务提交，而是把上下文快照写到这里等待管理员处理。
    """

    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    resume_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 审批通过后恢复执行的完整 AgentState
    resume_step: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 恢复执行的起始节点
    order_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
