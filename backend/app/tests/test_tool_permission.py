# 作用：测试 ToolRegistry 和 PermissionManager 能阻止 Agent 越权调用工具。
import pytest

from app.harness.tool_registry import ToolRegistry


async def test_agent_cannot_call_unauthorized_tool():
    """工具注册表必须拒绝 Agent 越权调用。"""
    registry = ToolRegistry()

    async def fake_tool():
        return {"ok": True}

    registry.register("create_order", fake_tool)

    with pytest.raises(PermissionError):
        await registry.call("IntentAgent", "create_order", {})
