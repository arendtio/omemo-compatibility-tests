"""Wire tests: Conversations vendor-native crypto vs Smack proxy peers."""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
INTEROP = ROOT / "scripts" / "run-interop-matrix.py"
NATIVE_WIRE = ROOT / "scripts" / "run-native-wire-matrix.py"


def xmpp_server_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5222), timeout=2):
            return True
    except OSError:
        return False


skip_no_server = pytest.mark.skipif(
    not xmpp_server_reachable(),
    reason="XMPP server not reachable on 127.0.0.1:5222",
)
skip_no_android = pytest.mark.skipif(
    not __import__("os").environ.get("ANDROID_HOME"),
    reason="ANDROID_HOME unset",
)


@pytest.mark.wire
@pytest.mark.native
@skip_no_android
@skip_no_server
def test_native_conversations_vs_siskin_matrix() -> None:
    rc = subprocess.call(
        [sys.executable, str(INTEROP), "--pair", "conversations-native-vs-siskin", "--build", "--native-conversations"],
        cwd=ROOT,
        env={**dict(__import__("os").environ), "OMEMO_XMPP_SECURITY": "disabled"},
        timeout=600,
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.native
@skip_no_android
@skip_no_server
def test_native_conversations_vs_monal_matrix() -> None:
    rc = subprocess.call(
        [sys.executable, str(INTEROP), "--pair", "conversations-native-vs-monal", "--build", "--native-conversations"],
        cwd=ROOT,
        env={**dict(__import__("os").environ), "OMEMO_XMPP_SECURITY": "disabled"},
        timeout=600,
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.native
@skip_no_android
@skip_no_server
def test_native_conversations_self_roundtrip_via_script() -> None:
    """Native vendor Alice (left) vs Smack Conversations proxy Bob (right)."""
    rc = subprocess.call(
        [sys.executable, str(NATIVE_WIRE), "--pair", "conversations-vs-conversations", "--build"],
        cwd=ROOT,
        env={**dict(__import__("os").environ), "OMEMO_XMPP_SECURITY": "disabled"},
        timeout=600,
    )
    assert rc == 0
