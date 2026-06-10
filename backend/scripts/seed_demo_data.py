#!/usr/bin/env python
"""写入 Demo 数据（幂等）。

用法：
    python scripts/seed_demo_data.py
    MASSAGEOPS_DATABASE_URL=postgresql+asyncpg://... python scripts/seed_demo_data.py

退出码：0=成功 1=失败
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.services.seed_service import ensure_demo_data


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await ensure_demo_data(session)
            await session.commit()
            print("✅ Demo 数据已写入")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
