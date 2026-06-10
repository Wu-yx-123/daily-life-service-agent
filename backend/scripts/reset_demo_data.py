#!/usr/bin/env python
"""清空数据库 → alembic upgrade head → 写入 Demo 数据。

用法：
    python scripts/reset_demo_data.py
    python scripts/reset_demo_data.py --no-seed   # 只迁移，不写 Demo 数据
"""
import argparse
import asyncio
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.database import Base
from app.services.seed_service import ensure_demo_data


async def main(seed: bool = True):
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)

    # 1. 清空所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("✅ 已清空数据库")

    # 2. 运行 alembic 迁移
    backend_dir = os.path.join(os.path.dirname(__file__), "..")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"❌ alembic 迁移失败:\n{result.stderr}")
        sys.exit(1)
    print("✅ alembic upgrade head 完成")

    # 3. 写入 Demo 数据
    if seed:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await ensure_demo_data(session)
            await session.commit()
            print("✅ Demo 数据已写入")

    await engine.dispose()
    print("\n🎉 数据库重置完成：表结构 + Demo 数据已就绪")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-seed", action="store_true", help="只迁移表结构，不写 Demo 数据")
    args = parser.parse_args()
    asyncio.run(main(seed=not args.no_seed))
