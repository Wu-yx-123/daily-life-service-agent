#!/usr/bin/env python3
"""MassageOps-Agent QA bootstrap：检查本地依赖和基础目录。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]


def main() -> int:
    checks = {
        "backend/.venv": (REPO_ROOT / "backend" / ".venv").exists(),
        "frontend/node_modules": (REPO_ROOT / "frontend" / "node_modules").exists(),
        "dev_spec.md": (REPO_ROOT / "dev_spec.md").exists(),
        "docker-compose.yml": (REPO_ROOT / "docker-compose.yml").exists(),
        "python": shutil.which(str(REPO_ROOT / "backend" / ".venv" / "bin" / "python")) is not None,
        "npm": shutil.which("npm") is not None,
    }
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
