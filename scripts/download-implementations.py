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


def looks_like_commit(ref: str) -> bool:
    return len(ref) >= 7 and all(c in "0123456789abcdef" for c in ref.lower())


def clone_or_update(repo: str, dest: Path, default_branch: str, ref: str | None) -> None:
    if dest.exists():
        print(f"Updating {dest.name} -> {ref or default_branch}...")
        if ref:
            run(["git", "fetch", "origin", ref], cwd=dest)
            run(["git", "checkout", ref], cwd=dest)
            if not looks_like_commit(ref):
                run(["git", "pull", "origin", ref], cwd=dest)
        else:
            run(["git", "fetch", "--depth", "1", "origin", default_branch], cwd=dest)
            run(["git", "checkout", default_branch], cwd=dest)
            run(["git", "pull", "origin", default_branch], cwd=dest)
    else:
        label = ref or default_branch
        print(f"Cloning {dest.name} ({label})...")
        run(["git", "clone", repo, str(dest)])
        if ref:
            if looks_like_commit(ref) or run(["git", "checkout", ref], cwd=dest) != 0:
                run(["git", "fetch", "--depth", "1", "origin", ref], cwd=dest)
                run(["git", "checkout", ref], cwd=dest)
        elif default_branch:
            run(["git", "checkout", default_branch], cwd=dest)

    if not dest.exists():
        return

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
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="ID",
        help="Download only these implementation ids (may be repeated)",
    )
    args = parser.parse_args()

    ref_map = parse_refs(args.ref)
    only_ids = {item.strip() for item in args.only} if args.only else None

    with open(CONFIG, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    VENDOR.mkdir(exist_ok=True)

    for impl in config["implementations"]:
        impl_id = impl["id"]
        if only_ids is not None and impl_id not in only_ids:
            continue
        if args.skip_optional and impl.get("optional") and impl_id not in ref_map:
            print(f"Skipping optional: {impl_id}")
            continue

        dest = VENDOR / impl.get("dir", impl_id)
        branch = impl.get("branch", "main")
        ref = ref_map.get(impl_id)
        clone_or_update(impl["repo"], dest, branch, ref)
        if not dest.exists():
            print(f"  FAILED: {impl_id} (clone/update did not produce {dest})", file=sys.stderr)
            return 1
        print(f"  OK: {impl_id}")

    print(f"\nVendor tree ready under {VENDOR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
