# 作用：记录每个 Agent 节点的输入、输出、状态、耗时和异常。
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.trace_repo import TraceRepository


class TraceLogger:
    """TraceLog 写入器。

    Orchestrator 使用 traced 包裹每个 Agent 节点，确保成功和失败都会落库。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TraceRepository(db)

    async def log_step(
        self,
        *,
        trace_id: str,
        session_id: str | None,
        agent_name: str,
        step_name: str,
        input: dict[str, Any] | None,
        output: dict[str, Any] | None,
        status: str = "success",
        latency_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """写入单个 Agent 步骤的执行记录。"""
        await self.repo.add(
            trace_id=trace_id,
            session_id=session_id,
            agent_name=agent_name,
            step_name=step_name,
            input=input,
            output=output,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        await self.db.commit()

    async def traced(self, *, trace_id: str, session_id: str | None, agent_name: str, step_name: str, input: dict[str, Any], fn: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        """执行节点函数并自动记录输入、输出、耗时和异常。"""
        started = time.perf_counter()
        try:
            output = await fn()
            # 成功时记录完整输出，前端 Trace 页面可以直接展示 Agent 每一步结果。
            await self.log_step(
                trace_id=trace_id,
                session_id=session_id,
                agent_name=agent_name,
                step_name=step_name,
                input=input,
                output=output,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            return output
        except Exception as exc:
            # 失败也必须落 Trace，否则排查 Agent 工作流时会断链。
            await self.log_step(
                trace_id=trace_id,
                session_id=session_id,
                agent_name=agent_name,
                step_name=step_name,
                input=input,
                output=None,
                status="failed",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_message=str(exc),
            )
            raise
