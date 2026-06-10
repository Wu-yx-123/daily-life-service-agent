#!/usr/bin/env python3
"""MassageOps-Agent 多步骤 QA：运行后端、前端和 Docker 静态检查。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]


def run(name: str, cmd: list[str], cwd: Path) -> bool:
    print(f"\n== {name} ==")
    result = subprocess.run(cmd, cwd=cwd, text=True)
    print(f"{name}: exit={result.returncode}")
    return result.returncode == 0


def check_docker_sandbox() -> bool:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    required = ["read_only: true", "no-new-privileges:true", "cap_drop:", "- ALL", "tmpfs:"]
    missing = [item for item in required if item not in compose]
    if missing:
        print(f"Docker sandbox missing: {missing}")
        return False
    print("Docker sandbox static check: PASS")
    return True


def main() -> int:
    backend_ok = run(
        "backend pytest",
        [str(REPO_ROOT / "backend" / ".venv" / "bin" / "python"), "-m", "pytest", "app/tests", "-q"],
        REPO_ROOT / "backend",
    )
    frontend_test_ok = run("frontend test", ["npm", "test"], REPO_ROOT / "frontend")
    frontend_build_ok = run("frontend build", ["npm", "run", "build"], REPO_ROOT / "frontend")
    docker_ok = check_docker_sandbox()
    return 0 if all([backend_ok, frontend_test_ok, frontend_build_ok, docker_ok]) else 1


if __name__ == "__main__":
    sys.exit(main())
