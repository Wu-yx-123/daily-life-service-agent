# 作用：实现 Agent 工具权限沙箱和任务级隔离沙箱，给 Harness 提供统一安全边界。
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from app.harness.tool_spec import ALL_TOOL_SPECS


class SandboxViolation(PermissionError):
    """沙箱违规基础异常。

    使用 PermissionError 子类，方便 API 层或 TraceLogger 统一识别为权限/隔离问题。
    """


class ToolSandboxViolation(SandboxViolation):
    """Agent 工具权限沙箱违规。"""


class TaskSandboxViolation(SandboxViolation):
    """任务级隔离沙箱违规。"""


@dataclass(frozen=True)
class ToolPolicy:
    """单个工具的沙箱策略。

    allowed_args 用来限制工具入参形状，避免 Agent 偷塞业务外字段；
    mutates 标记工具是否可能改变状态，后续可用于更严格的审批/回滚。
    """

    allowed_agents: set[str]
    allowed_args: set[str]
    mutates: bool = False


@dataclass(frozen=True)
class TaskContext:
    """一次 Agent 任务的隔离上下文。

    trace_id 是本次运行的唯一边界；session_id 和 user_id 用来防止跨会话/跨用户混用状态。
    """

    trace_id: str
    session_id: str
    user_id: str


# contextvars 能跟随 async 调用链传播，比把 trace_id 手动塞进每个函数更稳。
_current_task_context: ContextVar[TaskContext | None] = ContextVar("current_task_context", default=None)


class AgentToolSandbox:
    """Agent 工具权限沙箱。

    它不仅检查“哪个 Agent 能调用哪个工具”，还检查工具入参是否在允许范围内。
    """

    def __init__(self, policies: dict[str, ToolPolicy] | None = None):
        self.policies = policies or build_default_tool_policies()

    def authorize(self, *, agent_name: str, tool_name: str, args: dict[str, Any]) -> None:
        """在工具执行前做沙箱授权检查。"""
        policy = self.policies.get(tool_name)
        if not policy:
            raise ToolSandboxViolation(f"tool is not registered in sandbox policy: {tool_name}")
        if agent_name not in policy.allowed_agents:
            raise ToolSandboxViolation(f"{agent_name} cannot call {tool_name}")
        extra_args = set(args) - policy.allowed_args
        if extra_args:
            raise ToolSandboxViolation(f"{tool_name} received forbidden args: {sorted(extra_args)}")
        if policy.mutates and _current_task_context.get() is None:
            raise TaskSandboxViolation(f"mutating tool {tool_name} must run inside a task sandbox")


class TaskIsolationSandbox:
    """任务级隔离沙箱。

    每次 Orchestrator.run 都创建独立上下文，防止不同用户、会话、trace 的状态串线。
    """

    @asynccontextmanager
    async def context(self, *, trace_id: str, session_id: str, user_id: str):
        """开启一个异步任务隔离上下文。"""
        token = _current_task_context.set(TaskContext(trace_id=trace_id, session_id=session_id, user_id=user_id))
        try:
            yield _current_task_context.get()
        finally:
            # 退出任务时必须恢复上下文，避免下一个请求继承上一次 trace。
            _current_task_context.reset(token)

    def current(self) -> TaskContext:
        """读取当前任务上下文；没有上下文时说明代码越过了 Orchestrator。"""
        context = _current_task_context.get()
        if context is None:
            raise TaskSandboxViolation("no active task sandbox")
        return context

    def ensure_state_belongs_to_current_task(self, state: dict[str, Any]) -> None:
        """校验 LangGraph state 没有跨 trace/session/user 污染。"""
        context = self.current()
        expected = {
            "trace_id": context.trace_id,
            "session_id": context.session_id,
            "user_id": context.user_id,
        }
        for key, value in expected.items():
            if state.get(key) != value:
                raise TaskSandboxViolation(f"state {key} does not match current task sandbox")

    @staticmethod
    def agent_run_key(trace_id: str) -> str:
        """生成隔离后的 Agent 运行态缓存 Key。"""
        return f"agent_run:{trace_id}"


def build_default_tool_policies() -> dict[str, ToolPolicy]:
    """根据 ToolSpec 生成默认工具策略，避免权限表和沙箱策略各维护一份。"""
    return {
        name: ToolPolicy(
            allowed_agents=set(spec.allowed_agents),
            allowed_args=set(spec.allowed_args),
            mutates=spec.mutating,
        )
        for name, spec in ALL_TOOL_SPECS.items()
    }
