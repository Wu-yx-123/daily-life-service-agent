# 作用：集中定义 FastAPI 依赖，包括 Redis 时间锁封装。
from collections.abc import AsyncGenerator

from app.core.config import get_settings
from app.core.redis import TimeLockStore, get_redis_client


async def get_time_lock_store() -> AsyncGenerator[TimeLockStore, None]:
    """FastAPI 依赖：为请求创建 Redis 时间锁封装。"""
    redis = get_redis_client()
    try:
        yield TimeLockStore(redis, get_settings().time_lock_ttl_seconds)
    finally:
        close = getattr(redis, "aclose", None) or getattr(redis, "close", None)
        if close:
            await close()
