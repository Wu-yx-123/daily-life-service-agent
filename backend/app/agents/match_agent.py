# 作用：MatchAgent 负责通过工具注册表召回候选服务和技师。
from app.harness.tool_registry import ToolRegistry
from app.schemas.agent import IntentOutput, MatchOutput


class MatchAgent:
    """匹配 Agent：通过工具注册表调用服务匹配工具。"""

    name = "MatchAgent"

    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    async def run(self, intent: IntentOutput) -> MatchOutput:
        """根据 IntentAgent 输出召回候选预约方案。"""
        return await self.tools.call(self.name, "search_services", {"intent": intent})
