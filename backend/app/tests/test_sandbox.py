# 作用：测试 Agent 工具权限沙箱和任务级隔离沙箱的关键安全边界。
import pytest

from app.harness.sandbox import AgentToolSandbox, TaskIsolationSandbox, TaskSandboxViolation, ToolSandboxViolation
from app.harness.tool_spec import ALL_TOOL_SPECS
from app.harness.tool_registry import ToolRegistry


async def test_tool_sandbox_rejects_forbidden_args():
    """工具参数不在白名单内时，沙箱必须拒绝执行。"""
    registry = ToolRegistry(sandbox=AgentToolSandbox())

    async def fake_price_tool(service_id: str, user_id: str):
        return {"service_id": service_id, "user_id": user_id}

    registry.register("calculate_price", fake_price_tool)

    with pytest.raises(ToolSandboxViolation):
        await registry.call(
            "PriceAgent",
            "calculate_price",
            {"service_id": "service_001", "user_id": "user_001", "final_price": "1"},
        )


async def test_mutating_tool_requires_task_sandbox():
    """会改变状态的工具必须运行在任务级沙箱上下文中。"""
    registry = ToolRegistry(sandbox=AgentToolSandbox())

    async def fake_schedule_tool(candidate, preferred_time, user_id, trace_id):
        return {"available": True}

    registry.register("check_schedule", fake_schedule_tool)

    with pytest.raises(TaskSandboxViolation):
        await registry.call(
            "ScheduleAgent",
            "check_schedule",
            {"candidate": {}, "preferred_time": "2026-05-29T20:00:00", "user_id": "user_001", "trace_id": "trace_001"},
        )


async def test_mutating_tool_can_run_inside_task_sandbox():
    """进入任务沙箱后，合法 Agent 可以调用合法的变更型工具。"""
    registry = ToolRegistry(sandbox=AgentToolSandbox())
    task_sandbox = TaskIsolationSandbox()

    async def fake_schedule_tool(candidate, preferred_time, user_id, trace_id):
        return {"available": True, "trace_id": trace_id}

    registry.register("check_schedule", fake_schedule_tool)

    async with task_sandbox.context(trace_id="trace_001", session_id="session_001", user_id="user_001"):
        result = await registry.call(
            "ScheduleAgent",
            "check_schedule",
            {"candidate": {}, "preferred_time": "2026-05-29T20:00:00", "user_id": "user_001", "trace_id": "trace_001"},
        )

    assert result["available"] is True


async def test_task_sandbox_rejects_cross_trace_state():
    """LangGraph state 的 trace/session/user 与当前上下文不一致时必须被拦截。"""
    task_sandbox = TaskIsolationSandbox()

    async with task_sandbox.context(trace_id="trace_a", session_id="session_a", user_id="user_a"):
        with pytest.raises(TaskSandboxViolation):
            task_sandbox.ensure_state_belongs_to_current_task(
                {"trace_id": "trace_b", "session_id": "session_a", "user_id": "user_a"}
            )


async def test_sandbox_policy_covers_all_tool_specs():
    """每个 ToolSpec 都必须生成沙箱策略，避免新增工具绕过参数白名单。"""
    sandbox = AgentToolSandbox()

    assert set(ALL_TOOL_SPECS) == set(sandbox.policies)
    for name, spec in ALL_TOOL_SPECS.items():
        policy = sandbox.policies[name]
        assert policy.allowed_agents == set(spec.allowed_agents)
        assert policy.allowed_args == set(spec.allowed_args)
        assert policy.mutates is spec.mutating


async def test_high_risk_create_order_requires_task_sandbox():
    """高风险写工具即使 Agent 权限正确，也不能脱离任务沙箱执行。"""
    registry = ToolRegistry(sandbox=AgentToolSandbox())

    async def fake_create_order(draft, user_id):
        return {"order_id": "order_001", "user_id": user_id}

    registry.register("create_order", fake_create_order)

    with pytest.raises(TaskSandboxViolation):
        await registry.call(
            "OrderAgent",
            "create_order",
            {"draft": {"user_confirmed": True}, "user_id": "user_001"},
        )
