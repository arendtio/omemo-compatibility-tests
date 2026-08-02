"""
Wire-level E2E OMEMO tests using slixmpp over ejabberd.

Requires: docker compose -f docker/ejabberd/docker-compose.yml up -d
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Set

import oldmemo
import pytest
from omemo.storage import Just, Maybe, Nothing, Storage
from omemo.types import DeviceInformation, JSONType

from slixmpp.clientxmpp import ClientXMPP
from slixmpp.jid import JID
from slixmpp.plugins import register_plugin
from slixmpp.stanza import Message
from slixmpp.xmlstream.handler import CoroutineCallback
from slixmpp.xmlstream.matcher import MatchXPath

from slixmpp_omemo import TrustLevel, XEP_0384

from omemo_interop.constants import XMPP_HOST, XMPP_PORT
from tests.wire.conftest import skip_no_server

log = logging.getLogger(__name__)


class JsonFileStorage(Storage):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._data: Dict[str, JSONType] = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)

    async def _load(self, key: str) -> Maybe[JSONType]:
        if key in self._data:
            return Just(self._data[key])
        return Nothing()

    async def _store(self, key: str, value: JSONType) -> None:
        self._data[key] = value
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f)

    async def _delete(self, key: str) -> None:
        self._data.pop(key, None)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f)


class WireXEP0384(XEP_0384):
    default_config = {"fallback_message": "OMEMO encrypted.", "json_file_path": None}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.__storage: Storage

    def plugin_init(self) -> None:
        if not self.json_file_path:
            raise RuntimeError("json_file_path required")
        self.__storage = JsonFileStorage(Path(self.json_file_path))
        super().plugin_init()

    @property
    def storage(self) -> Storage:
        return self.__storage

    @property
    def _btbv_enabled(self) -> bool:
        return True

    async def _devices_blindly_trusted(
        self,
        blindly_trusted: FrozenSet[DeviceInformation],
        identifier: Optional[str],
    ) -> None:
        pass

    async def _prompt_manual_trust(
        self,
        manually_trusted: FrozenSet[DeviceInformation],
        identifier: Optional[str],
    ) -> None:
        sm = await self.get_session_manager()
        for device in manually_trusted:
            await sm.set_trust(
                device.bare_jid,
                device.identity_key,
                TrustLevel.TRUSTED.value,
            )


register_plugin(WireXEP0384)


class OmemoWireClient(ClientXMPP):
    def __init__(self, jid: str, password: str, data_path: Path) -> None:
        super().__init__(jid, password)
        self._data_path = data_path
        self._connected = asyncio.Event()
        self._omemo_ready = asyncio.Event()
        self._last_plaintext: Optional[str] = None
        self._receive_event = asyncio.Event()

        self.add_event_handler("session_start", self._on_session_start)
        self.register_handler(CoroutineCallback(
            "WireMessages",
            MatchXPath(f"{{{self.default_ns}}}message"),
            self._on_message,
        ))

    def _register_omemo(self) -> None:
        self.register_plugin("xep_0199")
        self.register_plugin("xep_0380")
        self.register_plugin(
            "xep_0384",
            {"json_file_path": self._data_path},
            module=sys.modules[__name__],
        )

    async def _on_session_start(self, _event: Any) -> None:
        self.send_presence()
        await self.get_roster()
        xep = self["xep_0384"]
        await self.wait_for_event("omemo_initialized")
        self._omemo_ready.set()
        self._connected.set()

    async def _on_message(self, stanza: Message) -> None:
        if stanza["type"] not in {"chat", "normal"}:
            return
        xep: XEP_0384 = self["xep_0384"]
        if not xep.is_encrypted(stanza):
            if stanza["body"]:
                self._last_plaintext = stanza["body"]
                self._receive_event.set()
            return
        try:
            message, _ = await xep.decrypt_message(stanza)
            if message["body"]:
                self._last_plaintext = message["body"]
                self._receive_event.set()
        except Exception:
            log.exception("decrypt failed")

    async def connect_and_wait(self, timeout: float = 60.0) -> None:
        self._register_omemo()
        self.connect((XMPP_HOST, XMPP_PORT))
        await asyncio.wait_for(self._connected.wait(), timeout=timeout)
        await asyncio.wait_for(self._omemo_ready.wait(), timeout=timeout)

    async def send_encrypted(self, recipient: str, body: str, timeout: float = 30.0) -> None:
        xep: XEP_0384 = self["xep_0384"]
        msg = self.make_message(mto=JID(recipient), mtype="chat")
        msg["body"] = body
        encrypted, errors = await xep.encrypt_message(msg, {JID(recipient)})
        if errors:
            raise RuntimeError(f"encryption errors: {errors}")
        if encrypted is None:
            raise RuntimeError("nothing to encrypt")
        encrypted["eme"]["namespace"] = oldmemo.oldmemo.NAMESPACE
        encrypted["eme"]["name"] = self["xep_0380"].mechanisms[oldmemo.oldmemo.NAMESPACE]
        encrypted.send()

    async def wait_for_body(self, expected: str, timeout: float = 30.0) -> None:
        self._receive_event.clear()
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if self._last_plaintext == expected:
                return
            try:
                await asyncio.wait_for(self._receive_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
        raise AssertionError(f"Expected '{expected}', got '{self._last_plaintext}'")

    async def disconnect_clean(self) -> None:
        self.disconnect()


@pytest.mark.wire
@skip_no_server
@pytest.mark.asyncio
async def test_alice_bob_encrypted_roundtrip(tmp_path: Path) -> None:
    """Full wire test: two slixmpp clients exchange OMEMO messages via ejabberd."""
    alice_data = tmp_path / "alice.json"
    bob_data = tmp_path / "bob.json"

    alice = OmemoWireClient("alice@localhost", "alicepass", alice_data)
    bob = OmemoWireClient("bob@localhost", "bobpass", bob_data)

    try:
        await alice.connect_and_wait()
        await bob.connect_and_wait()

        # Allow PEP publication to propagate
        await asyncio.sleep(2)

        await alice.send_encrypted("bob@localhost", "wire-hello-from-alice")
        await bob.wait_for_body("wire-hello-from-alice")

        await bob.send_encrypted("alice@localhost", "wire-reply-from-bob")
        await alice.wait_for_body("wire-reply-from-bob")
    finally:
        await alice.disconnect_clean()
        await bob.disconnect_clean()


@pytest.mark.wire
@skip_no_server
@pytest.mark.asyncio
async def test_cross_namespace_wire_roundtrip(tmp_path: Path) -> None:
    """
    Both clients use dual backends (like Conversations+Monal mixed deployments).
    """
    alice = OmemoWireClient("alice@localhost", "alicepass", tmp_path / "a.json")
    bob = OmemoWireClient("bob@localhost", "bobpass", tmp_path / "b.json")

    try:
        await alice.connect_and_wait()
        await bob.connect_and_wait()
        await asyncio.sleep(2)

        await alice.send_encrypted("bob@localhost", "dual-backend-wire")
        await bob.wait_for_body("dual-backend-wire")
    finally:
        await alice.disconnect_clean()
        await bob.disconnect_clean()
