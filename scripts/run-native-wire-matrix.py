#!/usr/bin/env python3
"""Run Conversations vendor-native wire scenarios (Robolectric + Smack transport)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "interop" / "android"
GRADLEW = ANDROID / "gradlew"


def gradle_wire(props: dict[str, str]) -> int:
    cmd = [str(GRADLEW), ":conv-native:conversationsCryptoWire", "--no-daemon"]
    for key, value in props.items():
        cmd.append(f"-P{key}={value}")
    env = os.environ.copy()
    env.setdefault("OMEMO_XMPP_SECURITY", "disabled")
    return subprocess.call(cmd, cwd=ANDROID, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-roundtrip", action="store_true", help="Native crypto local roundtrip")
    parser.add_argument(
        "--pair",
        choices=["conversations-vs-conversations"],
        help="Live XMPP pair using vendor crypto on both sides",
    )
    args = parser.parse_args()

    if not os.environ.get("ANDROID_HOME"):
        print("ANDROID_HOME required", file=sys.stderr)
        return 1

    if args.self_roundtrip or not args.pair:
        return gradle_wire({"wireMode": "local_roundtrip"})

    if args.pair == "conversations-vs-conversations":
        tag = "native-conv-self"
        bob = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve())],
            env={**os.environ, "NATIVE_WIRE_CHILD": "wait", "NATIVE_WIRE_TAG": tag},
        )
        import time

        time.sleep(12)
        rc = gradle_wire(
            {
                "wireMode": "send",
                "wireJid": "alice@localhost",
                "wirePassword": "alicepass",
                "wirePeer": "bob@localhost",
                "wireSend": f"hello-{tag}",
                "wireDataDir": str(ROOT / "tmp" / "wire-data" / "conv-native" / "alice"),
            }
        )
        bob.wait()
        return rc if rc != 0 else bob.returncode or 0

    return 1


if __name__ == "__main__":
    if os.environ.get("NATIVE_WIRE_CHILD") == "wait":
        tag = os.environ.get("NATIVE_WIRE_TAG", "native")
        sys.exit(
            gradle_wire(
                {
                    "wireMode": "wait",
                    "wireJid": "bob@localhost",
                    "wirePassword": "bobpass",
                    "wireExpect": f"hello-{tag}",
                    "wireDataDir": str(ROOT / "tmp" / "wire-data" / "conv-native" / "bob"),
                }
            )
        )
    sys.exit(main())
