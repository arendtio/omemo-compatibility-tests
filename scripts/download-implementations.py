#!/usr/bin/env python3
"""Clone or update upstream OMEMO implementations into vendor/."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "implementations.yaml"
VENDOR = ROOT / "vendor"


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=cwd)


def clone_or_update(
    repo: str,
    dest: Path,
    branch: str,
) -> None:
    if dest.exists():
        print(f"Updating {dest.name}...")
        run(["git", "fetch", "--depth", "1", "origin", branch], cwd=dest)
        run(["git", "checkout", branch], cwd=dest)
        run(["git", "pull", "origin", branch], cwd=dest)
    else:
        print(f"Cloning {dest.name}...")
        run([
            "git", "clone", "--depth", "1", "--branch", branch,
            repo, str(dest),
        ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Download OMEMO implementations")
    parser.add_argument(
        "--skip-optional",
        action="store_true",
        help="Skip optional large client repositories",
    )
    args = parser.parse_args()

    with open(CONFIG, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    VENDOR.mkdir(exist_ok=True)

    for impl in config["implementations"]:
        if args.skip_optional and impl.get("optional"):
            print(f"Skipping optional: {impl['id']}")
            continue

        dest = VENDOR / impl["id"]
        branch = impl.get("branch", "main")
        clone_or_update(impl["repo"], dest, branch)
        print(f"  OK: {impl['id']}")

    print(f"\nVendor tree ready under {VENDOR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
