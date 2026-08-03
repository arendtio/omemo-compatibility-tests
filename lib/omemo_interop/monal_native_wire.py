"""Monal MLOMEMO vendor-native wire launcher (macOS only)."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MONAL_NATIVE = ROOT / "interop" / "monal-native"
BINARY = MONAL_NATIVE / "build" / "MonalWire"
RUNNER = ROOT / "scripts" / "run-monal-wire.sh"


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


def monal_wire_runner() -> Path:
    if RUNNER.is_file():
        return RUNNER
    return BINARY


def monal_simulator_wire() -> bool:
    return platform.system() == "Darwin" and RUNNER.is_file()


def monal_xmpp_host(host: str) -> str:
    """Simulator processes cannot reach host ejabberd via 127.0.0.1."""
    if host != "127.0.0.1" or not monal_simulator_wire():
        return host
    for iface in ("en0", "en1", "en2"):
        try:
            ip = subprocess.check_output(
                ["ipconfig", "getifaddr", iface], text=True,
            ).strip()
            if ip:
                return ip
        except (subprocess.CalledProcessError, OSError):
            continue
    return host


def monal_native_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("OMEMO_XMPP_SECURITY", "auto")
    env["OMEMO_INTEROP_ROOT"] = str(ROOT)
    env.setdefault("MONAL_VENDOR_REV", monal_vendor_revision())
    frameworks = monal_native_frameworks_dir()
    if frameworks.is_dir():
        prev = env.get("DYLD_FRAMEWORK_PATH", "")
        env["DYLD_FRAMEWORK_PATH"] = (
            f"{frameworks}{os.pathsep}{prev}" if prev else str(frameworks)
        )
    return env


def _monal_cmd(
    mode: str,
    jid: str,
    password: str,
    data_dir: Path,
    peer: str | None,
    send: str | None,
    expect: str | None,
    host: str,
    port: int,
) -> list[str]:
    runner = monal_wire_runner()
    connect_host = monal_xmpp_host(host)
    if connect_host != host:
        print(f"Monal simulator wire: XMPP host {host} -> {connect_host}", flush=True)
    return [
        str(runner),
        "--mode", mode,
        *(["--peer", peer] if peer else []),
        *(["--send", send] if send else []),
        *(["--expect", expect] if expect else []),
        "--",
        "--jid", jid,
        "--password", password,
        "--host", connect_host,
        "--port", str(port),
        "--data-dir", str(data_dir),
    ]


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
    if not monal_native_binary().exists():
        print(f"Monal native wire binary missing: {monal_native_binary()}", flush=True)
        return 2
    cmd = _monal_cmd(mode, jid, password, data_dir, peer, send, expect, host, port)
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
    if not monal_native_binary().exists():
        raise FileNotFoundError(f"Monal native wire binary missing: {monal_native_binary()}")
    cmd = _monal_cmd(mode, jid, password, data_dir, peer, send, expect, host, port)
    log_path = data_dir / "wire-popen.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w", buffering=1)
    return subprocess.Popen(
        cmd, cwd=ROOT, env=monal_native_env(), stdout=log_file, stderr=subprocess.STDOUT,
    )
