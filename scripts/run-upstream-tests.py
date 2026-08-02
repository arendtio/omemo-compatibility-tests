#!/usr/bin/env python3
"""Run upstream unit tests defined in config/implementations.yaml."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "implementations.yaml"


def main() -> int:
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    commands = cfg.get("upstream_test_commands", {})
    failed: list[tuple[str, int]] = []

    for impl_id, cmd in commands.items():
        vendor = ROOT / "vendor" / impl_id
        if not vendor.exists():
            print(f"SKIP upstream {impl_id}: vendor missing")
            continue
        print(f"Running upstream tests: {impl_id}")
        rc = subprocess.call(cmd, shell=True, cwd=vendor)
        if rc != 0:
            failed.append((impl_id, rc))
            print(f"FAIL upstream {impl_id} (exit {rc})")
        else:
            print(f"PASS upstream {impl_id}")

    if failed:
        print("Upstream failures:", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
