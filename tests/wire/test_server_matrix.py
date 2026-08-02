"""Wire tests across XMPP server profiles (ejabberd, Prosody, Tigase)."""

import socket
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SERVER_MATRIX = ROOT / "config" / "server-matrix.yaml"
RUN_SCRIPT = ROOT / "scripts" / "run-server-matrix.py"


def _server_reachable(host: str = "127.0.0.1", port: int = 5222) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _profile_ids() -> list[str]:
    with open(SERVER_MATRIX, encoding="utf-8") as f:
        return list(yaml.safe_load(f)["profiles"].keys())


@pytest.mark.wire
@pytest.mark.parametrize("profile_id", _profile_ids())
def test_server_matrix_slixmpp_roundtrip(profile_id: str) -> None:
    if profile_id == "tigase" and not __import__("os").environ.get("OMEMO_TIGASE_READY"):
        pytest.skip("Tigase requires manual web setup; set OMEMO_TIGASE_READY=1 when configured")

    if not _server_reachable():
        pytest.skip("No XMPP server on 127.0.0.1:5222")

    rc = subprocess.call(
        [sys.executable, str(RUN_SCRIPT), "--profile", profile_id],
        cwd=ROOT,
    )
    assert rc == 0
