"""Gradle launcher for Conversations vendor-native wire (Robolectric + Smack transport)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parent.parent.parent
ANDROID = ROOT / "interop" / "android"
GRADLEW = ANDROID / "gradlew"


def native_wire_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("OMEMO_XMPP_SECURITY", "auto")
    return env


def gradle_wire_cmd(props: Mapping[str, str]) -> list[str]:
    cmd = [str(GRADLEW), ":conv-native:conversationsCryptoWire", "--no-daemon"]
    for key, value in props.items():
        cmd.append(f"-P{key}={value}")
    return cmd


def run_native_wire(
    mode: str,
    jid: str,
    password: str,
    data_dir: Path,
    peer: str | None = None,
    send: str | None = None,
    expect: str | None = None,
    host: str = "127.0.0.1",
    port: int = 5222,
    timeout: int = 300,
) -> int:
    if not GRADLEW.exists():
        raise FileNotFoundError(f"Missing {GRADLEW}")
    props: dict[str, str] = {
        "wireMode": mode,
        "wireJid": jid,
        "wirePassword": password,
        "wireHost": host,
        "wirePort": str(port),
        "wireDataDir": str(data_dir),
    }
    if peer:
        props["wirePeer"] = peer
    if send:
        props["wireSend"] = send
    if expect:
        props["wireExpect"] = expect
    return subprocess.call(
        gradle_wire_cmd(props),
        cwd=ANDROID,
        env=native_wire_env(),
        timeout=timeout,
    )


def popen_native_wire(
    mode: str,
    jid: str,
    password: str,
    data_dir: Path,
    peer: str | None = None,
    send: str | None = None,
    expect: str | None = None,
    host: str = "127.0.0.1",
    port: int = 5222,
) -> subprocess.Popen:
    props: dict[str, str] = {
        "wireMode": mode,
        "wireJid": jid,
        "wirePassword": password,
        "wireHost": host,
        "wirePort": str(port),
        "wireDataDir": str(data_dir),
    }
    if peer:
        props["wirePeer"] = peer
    if send:
        props["wireSend"] = send
    if expect:
        props["wireExpect"] = expect
    return subprocess.Popen(
        gradle_wire_cmd(props),
        cwd=ANDROID,
        env=native_wire_env(),
    )


def android_native_available() -> bool:
    return bool(os.environ.get("ANDROID_HOME")) and GRADLEW.exists()
