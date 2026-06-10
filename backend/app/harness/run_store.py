# 作用：保存 Agent 工作流状态，供用户确认预约时读取订单草稿。
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def json_default(value: Any) -> str:
    """把日期和 Decimal 转成可 JSON 序列化的字符串。"""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


class AgentRunStore:
    """Phase 1 的运行态缓存。

    保存 trace_id 对应的订单草稿，供用户点击确认时读取。
    后续可以替换成 Redis 的 agent_run:{trace_id}。
    """

    def __init__(self):
        self._runs: dict[str, dict[str, Any]] = {}

    def save(self, trace_id: str, state: dict[str, Any]) -> None:
        """保存一次 Agent 工作流最终状态。"""
        self._runs[trace_id] = json.loads(json.dumps(state, default=json_default))

    def get(self, trace_id: str) -> dict[str, Any] | None:
        """读取 trace_id 对应的 Agent 状态。"""
        return self._runs.get(trace_id)


agent_run_store = AgentRunStore()
