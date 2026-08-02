"""Live Conversations vendor-native wire (Smack transport + AxolotlService crypto)."""

import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "run-native-wire-matrix.py"


def xmpp_server_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5222), timeout=2):
            return True
    except OSError:
        return False


@pytest.mark.wire
@pytest.mark.native
@pytest.mark.skipif(not __import__("os").environ.get("ANDROID_HOME"), reason="ANDROID_HOME unset")
@pytest.mark.skipif(not xmpp_server_reachable(), reason="XMPP server not on 127.0.0.1:5222")
def test_conversations_native_vs_native_live() -> None:
    rc = subprocess.call(
        [sys.executable, str(SCRIPT), "--pair", "conversations-vs-conversations"],
        cwd=ROOT,
        env={**dict(__import__("os").environ), "OMEMO_XMPP_SECURITY": "disabled"},
    )
    assert rc == 0
