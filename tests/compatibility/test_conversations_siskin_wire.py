"""Wire-level compatibility tests for Conversations vs Siskin Gradle runners."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
INTEROP_SCRIPT = ROOT / "scripts" / "run-interop-matrix.py"
CLIENTS_DIR = ROOT / "interop" / "clients"
MATRIX = ROOT / "config" / "interop-matrix.yaml"


def xmpp_server_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5222), timeout=2):
            return True
    except OSError:
        return False


skip_no_server = pytest.mark.skipif(
    not xmpp_server_reachable(),
    reason="ejabberd not reachable on 127.0.0.1:5222",
)


def _launcher(module: str) -> Path:
    return CLIENTS_DIR / module / "build" / "install" / module / "bin" / module


def _roundtrip(
    left_module: str,
    right_module: str,
    hello: str,
    reply: str,
    bob_first: bool = False,
) -> int:
    """Run a two-leg OMEMO roundtrip between Gradle wire clients."""
    env = {
        **dict(__import__("os").environ),
        "OMEMO_INTEROP_ROOT": str(ROOT),
        "OMEMO_XMPP_SECURITY": __import__("os").environ.get("OMEMO_XMPP_SECURITY", "auto"),
    }
    bob_data = ROOT / "tmp" / "wire-compat" / right_module / "bob"
    alice_data = ROOT / "tmp" / "wire-compat" / left_module / "alice"
    bob_data.mkdir(parents=True, exist_ok=True)
    alice_data.mkdir(parents=True, exist_ok=True)

    bob_bin = str(_launcher(right_module))
    alice_bin = str(_launcher(left_module))

    if bob_first:
        alice_wait = subprocess.Popen(
            [alice_bin, "--mode", "wait", "--expect", hello, "--",
             "--jid", "alice@localhost", "--password", "alicepass",
             "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(alice_data)],
            cwd=ROOT, env=env,
        )
        time.sleep(12)
        rc = subprocess.call(
            [bob_bin, "--mode", "send", "--peer", "alice@localhost", "--send", hello, "--",
             "--jid", "bob@localhost", "--password", "bobpass",
             "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(bob_data)],
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
            [bob_bin, "--mode", "wait", "--expect", reply, "--",
             "--jid", "bob@localhost", "--password", "bobpass",
             "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(bob_data)],
            cwd=ROOT, env=env,
        )
        time.sleep(1)
        rc = subprocess.call(
            [alice_bin, "--mode", "send", "--peer", "bob@localhost", "--send", reply, "--",
             "--jid", "alice@localhost", "--password", "alicepass",
             "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(alice_data)],
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
        [bob_bin, "--mode", "wait", "--expect", hello, "--",
         "--jid", "bob@localhost", "--password", "bobpass",
         "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(bob_data)],
        cwd=ROOT, env=env,
    )
    time.sleep(12)
    rc = subprocess.call(
        [alice_bin, "--mode", "send", "--peer", "bob@localhost", "--send", hello, "--",
         "--jid", "alice@localhost", "--password", "alicepass",
         "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(alice_data)],
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
        [alice_bin, "--mode", "wait", "--expect", reply, "--",
         "--jid", "alice@localhost", "--password", "alicepass",
         "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(alice_data)],
        cwd=ROOT, env=env,
    )
    time.sleep(1)
    rc = subprocess.call(
        [bob_bin, "--mode", "send", "--peer", "alice@localhost", "--send", reply, "--",
         "--jid", "bob@localhost", "--password", "bobpass",
         "--host", "127.0.0.1", "--port", "5222", "--data-dir", str(bob_data)],
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


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_conversations_vs_siskin_matrix() -> None:
    rc = subprocess.call(
        [sys.executable, str(INTEROP_SCRIPT), "--pair", "conversations-vs-siskin"],
        cwd=ROOT,
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_bob_siskin_sends_first() -> None:
    """Siskin-initiated session: prekey handshake when recipient has no prior session."""
    import shutil
    wire_root = ROOT / "tmp" / "wire-compat"
    if wire_root.exists():
        shutil.rmtree(wire_root)
    rc = _roundtrip(
        "conversations", "siskin",
        hello="siskin-init-🧪",
        reply="conv-reply-after-siskin-init",
        bob_first=True,
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_unicode_roundtrip() -> None:
    import shutil
    wire_root = ROOT / "tmp" / "wire-compat"
    if wire_root.exists():
        shutil.rmtree(wire_root)
    rc = _roundtrip(
        "conversations", "siskin",
        hello="hello-unicode-🧪-siskin",
        reply="reply-unicode-🧪-conv",
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_session_survives_after_first_message() -> None:
    """Second message on existing OMEMO session (no fresh prekey handshake)."""
    import shutil
    wire_root = ROOT / "tmp" / "wire-compat"
    if wire_root.exists():
        shutil.rmtree(wire_root)
    rc = _roundtrip(
        "conversations", "siskin",
        hello="session-msg-1",
        reply="session-msg-2",
    )
    assert rc == 0
    # Second exchange reusing same data dirs
    rc = _roundtrip(
        "conversations", "siskin",
        hello="session-msg-3",
        reply="session-msg-4",
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_cross_fetch_without_prior_roster() -> None:
    """Bob connects and waits before Alice adds him to roster — open PEP must still deliver."""
    import shutil
    wire_root = ROOT / "tmp" / "wire-compat"
    if wire_root.exists():
        shutil.rmtree(wire_root)
    rc = _roundtrip(
        "conversations", "siskin",
        hello="open-pep-fetch",
        reply="open-pep-reply",
    )
    assert rc == 0
