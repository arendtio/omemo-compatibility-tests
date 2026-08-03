"""Monal MLOMEMO vendor-native wire launcher (macOS only)."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MONAL_NATIVE = ROOT / "interop" / "monal-native"
BINARY = MONAL_NATIVE / "build" / "MonalWire"


def native_macos_wire_enabled() -> bool:
    if os.environ.get("OMEMO_FORCE_SMACK_PROXY") == "1":
        return False
    if os.environ.get("OMEMO_NATIVE_MACOS") == "1":
        return True
    return platform.system() == "Darwin"


def monal_native_binary() -> Path:
    return BINARY


def monal_native_frameworks_dir() -> Path:
    return MONAL_NATIVE / "build" / "Frameworks"


def monal_vendor_revision() -> str:
    monal = ROOT / "vendor" / "monal"
    if not monal.is_dir():
        return "unknown"
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=monal, text=True,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def monal_native_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("OMEMO_XMPP_SECURITY", "auto")
    env["OMEMO_INTEROP_ROOT"] = str(ROOT)
    env.setdefault("MONAL_VENDOR_REV", monal_vendor_revision())
    frameworks = monal_native_frameworks_dir()
    if frameworks.is_dir():
        prev = env.get("DYLD_LIBRARY_PATH", "")
        env["DYLD_LIBRARY_PATH"] = (
            f"{frameworks}{os.pathsep}{prev}" if prev else str(frameworks)
        )
    return env


def build_monal_native() -> int:
    if not native_macos_wire_enabled():
        return 0
    script = ROOT / "scripts" / "build-monal-native.sh"
    if not script.exists():
        return 2
    return subprocess.call([str(script)], cwd=ROOT)


def run_monal_native_wire(
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
    bin_path = monal_native_binary()
    if not bin_path.exists():
        print(f"Monal native wire binary missing: {bin_path}", flush=True)
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
    return subprocess.call(cmd, cwd=ROOT, env=monal_native_env(), timeout=timeout)


def popen_monal_native_wire(
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
    bin_path = monal_native_binary()
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
    log_path = data_dir / "wire-popen.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w", buffering=1)
    return subprocess.Popen(
        cmd, cwd=ROOT, env=monal_native_env(), stdout=log_file, stderr=subprocess.STDOUT,
    )
