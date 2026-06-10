#!/usr/bin/env python3
"""MassageOps-Agent QA 记录校验：检查进度文件是否包含实际执行证据。"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
PROGRESS_FILE = REPO_ROOT / ".github" / "skills" / "qa-tester" / "QA_TEST_PROGRESS.md"
EVIDENCE = [r"\d+\s+passed", r"success", r"200", r"通过", r"PASS", r"成功"]


def main() -> int:
    text = PROGRESS_FILE.read_text(encoding="utf-8")
    missing = [pattern for pattern in EVIDENCE if not re.search(pattern, text, re.IGNORECASE)]
    print("QA progress evidence check")
    print(f"file={PROGRESS_FILE.relative_to(REPO_ROOT)}")
    print(f"missing_patterns={missing}")
    return 0 if len(missing) < len(EVIDENCE) else 1


if __name__ == "__main__":
    sys.exit(main())
