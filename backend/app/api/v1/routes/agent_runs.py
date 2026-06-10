# 作用：提供 Agent 执行轨迹查询接口，给前端 Trace 时间线使用。
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.trace_repo import TraceRepository

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.get("/{trace_id}")
async def get_agent_run(trace_id: str, db: AsyncSession = Depends(get_db)):
    """查询某次 Agent 工作流的完整执行轨迹。"""
    traces = await TraceRepository(db).list_by_trace_id(trace_id)
    return {
        "trace_id": trace_id,
        "steps": [
            {
                "agent_name": item.agent_name,
                "step_name": item.step_name,
                "status": item.status,
                "latency_ms": item.latency_ms,
                "input": item.input,
                "output": item.output,
                "error_message": item.error_message,
            }
            for item in traces
        ],
    }
