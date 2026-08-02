"""Cross-backend tests: oldmemo (Conversations) vs twomemo (Monal/Dino)."""

import xml.etree.ElementTree as ET
from typing import Callable, List, Optional

import oldmemo
import oldmemo.etree
import omemo
import pytest
import twomemo
import twomemo.etree

from omemo_interop.constants import ALICE_BARE_JID, BOB_BARE_JID, NS_OLDMEMO, NS_TWOMEMO
from omemo_interop.harness import (
    BundleStorage,
    DeviceListStorage,
    TrustLevel,
    make_session_manager_impl,
)
from omemo_interop.storage import InMemoryStorage

BackendFactory = Callable[[omemo.Storage], omemo.Backend]


async def _make_pair(
    alice_factories: List[BackendFactory],
    bob_factories: List[BackendFactory],
) -> tuple:
    bundle_storage: BundleStorage = {}
    device_list_storage: DeviceListStorage = {}
    alice_queue: list = []
    bob_queue: list = []

    AliceImpl = make_session_manager_impl(
        ALICE_BARE_JID, bundle_storage, device_list_storage, alice_queue,
    )
    BobImpl = make_session_manager_impl(
        BOB_BARE_JID, bundle_storage, device_list_storage, bob_queue,
    )

    alice_storage = InMemoryStorage()
    bob_storage = InMemoryStorage()

    alice_backends = [factory(alice_storage) for factory in alice_factories]
    bob_backends = [factory(bob_storage) for factory in bob_factories]

    alice = await AliceImpl.create(
        backends=alice_backends,
        storage=alice_storage,
        own_bare_jid=ALICE_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )
    bob = await BobImpl.create(
        backends=bob_backends,
        storage=bob_storage,
        own_bare_jid=BOB_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )

    await alice.after_history_sync()
    await bob.after_history_sync()

    alice_ns = {backend.namespace for backend in alice_backends}
    bob_ns = {backend.namespace for backend in bob_backends}
    for ns in alice_ns | bob_ns:
        if ns in alice_ns:
            await alice.refresh_device_list(ns, BOB_BARE_JID)
        if ns in bob_ns:
            await bob.refresh_device_list(ns, ALICE_BARE_JID)

    return alice, bob, alice_queue, bob_queue


async def _complete_session_handshake(
    sender,
    recipient,
    recipient_queue: list,
    peer_bare_jid: str,
    namespace: str,
    plaintext: bytes,
) -> None:
    messages, errors = await sender.encrypt(
        bare_jids=frozenset({peer_bare_jid}),
        plaintext={namespace: plaintext},
        backend_priority_order=[namespace],
    )
    assert len(errors) == 0
    assert len(messages) == 1

    message = next(iter(messages.keys()))
    decrypted, _, _ = await recipient.decrypt(message)
    assert decrypted == plaintext

    if recipient_queue:
        _, queued = recipient_queue.pop()
        await sender.decrypt(queued)


@pytest.mark.asyncio
async def test_twomemo_to_oldmemo_when_sender_has_both_backends() -> None:
    """
    Modern sender (dual backend) reaches legacy-only recipient via oldmemo namespace.
    Pure twomemo-only -> oldmemo-only is not wire compatible; clients must negotiate namespace.
    """
    alice, bob, _, bob_queue = await _make_pair(
        [lambda s: twomemo.Twomemo(s), lambda s: oldmemo.Oldmemo(s)],
        [lambda s: oldmemo.Oldmemo(s)],
    )
    await _complete_session_handshake(
        alice, bob, bob_queue, BOB_BARE_JID, NS_OLDMEMO, b"dual sender to legacy",
    )


@pytest.mark.asyncio
async def test_oldmemo_to_twomemo_when_recipient_has_both_backends() -> None:
    """Legacy sender reaches modern dual-backend recipient."""
    alice, bob, _, bob_queue = await _make_pair(
        [lambda s: oldmemo.Oldmemo(s)],
        [lambda s: twomemo.Twomemo(s), lambda s: oldmemo.Oldmemo(s)],
    )
    await _complete_session_handshake(
        alice, bob, bob_queue, BOB_BARE_JID, NS_OLDMEMO, b"legacy to dual recipient",
    )


@pytest.mark.asyncio
async def test_dual_backend_bidirectional() -> None:
    """Both parties load both backends like slixmpp-omemo / modern multi-backend clients."""
    factories = [lambda s: twomemo.Twomemo(s), lambda s: oldmemo.Oldmemo(s)]
    alice, bob, alice_queue, bob_queue = await _make_pair(factories, factories)

    for ns in (NS_TWOMEMO, NS_OLDMEMO):
        await _complete_session_handshake(
            alice, bob, bob_queue, BOB_BARE_JID, ns, f"roundtrip-{ns}".encode(),
        )
        await _complete_session_handshake(
            bob, alice, alice_queue, ALICE_BARE_JID, ns, f"reply-{ns}".encode(),
        )


@pytest.mark.asyncio
async def test_key_transport_without_payload() -> None:
    """
    Key transport messages (no payload) must not break subsequent messaging.
    Regression for Libervia JET / Monal self-healing scenarios.
    """
    factories = [lambda s: twomemo.Twomemo(s), lambda s: oldmemo.Oldmemo(s)]
    alice, bob, _, bob_queue = await _make_pair(factories, factories)

    for namespace in (NS_TWOMEMO, NS_OLDMEMO):
        messages, errors = await alice.encrypt(
            bare_jids=frozenset({BOB_BARE_JID}),
            plaintext={namespace: b"\x00" * 32},
            backend_priority_order=[namespace],
        )
        assert len(errors) == 0
        message = next(iter(messages.keys()))

        encrypted_elt: Optional[ET.Element] = None
        if namespace == NS_TWOMEMO:
            encrypted_elt = twomemo.etree.serialize_message(message)
        else:
            encrypted_elt = oldmemo.etree.serialize_message(message)

        for payload_elt in encrypted_elt.findall(f"{{{namespace}}}payload"):
            encrypted_elt.remove(payload_elt)

        if namespace == NS_TWOMEMO:
            message = twomemo.etree.parse_message(encrypted_elt, ALICE_BARE_JID)
        else:
            message = await oldmemo.etree.parse_message(
                encrypted_elt, ALICE_BARE_JID, BOB_BARE_JID, bob,
            )

        plaintext, _, _ = await bob.decrypt(message)
        assert plaintext is None

        await _complete_session_handshake(
            alice, bob, bob_queue, BOB_BARE_JID, namespace, b"after-key-transport",
        )
