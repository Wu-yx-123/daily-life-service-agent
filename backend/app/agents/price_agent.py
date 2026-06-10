# 作用：PriceAgent 负责调用计价工具并返回结构化价格结果。
from app.harness.tool_registry import ToolRegistry
from app.schemas.agent import PriceOutput


class PriceAgent:
    """计价 Agent：通过工具调用确定性价格服务。"""

    name = "PriceAgent"

    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    async def run(self, *, service_id: str, user_id: str) -> PriceOutput:
        """计算服务价格并生成价格快照。"""
        return await self.tools.call(self.name, "calculate_price", {"service_id": service_id, "user_id": user_id})
