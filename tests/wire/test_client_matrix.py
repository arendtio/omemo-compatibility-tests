"""Legacy OMEMO (eu.siacs.conversations.axolotl) cross-client wire tests."""

import socket
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
MATRIX = ROOT / "config" / "interop-matrix.yaml"
INTEROP_SCRIPT = ROOT / "scripts" / "run-interop-matrix.py"


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


@pytest.fixture
def matrix_pairs() -> list:
    with open(MATRIX, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["pairs"]


@pytest.mark.wire
@skip_no_server
def test_conversations_vs_siskin_legacy_roundtrip() -> None:
    """Conversations vendor runner and Siskin vendor runner over ejabberd."""
    rc = subprocess.call(
        [sys.executable, str(INTEROP_SCRIPT), "--pair", "conversations-vs-siskin", "--build"],
        cwd=ROOT,
    )
    assert rc == 0


@pytest.mark.wire
@skip_no_server
def test_conversations_vs_monal_legacy_roundtrip() -> None:
    """Conversations vendor runner and Monal vendor runner over ejabberd."""
    rc = subprocess.call(
        [sys.executable, str(INTEROP_SCRIPT), "--pair", "conversations-vs-monal", "--build"],
        cwd=ROOT,
    )
    assert rc == 0


@pytest.mark.wire
@skip_no_server
@pytest.mark.parametrize("pair_id", ["conversations-vs-conversations", "monal-vs-monal"])
def test_client_sanity_pairs(pair_id: str, matrix_pairs: list) -> None:
    ids = {p["id"] for p in matrix_pairs}
    assert pair_id in ids
    rc = subprocess.call(
        [sys.executable, str(INTEROP_SCRIPT), "--pair", pair_id, "--build"],
        cwd=ROOT,
    )
    assert rc == 0
