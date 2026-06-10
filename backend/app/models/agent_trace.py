# 作用：定义 Agent TraceLog ORM 模型，用于持久化执行轨迹。
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID


class AgentTrace(Base):
    """Agent 执行轨迹表。

    每个节点都会记录输入、输出、状态和耗时，前端 Trace 页面直接读取这里。
    """

    __tablename__ = "agent_traces"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128))
    order_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    agent_name: Mapped[str | None] = mapped_column(String(128))
    step_name: Mapped[str | None] = mapped_column(String(128))
    input: Mapped[dict | None] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON)
    tool_name: Mapped[str | None] = mapped_column(String(128))
    tool_args: Mapped[dict | None] = mapped_column(JSON)
    tool_result: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str | None] = mapped_column(String(32))
    latency_ms: Mapped[int | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
