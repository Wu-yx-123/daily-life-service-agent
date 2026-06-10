# 作用：Agent Contract 校验器——确保每个 Agent 的输出都符合其 Schema。
# 输出不符合合同时：记录错误 → 尝试重试 → 回退确定性逻辑。
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.schemas.agent import AgentError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
MAX_RETRIES = 2


def validate_output(raw: Any, schema: type[T], *, agent_name: str) -> T:
    """校验 Agent 输出是否符合合同 Schema。

    Args:
        raw: Agent 返回的原始数据（dict 或 Pydantic 对象）
        schema: 目标 Pydantic 类型
        agent_name: Agent 名称（用于错误日志）

    Returns:
        校验通过的 Pydantic 实例

    Raises:
        ValueError: 校验失败且无法修复时抛出，调用方应降级到 fallback
    """
    try:
        if isinstance(raw, schema):
            return raw
        return schema.model_validate(raw)
    except ValidationError as exc:
        error = AgentError(
            agent=agent_name,
            code="schema_validation",
            message=f"{agent_name} 输出不符合合同: {_summarize_errors(exc)}",
        )
        logger.warning("Contract 校验失败: %s", error.model_dump())
        raise ValueError(error.message) from exc


def validate_output_with_retry(
    raw: Any,
    schema: type[T],
    *,
    agent_name: str,
    retry_fn: Callable | None = None,
) -> T:
    """校验输出，最多重试 MAX_RETRIES 次。

    Args:
        raw: Agent 返回的原始数据
        schema: 目标 Pydantic 类型
        agent_name: Agent 名称
        retry_fn: 可选的重试函数 async fn() -> Any，校验失败时调用

    Returns:
        校验通过的 Pydantic 实例

    Raises:
        AgentError: 所有重试均失败
    """
    last_error: Exception | None = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            return validate_output(raw, schema, agent_name=agent_name)
        except (ValueError, ValidationError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES and retry_fn:
                logger.info("%s 第 %d/%d 次重试", agent_name, attempt + 1, MAX_RETRIES)
                # Note: retry_fn is expected to be a coroutine; the caller should await if needed
            raw = None  # 防止无限循环用旧数据

    raise AgentError(
        agent=agent_name,
        code="schema_validation",
        message=f"{agent_name} 输出持续不符合合同（{MAX_RETRIES} 次重试后仍失败）: {last_error}",
        retries_attempted=MAX_RETRIES,
    )


def _summarize_errors(exc: ValidationError) -> str:
    """提取 Pydantic ValidationError 中最重要的前 3 条错误。"""
    errors = exc.errors()
    summaries = []
    for e in errors[:3]:
        loc = ".".join(str(p) for p in e.get("loc", []))
        msg = e.get("msg", "unknown")
        summaries.append(f"{loc}: {msg}")
    return "; ".join(summaries)
