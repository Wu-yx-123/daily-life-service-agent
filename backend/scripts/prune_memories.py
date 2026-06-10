#!/usr/bin/env python
"""清理长期记忆。

默认 dry-run，只输出将清理的数量，不会真正删除。

用法：
    python scripts/prune_memories.py
    python scripts/prune_memories.py --execute
    python scripts/prune_memories.py --user-id 00000000-0000-0000-0000-000000000001 --execute
    python scripts/prune_memories.py --delete-user --user-id 00000000-0000-0000-0000-000000000001 --execute
"""
import argparse
import asyncio
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.services.memory_retention_service import MemoryRetentionService


async def main(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            service = MemoryRetentionService(session)
            dry_run = not args.execute
            if args.delete_user:
                if not args.user_id:
                    print("❌ --delete-user 必须同时提供 --user-id")
                    return 1
                result = await service.delete_user_memories(user_id=args.user_id, dry_run=dry_run)
            else:
                result = await service.prune_stale_memories(
                    preference_days=args.preference_days,
                    semantic_days=args.semantic_days,
                    max_preference_confidence=Decimal(str(args.max_preference_confidence)),
                    max_semantic_importance=Decimal(str(args.max_semantic_importance)),
                    user_id=args.user_id,
                    dry_run=dry_run,
                )

            mode = "预览" if result.dry_run else "已执行"
            print(f"🧠 记忆清理{mode}")
            print(f"- 结构化偏好: {result.structured_preferences}")
            print(f"- 语义记忆片段: {result.semantic_chunks}")
            print(f"- 合计: {result.total}")
            if result.dry_run:
                print("\n提示：加 --execute 才会真正删除。")
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清理 MassageOps 长期记忆")
    parser.add_argument("--execute", action="store_true", help="真正执行删除；默认只 dry-run 预览")
    parser.add_argument("--user-id", help="只清理指定用户的长期记忆")
    parser.add_argument("--delete-user", action="store_true", help="删除指定用户的全部长期记忆，需配合 --user-id")
    parser.add_argument("--preference-days", type=int, default=90, help="结构化偏好超过多少天未出现才清理")
    parser.add_argument("--semantic-days", type=int, default=180, help="语义记忆超过多少天才清理")
    parser.add_argument("--max-preference-confidence", default="0.65", help="低于该置信度的结构化偏好才清理")
    parser.add_argument("--max-semantic-importance", default="0.60", help="低于该重要性的语义记忆才清理")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
