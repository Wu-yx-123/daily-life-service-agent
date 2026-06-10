# 作用：ScheduleAgent 负责调用排班工具，检查可用性并创建时间锁。
from app.harness.tool_registry import ToolRegistry
from app.schemas.agent import CandidateOption, IntentOutput, ScheduleOutput


class ScheduleAgent:
    """排班 Agent：检查时间可用性并创建临时时间锁。"""

    name = "ScheduleAgent"

    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    async def run(self, *, candidate: CandidateOption, intent: IntentOutput, user_id: str, trace_id: str) -> ScheduleOutput:
        """为候选方案校验目标时间，成功则返回房间和锁 ID。"""
        if not intent.slots.preferred_time:
            return ScheduleOutput(available=False, reason="缺少预约时间")
        return await self.tools.call(
            self.name,
            "check_schedule",
            {"candidate": candidate, "preferred_time": intent.slots.preferred_time, "user_id": user_id, "trace_id": trace_id},
        )
