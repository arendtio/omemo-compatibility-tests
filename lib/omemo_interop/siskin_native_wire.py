"""Gradle-style launcher for Siskin vendor-native wire (Martin + MartinOMEMO on macOS)."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SISKIN_NATIVE = ROOT / "interop" / "siskin-native"
BINARY = SISKIN_NATIVE / ".build" / "release" / "siskin-native-wire"


def native_macos_wire_enabled() -> bool:
    if os.environ.get("OMEMO_FORCE_SMACK_PROXY") == "1":
        return False
    if os.environ.get("OMEMO_NATIVE_MACOS") == "1":
        return True
    return platform.system() == "Darwin"


def siskin_native_binary() -> Path:
    return BINARY


def build_siskin_native() -> int:
    if not native_macos_wire_enabled():
        return 0
    return subprocess.call(
        ["swift", "build", "-c", "release", "--package-path", str(SISKIN_NATIVE)],
        cwd=ROOT,
    )


def run_siskin_native_wire(
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
    bin_path = siskin_native_binary()
    if not bin_path.exists():
        print(f"Siskin native wire binary missing: {bin_path}", flush=True)
        return 2
    cmd = [
        str(bin_path),
        "--mode", mode,
        *(["--peer", peer] if peer else []),
        *(["--send", send] if send else []),
        *(["--expect", expect] if expect else []),
        "--",
        "--jid", jid,
        "--password", password,
        "--host", host,
        "--port", str(port),
        "--data-dir", str(data_dir),
    ]
    env = os.environ.copy()
    env.setdefault("OMEMO_XMPP_SECURITY", "auto")
    env["OMEMO_INTEROP_ROOT"] = str(ROOT)
    return subprocess.call(cmd, cwd=ROOT, env=env, timeout=timeout)


def popen_siskin_native_wire(
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
    bin_path = siskin_native_binary()
    cmd = [
        str(bin_path),
        "--mode", mode,
        *(["--peer", peer] if peer else []),
        *(["--send", send] if send else []),
        *(["--expect", expect] if expect else []),
        "--",
        "--jid", jid,
        "--password", password,
        "--host", host,
        "--port", str(port),
        "--data-dir", str(data_dir),
    ]
    env = os.environ.copy()
    env.setdefault("OMEMO_XMPP_SECURITY", "auto")
    env["OMEMO_INTEROP_ROOT"] = str(ROOT)
    log_path = data_dir / "wire-popen.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w", buffering=1)
    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT)
