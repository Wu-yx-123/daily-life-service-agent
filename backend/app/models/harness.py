# 作用：定义 Harness 工程化相关记录表，包括风控、工具调用和回滚日志。
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID


class RiskRecord(Base):
    """风控记录表。

    RiskAgent 的风险结论可以沉淀到这里，便于后续审计和模型优化。
    """

    __tablename__ = "risk_records"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[dict | None] = mapped_column(JSON)
    action: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ToolCallLog(Base):
    """工具调用审计日志——细粒度记录每次调用的元数据、权限、超时与重试。"""

    __tablename__ = "tool_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128))
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_args: Mapped[dict | None] = mapped_column(JSON)
    tool_result: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="success")  # success | denied | timeout | error | retry
    risk_level: Mapped[str | None] = mapped_column(String(16))           # low | medium | high
    error_message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None]
    retry_count: Mapped[int | None] = mapped_column(default=0)           # 重试次数
    permission_denied: Mapped[bool | None] = mapped_column(default=False) # 是否因权限被拒绝
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RollbackLog(Base):
    """回滚日志表。"""

    __tablename__ = "rollback_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str | None] = mapped_column(String(128), index=True)
    rollback_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_ref: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="success")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
