# 作用：会话级记忆存储，支撑多轮对话上下文。
# 消息历史用 Redis List，AgentState 用 Redis String (JSON)，TTL 2 小时。
import json
import logging
from typing import Any

from app.core.config import get_settings
from app.core.redis import TimeLockStore

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TTL_SECONDS = 7200  # 2 小时


class SessionStore:
    """会话记忆存储。

    - 消息历史：(session_id):history → Redis List
    - AgentState：(session_id):state → Redis String (JSON)
    - TTL 自动续期，每次写入刷新
    """

    def __init__(self, redis: Any, ttl_seconds: int | None = None):
        self.redis = redis
        self.ttl = ttl_seconds or DEFAULT_SESSION_TTL_SECONDS

    # ── Key 命名 ──────────────────────────────────────────────────

    @staticmethod
    def history_key(session_id: str) -> str:
        return f"session:{session_id}:history"

    @staticmethod
    def state_key(session_id: str) -> str:
        return f"session:{session_id}:state"

    # ── 消息历史 ──────────────────────────────────────────────────

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息到会话历史，刷新 TTL。"""
        key = self.history_key(session_id)
        entry = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        await self.redis.lpush(key, entry)
        await self.redis.expire(key, self.ttl)

    async def recent_messages(self, session_id: str, n: int = 10) -> list[dict[str, str]]:
        """获取最近 n 条消息，按时间正序返回（最早的在前）。"""
        key = self.history_key(session_id)
        raw = await self.redis.lrange(key, 0, n - 1)
        if not raw:
            return []
        messages = [json.loads(m) for m in reversed(raw) if isinstance(m, str)]
        return [m for m in messages if isinstance(m, dict)]

    # ── AgentState 持久化 ─────────────────────────────────────────

    async def save_state(self, session_id: str, state: dict[str, Any]) -> None:
        """保存当前 AgentState 快照。"""
        key = self.state_key(session_id)
        # 只保留可序列化字段，排除大型嵌套
        saveable = _state_to_saveable(state)
        await self.redis.set(key, json.dumps(saveable, ensure_ascii=False, default=str), ex=self.ttl)

    async def get_last_state(self, session_id: str) -> dict[str, Any] | None:
        """读取上一次执行的 AgentState。"""
        key = self.state_key(session_id)
        raw = await self.redis.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def clear(self, session_id: str) -> None:
        """清除会话所有数据。"""
        for key in [self.history_key(session_id), self.state_key(session_id)]:
            await self.redis.delete(key)


# ── 辅助 ──────────────────────────────────────────────────────────

def _state_to_saveable(state: dict[str, Any]) -> dict[str, Any]:
    """提取 AgentState 中需要跨轮保留的上下文字段。

    保留：selected_option, candidates, task_type, order_draft 等业务上下文
    丢弃：errors, verification, final_response 等单轮临时信息
    """
    keep_keys = {
        "selected_option", "candidates", "task_type", "intent",
        "order_draft", "schedule_check", "price_result",
        "risk_result", "approval_request", "trace_id",
    }
    return {k: v for k, v in state.items() if k in keep_keys and v is not None}


# ── 单例 ──────────────────────────────────────────────────────────

_session_store: SessionStore | None = None


def get_session_store(redis: Any | None = None) -> SessionStore:
    global _session_store
    if _session_store is None:
        from app.core.redis import get_redis_client
        _session_store = SessionStore(redis or get_redis_client())
    return _session_store
