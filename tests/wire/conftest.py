"""Wire-level OMEMO tests over a live ejabberd instance."""

import asyncio
import socket
import tempfile
from pathlib import Path

import pytest

from omemo_interop.constants import XMPP_HOST, XMPP_PORT


def xmpp_server_reachable() -> bool:
    try:
        with socket.create_connection((XMPP_HOST, XMPP_PORT), timeout=2):
            return True
    except OSError:
        return False


skip_no_server = pytest.mark.skipif(
    not xmpp_server_reachable(),
    reason=f"XMPP server not reachable at {XMPP_HOST}:{XMPP_PORT}",
)


@pytest.fixture
def omemo_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "omemo-data"
    d.mkdir()
    return d
