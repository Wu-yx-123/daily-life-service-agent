# 作用：封装 Agent TraceLog 的数据库写入和查询。
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trace import AgentTrace


class TraceRepository:
    """Agent Trace 仓储，负责写入和按 trace_id 查询执行轨迹。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, **data) -> AgentTrace:
        trace = AgentTrace(**data)
        self.db.add(trace)
        await self.db.flush()
        return trace

    async def list_by_trace_id(self, trace_id: str) -> list[AgentTrace]:
        stmt = select(AgentTrace).where(AgentTrace.trace_id == trace_id).order_by(AgentTrace.created_at, AgentTrace.id)
        return list((await self.db.scalars(stmt)).all())
