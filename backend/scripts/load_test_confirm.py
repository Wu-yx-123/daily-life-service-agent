#!/usr/bin/env python
"""并发确认压测——验证 Redis 锁 + 幂等 Key + DB 事务三道防线。

用法：
    python scripts/load_test_confirm.py [--requests 50] [--base-url http://localhost:8000]

输出报告 JSON 到 stdout，包含请求数、成功数、拒绝数、延迟分布等。
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def _create_booking(client: httpx.AsyncClient, base: str) -> tuple[str, str]:
    resp = await client.post(
        f"{base}/api/v1/conversations/message",
        json={
            "session_id": f"load_test_{id(asyncio.current_task())}",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "message": "明天20点想约一个60分钟肩颈按摩，预算300以内。",
        },
    )
    resp.raise_for_status()
    body = resp.json()
    return body["trace_id"], body["options"][0]["option_id"]


async def main(total: int, base_url: str):
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        # 1. 预约
        trace_id, option_id = await _create_booking(client, base_url)
        print(f"booking ready: trace={trace_id[:20]}... option={option_id[:20]}...")

        # 2. 并发确认
        latencies: list[float] = []

        async def confirm(i: int):
            t0 = time.monotonic()
            resp = await client.post(
                f"{base_url}/api/v1/orders/confirm",
                json={"trace_id": trace_id, "option_id": option_id, "user_confirmed": True},
            )
            latencies.append(time.monotonic() - t0)
            return resp

        print(f"firing {total} concurrent confirm requests...")
        t_start = time.monotonic()
        results = await asyncio.gather(*[confirm(i) for i in range(total)])
        elapsed = time.monotonic() - t_start
        print(f"done in {elapsed:.2f}s")

        # 3. 统计
        success = [r for r in results if r.status_code == 200]
        conflict = [r for r in results if r.status_code == 409]
        other = [r for r in results if r.status_code not in (200, 409)]
        order_ids = list({r.json().get("order_id") for r in success if r.json().get("order_id")})

        latencies_ms = sorted([l * 1000 for l in latencies])
        avg_lat = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0
        p95_idx = int(len(latencies_ms) * 0.95)
        p95_lat = latencies_ms[p95_idx] if latencies_ms else 0
        p99_lat = latencies_ms[int(len(latencies_ms) * 0.99)] if latencies_ms else 0

        report = {
            "total_requests": total,
            "success_orders": len(order_ids),
            "duplicate_idempotent": len([r for r in success if "duplicate" in (r.json().get("status", ""))]),
            "conflict_rejected": len(conflict),
            "other_errors": len(other),
            "duplicate_orders": len(success) - len(order_ids),
            "order_ids": order_ids,
            "avg_latency_ms": round(avg_lat, 1),
            "p95_latency_ms": round(p95_lat, 1),
            "p99_latency_ms": round(p99_lat, 1),
            "min_latency_ms": round(latencies_ms[0], 1) if latencies_ms else 0,
            "max_latency_ms": round(latencies_ms[-1], 1) if latencies_ms else 0,
            "elapsed_seconds": round(elapsed, 2),
        }

        print(json.dumps(report, indent=2, ensure_ascii=False))

        # 验证
        if len(order_ids) != 1:
            print(f"\n⚠️  预期 1 个 order_id，实际 {len(order_ids)}: {order_ids}", file=sys.stderr)
            sys.exit(1)
        print(f"\n✅ 并发压测通过：{total}请求 → 1个订单 + 幂等/冲突拒绝", file=sys.stderr)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--requests", type=int, default=50)
    p.add_argument("--base-url", default="http://localhost:8000")
    args = p.parse_args()
    asyncio.run(main(args.requests, args.base_url))
