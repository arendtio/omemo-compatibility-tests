"""XEP-0384 structural conformance tests."""

import xml.etree.ElementTree as ET

import pytest
import twomemo
import oldmemo

from omemo_interop.constants import ALICE_BARE_JID, BOB_BARE_JID, NS_OLDMEMO, NS_TWOMEMO
from omemo_interop.harness import BundleStorage, DeviceListStorage, TrustLevel, make_session_manager_impl
from omemo_interop.storage import InMemoryStorage
from omemo_interop.xep0384 import (
    FINGERPRINT_HEX_RE,
    OLDMEMO_DEVICE_LIST_NODE,
    TWOMEMO_DEVICE_LIST_NODE,
    fingerprint_is_valid_hex,
    format_fingerprint_for_display,
)


@pytest.mark.asyncio
async def test_namespace_uris_match_xep0384() -> None:
    assert NS_TWOMEMO == "urn:xmpp:omemo:2"
    assert NS_OLDMEMO == "eu.siacs.conversations.axolotl"


@pytest.mark.asyncio
async def test_device_list_pep_node_names() -> None:
    assert OLDMEMO_DEVICE_LIST_NODE.startswith("eu.siacs.conversations.axolotl")
    assert TWOMEMO_DEVICE_LIST_NODE.startswith("urn:xmpp:omemo:2")


@pytest.mark.asyncio
async def test_identity_key_fingerprint_format() -> None:
    bundle_storage: BundleStorage = {}
    device_list_storage: DeviceListStorage = {}
    queue: list = []

    Impl = make_session_manager_impl(
        ALICE_BARE_JID, bundle_storage, device_list_storage, queue,
    )
    storage = InMemoryStorage()
    sm = await Impl.create(
        backends=[twomemo.Twomemo(storage)],
        storage=storage,
        own_bare_jid=ALICE_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )
    await sm.after_history_sync()

    device, _ = await sm.get_own_device_information()
    identity_bytes = device.identity_key
    assert len(identity_bytes) == 32
    assert fingerprint_is_valid_hex(identity_bytes)

    formatted = format_fingerprint_for_display(identity_bytes)
    parts = formatted.split(" ")
    assert len(parts) == 8
    assert all(len(p) == 8 for p in parts)
    assert FINGERPRINT_HEX_RE.match(identity_bytes.hex())


@pytest.mark.asyncio
async def test_serialized_twomemo_message_contains_namespace() -> None:
    """Encrypted messages must carry the OMEMO namespace on the wire."""
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

    storage = InMemoryStorage()
    alice = await AliceImpl.create(
        backends=[twomemo.Twomemo(storage)],
        storage=storage,
        own_bare_jid=ALICE_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )
    bob_storage = InMemoryStorage()
    bob = await BobImpl.create(
        backends=[twomemo.Twomemo(bob_storage)],
        storage=bob_storage,
        own_bare_jid=BOB_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )
    await alice.after_history_sync()
    await bob.after_history_sync()
    await alice.refresh_device_list(NS_TWOMEMO, BOB_BARE_JID)

    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_TWOMEMO: b"conformance"},
        backend_priority_order=[NS_TWOMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    xml = twomemo.etree.serialize_message(message)
    assert NS_TWOMEMO in ET.tostring(xml, encoding="unicode")


@pytest.mark.asyncio
async def test_serialized_oldmemo_message_contains_namespace() -> None:
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
    alice = await AliceImpl.create(
        backends=[oldmemo.Oldmemo(alice_storage)],
        storage=alice_storage,
        own_bare_jid=ALICE_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )
    bob_storage = InMemoryStorage()
    bob = await BobImpl.create(
        backends=[oldmemo.Oldmemo(bob_storage)],
        storage=bob_storage,
        own_bare_jid=BOB_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )
    await alice.after_history_sync()
    await bob.after_history_sync()
    await alice.refresh_device_list(NS_OLDMEMO, BOB_BARE_JID)

    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"conformance"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    xml = oldmemo.etree.serialize_message(message)
    assert NS_OLDMEMO in ET.tostring(xml, encoding="unicode")
