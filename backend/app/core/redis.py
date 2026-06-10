# 作用：封装 Redis 客户端、测试内存 Redis，以及预约临时时间锁。
import json
from dataclasses import dataclass, field
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings


def get_redis_client() -> Redis:
    """创建真实 Redis 客户端，供运行时的时间锁和幂等 Key 使用。"""
    if get_settings().redis_url == "memory://":
        return _memory_redis
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


@dataclass
class InMemoryRedis:
    """测试用极简 Redis 替身。

    实现 set/get/delete/lpush/lrange/expire，覆盖时间锁、幂等 Key 和会话存储。
    """

    values: dict[str, str] = field(default_factory=dict)
    lists: dict[str, list[str]] = field(default_factory=dict)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        existed = 1 if (key in self.values or key in self.lists) else 0
        self.values.pop(key, None)
        self.lists.pop(key, None)
        return existed

    async def lpush(self, key: str, value: str) -> int:
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key].insert(0, value)
        return len(self.lists[key])

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        lst = self.lists.get(key, [])
        return lst[start:stop + 1 if stop >= 0 else None]

    async def expire(self, key: str, ttl: int) -> bool:
        # 内存 Redis 不实现真正的 TTL，测试中无影响
        return True

    async def close(self) -> None:
        return None


_memory_redis = InMemoryRedis()


class TimeLockStore:
    """临时时间锁封装。

    ScheduleAgent 只拿到这个抽象，不直接操作 Redis key，便于后续替换为分布式锁实现。
    """

    def __init__(self, redis: Any, ttl_seconds: int | None = None):
        self.redis = redis
        self.ttl_seconds = ttl_seconds or get_settings().time_lock_ttl_seconds

    @staticmethod
    def key(store_id: str, technician_id: str, start_time: str) -> str:
        """生成同一门店、技师、开始时间唯一的时间锁 Key。"""
        return f"time_lock:{store_id}:{technician_id}:{start_time}"

    async def acquire(self, *, store_id: str, technician_id: str, start_time: str, payload: dict[str, Any]) -> bool:
        # 同一技师同一开始时间只能获取一次锁；锁内容记录用户和 trace，方便排查。
        key = self.key(store_id, technician_id, start_time)
        return bool(await self.redis.set(key, json.dumps(payload), ex=self.ttl_seconds, nx=True))

    async def get(self, *, store_id: str, technician_id: str, start_time: str) -> dict[str, Any] | None:
        raw = await self.redis.get(self.key(store_id, technician_id, start_time))
        return json.loads(raw) if raw else None

    async def release(self, *, store_id: str, technician_id: str, start_time: str) -> None:
        await self.redis.delete(self.key(store_id, technician_id, start_time))
