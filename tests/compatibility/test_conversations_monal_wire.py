"""Wire-level compatibility tests for Conversations vs Monal Gradle runners."""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tests.compatibility.wire_helpers import roundtrip, wipe_compat_data

ROOT = Path(__file__).resolve().parent.parent.parent
INTEROP_SCRIPT = ROOT / "scripts" / "run-interop-matrix.py"


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


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_conversations_vs_monal_matrix() -> None:
    rc = subprocess.call(
        [sys.executable, str(INTEROP_SCRIPT), "--pair", "conversations-vs-monal"],
        cwd=ROOT,
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_bob_monal_sends_first() -> None:
    """Monal-initiated session: prekey handshake when recipient has no prior session."""
    wipe_compat_data()
    rc = roundtrip(
        "conversations", "monal",
        hello="monal-init-🧪",
        reply="conv-reply-after-monal-init",
        bob_first=True,
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_unicode_roundtrip_monal() -> None:
    wipe_compat_data()
    rc = roundtrip(
        "conversations", "monal",
        hello="hello-unicode-🧪-monal",
        reply="reply-unicode-🧪-conv",
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_session_survives_after_first_message_monal() -> None:
    """Second message on existing OMEMO session (no fresh prekey handshake)."""
    wipe_compat_data()
    rc = roundtrip(
        "conversations", "monal",
        hello="session-msg-1",
        reply="session-msg-2",
    )
    assert rc == 0
    rc = roundtrip(
        "conversations", "monal",
        hello="session-msg-3",
        reply="session-msg-4",
    )
    assert rc == 0


@pytest.mark.wire
@pytest.mark.compatibility
@skip_no_server
def test_wire_cross_fetch_without_prior_roster_monal() -> None:
    """Bob connects before Alice adds roster — open PEP must still deliver bundles."""
    wipe_compat_data()
    rc = roundtrip(
        "conversations", "monal",
        hello="open-pep-fetch-monal",
        reply="open-pep-reply-monal",
    )
    assert rc == 0
