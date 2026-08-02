"""Shared Gradle wire-client helpers for compatibility wire tests."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLIENTS_DIR = ROOT / "interop" / "clients"


def launcher(module: str) -> Path:
    return CLIENTS_DIR / module / "build" / "install" / module / "bin" / module


def wire_env() -> dict[str, str]:
    import os

    return {
        **dict(os.environ),
        "OMEMO_INTEROP_ROOT": str(ROOT),
        "OMEMO_XMPP_SECURITY": os.environ.get("OMEMO_XMPP_SECURITY", "auto"),
    }


def roundtrip(
    left_module: str,
    right_module: str,
    hello: str,
    reply: str,
    bob_first: bool = False,
    data_subdir: str = "wire-compat",
) -> int:
    """Run a two-leg OMEMO roundtrip between Gradle wire clients."""
    env = wire_env()
    bob_data = ROOT / "tmp" / data_subdir / right_module / "bob"
    alice_data = ROOT / "tmp" / data_subdir / left_module / "alice"
    bob_data.mkdir(parents=True, exist_ok=True)
    alice_data.mkdir(parents=True, exist_ok=True)

    bob_bin = str(launcher(right_module))
    alice_bin = str(launcher(left_module))

    if bob_first:
        alice_wait = subprocess.Popen(
            [
                alice_bin, "--mode", "wait", "--expect", hello, "--",
                "--jid", "alice@localhost", "--password", "alicepass",
                "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(alice_data),
            ],
            cwd=ROOT, env=env,
        )
        time.sleep(12)
        rc = subprocess.call(
            [
                bob_bin, "--mode", "send", "--peer", "alice@localhost", "--send", hello, "--",
                "--jid", "bob@localhost", "--password", "bobpass",
                "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(bob_data),
            ],
            cwd=ROOT, env=env, timeout=90,
        )
        if rc != 0:
            alice_wait.kill()
            return rc
        try:
            alice_rc = alice_wait.wait(timeout=60)
        except subprocess.TimeoutExpired:
            alice_wait.kill()
            return 1
        if alice_rc != 0:
            return alice_rc
        bob_wait = subprocess.Popen(
            [
                bob_bin, "--mode", "wait", "--expect", reply, "--",
                "--jid", "bob@localhost", "--password", "bobpass",
                "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(bob_data),
            ],
            cwd=ROOT, env=env,
        )
        time.sleep(1)
        rc = subprocess.call(
            [
                alice_bin, "--mode", "send", "--peer", "bob@localhost", "--send", reply, "--",
                "--jid", "alice@localhost", "--password", "alicepass",
                "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(alice_data),
            ],
            cwd=ROOT, env=env, timeout=90,
        )
        if rc != 0:
            bob_wait.kill()
            return rc
        try:
            return bob_wait.wait(timeout=60)
        except subprocess.TimeoutExpired:
            bob_wait.kill()
            return 1

    bob_wait = subprocess.Popen(
        [
            bob_bin, "--mode", "wait", "--expect", hello, "--",
            "--jid", "bob@localhost", "--password", "bobpass",
            "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(bob_data),
        ],
        cwd=ROOT, env=env,
    )
    time.sleep(12)
    rc = subprocess.call(
        [
            alice_bin, "--mode", "send", "--peer", "bob@localhost", "--send", hello, "--",
            "--jid", "alice@localhost", "--password", "alicepass",
            "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(alice_data),
        ],
        cwd=ROOT, env=env, timeout=90,
    )
    if rc != 0:
        bob_wait.kill()
        return rc
    try:
        bob_rc = bob_wait.wait(timeout=60)
    except subprocess.TimeoutExpired:
        bob_wait.kill()
        return 1
    if bob_rc != 0:
        return bob_rc

    alice_wait = subprocess.Popen(
        [
            alice_bin, "--mode", "wait", "--expect", reply, "--",
            "--jid", "alice@localhost", "--password", "alicepass",
            "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(alice_data),
        ],
        cwd=ROOT, env=env,
    )
    time.sleep(1)
    rc = subprocess.call(
        [
            bob_bin, "--mode", "send", "--peer", "alice@localhost", "--send", reply, "--",
            "--jid", "bob@localhost", "--password", "bobpass",
            "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(bob_data),
        ],
        cwd=ROOT, env=env, timeout=90,
    )
    if rc != 0:
        alice_wait.kill()
        return rc
    try:
        return alice_wait.wait(timeout=60)
    except subprocess.TimeoutExpired:
        alice_wait.kill()
        return 1


def wipe_compat_data(data_subdir: str = "wire-compat") -> None:
    import shutil

    wire_root = ROOT / "tmp" / data_subdir
    if wire_root.exists():
        shutil.rmtree(wire_root)
