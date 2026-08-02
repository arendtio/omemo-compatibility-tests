"""Scenario-based wire interop tests."""

import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
RUN_SCENARIO = ROOT / "scripts" / "run-scenario.py"


def server_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5222), timeout=2):
            return True
    except OSError:
        return False


skip_no_server = pytest.mark.skipif(not server_up(), reason="ejabberd not on 5222")


@pytest.mark.wire
@skip_no_server
def test_full_conversation_scenario() -> None:
    rc = subprocess.call(
        [sys.executable, str(RUN_SCENARIO), str(ROOT / "scenarios" / "legacy" / "full_conversation.yaml")],
        cwd=ROOT,
    )
    assert rc == 0


@pytest.mark.wire
@skip_no_server
def test_message_burst_scenario() -> None:
    rc = subprocess.call(
        [sys.executable, str(RUN_SCENARIO), str(ROOT / "scenarios" / "legacy" / "message_burst.yaml")],
        cwd=ROOT,
    )
    assert rc == 0
