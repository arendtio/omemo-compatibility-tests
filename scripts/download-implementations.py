#!/usr/bin/env python3
"""Clone or update upstream implementations into vendor/ with optional ref overrides."""

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


def parse_refs(ref_args: list[str]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for item in ref_args:
        if "=" not in item:
            print(f"Invalid --ref format (expected id=ref): {item}", file=sys.stderr)
            sys.exit(2)
        impl_id, ref = item.split("=", 1)
        refs[impl_id.strip()] = ref.strip()
    return refs


def clone_or_update(repo: str, dest: Path, default_branch: str, ref: str | None) -> None:
    target = ref or default_branch

    if dest.exists():
        print(f"Updating {dest.name} -> {target}...")
        if ref:
            run(["git", "fetch", "origin", target], cwd=dest)
            run(["git", "checkout", target], cwd=dest)
            if not run(["git", "pull", "origin", target], cwd=dest):
                pass
        else:
            run(["git", "fetch", "--depth", "1", "origin", target], cwd=dest)
            run(["git", "checkout", target], cwd=dest)
            run(["git", "pull", "origin", target], cwd=dest)
    else:
        print(f"Cloning {dest.name} ({target})...")
        run([
            "git", "clone", "--depth", "1", "--branch", target,
            repo, str(dest),
        ])
        if ref and run(["git", "checkout", target], cwd=dest) != 0:
            run(["git", "fetch", "--depth", "1", "origin", target], cwd=dest)
            run(["git", "checkout", target], cwd=dest)

    rev = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=dest, text=True,
    ).strip()
    print(f"  at {rev[:12]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download OMEMO implementations")
    parser.add_argument(
        "--skip-optional",
        action="store_true",
        help="Skip optional implementations (e.g. python-twomemo)",
    )
    parser.add_argument(
        "--ref",
        action="append",
        default=[],
        metavar="ID=REF",
        help="Checkout specific ref for an implementation (e.g. conversations=2.20.1)",
    )
    args = parser.parse_args()

    ref_map = parse_refs(args.ref)

    with open(CONFIG, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    VENDOR.mkdir(exist_ok=True)

    for impl in config["implementations"]:
        if args.skip_optional and impl.get("optional"):
            print(f"Skipping optional: {impl['id']}")
            continue

        dest = VENDOR / impl["id"]
        branch = impl.get("branch", "main")
        ref = ref_map.get(impl["id"])
        clone_or_update(impl["repo"], dest, branch, ref)
        print(f"  OK: {impl['id']}")

    print(f"\nVendor tree ready under {VENDOR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
