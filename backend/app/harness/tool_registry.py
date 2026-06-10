# 作用：增强 ToolRegistry——基于 ToolSpec 做权限校验、超时控制、重试和审计日志。
import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.harness.permission import PermissionManager
from app.harness.sandbox import AgentToolSandbox
from app.harness.tool_spec import ALL_TOOL_SPECS, ToolSpec

logger = logging.getLogger(__name__)

ToolCallable = Callable[..., Awaitable[Any]]


class ToolRegistry:
    """增强工具注册表。

    每次工具调用经过 5 层控制：
    1. ToolSpec 元数据校验
    2. PermissionManager 白名单检查
    3. AgentToolSandbox 参数沙箱
    4. 超时保护（asyncio.wait_for）
    5. 审计日志（tool_call_logs）
    """

    def __init__(
        self,
        permission: PermissionManager | None = None,
        sandbox: AgentToolSandbox | None = None,
    ):
        self.permission = permission or PermissionManager()
        self.sandbox = sandbox or AgentToolSandbox()
        self.tools: dict[str, ToolCallable] = {}
        self._specs: dict[str, ToolSpec] = {}

    def register(self, name: str, tool: ToolCallable, spec: ToolSpec | None = None) -> None:
        """注册工具函数及其 ToolSpec 元数据。"""
        self.tools[name] = tool
        self._specs[name] = spec or ALL_TOOL_SPECS.get(name, ToolSpec(name=name))

    async def call(
        self,
        agent_name: str,
        tool_name: str,
        args: dict[str, Any],
        *,
        trace_id: str = "",
        session_id: str = "",
    ) -> Any:
        """按 Agent 身份调用工具，含完整的治理链路。

        Returns:
            工具执行结果

        Raises:
            PermissionError: 权限拒绝
            TimeoutError: 超时
            Exception: 执行异常
        """
        spec = self._specs.get(tool_name, ToolSpec(name=tool_name))
        t0 = time.monotonic()

        # ── 1. ToolSpec 权限检查 ──
        if spec.allowed_agents and agent_name not in spec.allowed_agents:
            denied = True
            self._audit_denial(trace_id, session_id, agent_name, tool_name, spec, "ToolSpec 不允许此 Agent 调用")
            raise PermissionError(f"ToolSpec: {agent_name} not allowed to call {tool_name}")

        # ── 2. PermissionManager 白名单 ──
        try:
            self.permission.check(agent_name, tool_name)
        except PermissionError as exc:
            self._audit_denial(trace_id, session_id, agent_name, tool_name, spec, str(exc))
            raise

        # ── 3. 沙箱校验 ──
        self.sandbox.authorize(agent_name=agent_name, tool_name=tool_name, args=args)

        if tool_name not in self.tools:
            raise KeyError(f"tool not registered: {tool_name}")

        # ── 4. 执行（含超时 + 重试） ──
        last_error: Exception | None = None
        for attempt in range(1 + (spec.max_retries if spec.retryable else 0)):
            try:
                result = await asyncio.wait_for(
                    self.tools[tool_name](**args),
                    timeout=spec.timeout_seconds,
                )
                latency = int((time.monotonic() - t0) * 1000)
                self._audit_success(trace_id, session_id, agent_name, tool_name, spec, latency, attempt)
                return result
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"{tool_name} 超时 ({spec.timeout_seconds}s)")
                logger.warning("Tool 超时: %s attempt=%d", tool_name, attempt)
            except Exception as exc:
                last_error = exc
                if not spec.retryable or attempt >= spec.max_retries:
                    break
                logger.warning("Tool 失败，重试: %s attempt=%d error=%s", tool_name, attempt, exc)

        # ── 5. 全部失败 → 审计 + 抛出 ──
        latency = int((time.monotonic() - t0) * 1000)
        self._audit_error(trace_id, session_id, agent_name, tool_name, spec, latency, last_error or Exception("unknown"))
        raise last_error or RuntimeError(f"{tool_name} failed")

    def get_spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """列出所有注册工具及其元数据（供管理后台展示）。"""
        return [
            {
                "name": name,
                "description": (self._specs.get(name, ToolSpec(name=name))).description,
                "risk_level": (self._specs.get(name, ToolSpec(name=name))).risk_level,
                "mutating": (self._specs.get(name, ToolSpec(name=name))).mutating,
                "allowed_agents": (self._specs.get(name, ToolSpec(name=name))).allowed_agents,
                "allowed_args": (self._specs.get(name, ToolSpec(name=name))).allowed_args,
            }
            for name in self.tools
        ]

    # ── 审计日志 ───────────────────────────────────────────────────

    @staticmethod
    def _audit_success(trace_id: str, session_id: str, agent_name: str,
                       tool_name: str, spec: ToolSpec, latency_ms: int, retries: int):
        logger.info(
            "TOOL ✅ trace=%s agent=%s tool=%s risk=%s latency=%dms retries=%d",
            trace_id, agent_name, tool_name, spec.risk_level, latency_ms, retries,
        )

    @staticmethod
    def _audit_denial(trace_id: str, session_id: str, agent_name: str,
                      tool_name: str, spec: ToolSpec, reason: str):
        logger.warning(
            "TOOL 🚫 DENIED trace=%s agent=%s tool=%s risk=%s reason=%s",
            trace_id, agent_name, tool_name, spec.risk_level, reason,
        )

    @staticmethod
    def _audit_error(trace_id: str, session_id: str, agent_name: str,
                     tool_name: str, spec: ToolSpec, latency_ms: int, error: Exception):
        logger.error(
            "TOOL ❌ trace=%s agent=%s tool=%s risk=%s latency=%dms error=%s",
            trace_id, agent_name, tool_name, spec.risk_level, latency_ms, str(error)[:200],
        )
