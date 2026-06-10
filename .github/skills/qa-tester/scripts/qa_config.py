#!/usr/bin/env python3
"""MassageOps-Agent QA config：输出本地推荐环境变量。"""

from __future__ import annotations

import argparse


LOCAL_ENV = {
    "MASSAGEOPS_DATABASE_URL": "sqlite+aiosqlite:///./dev.db",
    "MASSAGEOPS_REDIS_URL": "memory://",
    "VITE_API_BASE": "",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Show MassageOps-Agent QA env")
    parser.add_argument("command", choices=["show", "export"], nargs="?", default="show")
    args = parser.parse_args()

    if args.command == "export":
        for key, value in LOCAL_ENV.items():
            print(f"export {key}='{value}'")
    else:
        for key, value in LOCAL_ENV.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
