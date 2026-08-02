#!/usr/bin/env python3
"""Run Conversations vendor-native wire scenarios."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-roundtrip", action="store_true")
    parser.add_argument(
        "--pair",
        choices=[
            "conversations-vs-conversations",
            "conversations-native-vs-siskin",
            "conversations-native-vs-monal",
        ],
    )
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()

    if not os.environ.get("ANDROID_HOME"):
        print("ANDROID_HOME required", file=sys.stderr)
        return 1

    if args.self_roundtrip:
        return subprocess.call(
            [
                sys.executable,
                str(ROOT / "scripts" / "run-interop-matrix.py"),
                "--pair", "conversations-vs-conversations",
                "--native-conversations",
                *(["--build"] if args.build else []),
            ],
            cwd=ROOT,
            env=os.environ.copy(),
        )

    if args.pair:
        pair_map = {
            "conversations-vs-conversations": "conversations-vs-conversations",
            "conversations-native-vs-siskin": "conversations-native-vs-siskin",
            "conversations-native-vs-monal": "conversations-native-vs-monal",
        }
        return subprocess.call(
            [
                sys.executable,
                str(ROOT / "scripts" / "run-interop-matrix.py"),
                "--pair", pair_map[args.pair],
                "--native-conversations",
                *(["--build"] if args.build else []),
            ],
            cwd=ROOT,
            env=os.environ.copy(),
        )

    return subprocess.call(
        [
            str(ROOT / "interop" / "android" / "gradlew"),
            ":conv-native:conversationsCryptoWire",
            "-PwireMode=local_roundtrip",
            "--no-daemon",
        ],
        cwd=ROOT / "interop" / "android",
        env=os.environ.copy(),
    )


if __name__ == "__main__":
    sys.exit(main())
