"""Static source-audit helpers (commit-pinned control-flow review)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from omemo_interop.runner_registry import ROOT


def vendor_path(rel: str) -> Path:
    return ROOT / rel


def read_vendor(rel: str) -> str:
    path = vendor_path(rel)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8", errors="replace")


def git_rev(rel_dir: str) -> Optional[str]:
    path = vendor_path(rel_dir)
    if not (path / ".git").exists():
        return None
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def line_window(text: str, pattern: str, context: int = 0) -> Optional[str]:
    for i, line in enumerate(text.splitlines(), start=1):
        if re.search(pattern, line):
            start = max(1, i - context)
            end = i + context
            lines = text.splitlines()[start - 1:end]
            return "\n".join(f"{start + j}: {lines[j]}" for j in range(len(lines)))
    return None


def assert_pattern(text: str, pattern: str, description: str) -> None:
    if not re.search(pattern, text, re.MULTILINE | re.DOTALL):
        raise AssertionError(f"Expected pattern for {description}: {pattern!r}")


def assert_no_pattern(text: str, pattern: str, description: str) -> None:
    if re.search(pattern, text, re.MULTILINE | re.DOTALL):
        raise AssertionError(f"Unexpected pattern for {description}: {pattern!r}")


def count_matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, re.MULTILINE))
