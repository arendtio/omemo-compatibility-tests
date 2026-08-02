"""Multi-device OMEMO fan-out compatibility."""

import pytest
import twomemo
import oldmemo

from omemo_interop.constants import ALICE_BARE_JID, BOB_BARE_JID, NS_OLDMEMO, NS_TWOMEMO
from omemo_interop.harness import (
    BundleStorage,
    DeviceListStorage,
    TrustLevel,
    make_session_manager_impl,
)
from omemo_interop.storage import InMemoryStorage


@pytest.mark.asyncio
async def test_bob_two_devices_both_receive_twomemo() -> None:
    """Encrypting for a contact with two devices must deliver to both (twomemo)."""
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
    bob_storage1 = InMemoryStorage()
    bob_storage2 = InMemoryStorage()

    alice = await AliceImpl.create(
        backends=[twomemo.Twomemo(alice_storage)],
        storage=alice_storage,
        own_bare_jid=ALICE_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )

    bob1 = await BobImpl.create(
        backends=[twomemo.Twomemo(bob_storage1)],
        storage=bob_storage1,
        own_bare_jid=BOB_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )

    BobImpl2 = make_session_manager_impl(
        BOB_BARE_JID, bundle_storage, device_list_storage, bob_queue,
    )
    bob2 = await BobImpl2.create(
        backends=[twomemo.Twomemo(bob_storage2)],
        storage=bob_storage2,
        own_bare_jid=BOB_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )

    await alice.after_history_sync()
    await bob1.after_history_sync()
    await bob2.after_history_sync()

    await alice.refresh_device_list(NS_TWOMEMO, BOB_BARE_JID)

    bob_devices = await alice.get_device_information(BOB_BARE_JID)
    twomemo_devices = [d for d in bob_devices if NS_TWOMEMO in d.namespaces]
    assert len(twomemo_devices) >= 2

    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_TWOMEMO: b"multi-device"},
        backend_priority_order=[NS_TWOMEMO],
    )
    assert len(errors) == 0
    assert len(messages) >= 1

    message = next(iter(messages.keys()))
    pt1, _, _ = await bob1.decrypt(message)
    pt2, _, _ = await bob2.decrypt(message)
    assert pt1 == b"multi-device"
    assert pt2 == b"multi-device"


@pytest.mark.asyncio
async def test_dual_backend_recipient_accepts_both_namespaces() -> None:
    """Single dual-backend recipient (like slixmpp-omemo) decrypts twomemo and oldmemo."""
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

    alice = await AliceImpl.create(
        backends=[twomemo.Twomemo(alice_storage), oldmemo.Oldmemo(alice_storage)],
        storage=alice_storage,
        own_bare_jid=ALICE_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )

    bob = await BobImpl.create(
        backends=[twomemo.Twomemo(bob_storage), oldmemo.Oldmemo(bob_storage)],
        storage=bob_storage,
        own_bare_jid=BOB_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )

    await alice.after_history_sync()
    await bob.after_history_sync()

    for ns in (NS_TWOMEMO, NS_OLDMEMO):
        await alice.refresh_device_list(ns, BOB_BARE_JID)
        await bob.refresh_device_list(ns, ALICE_BARE_JID)

    for ns in (NS_TWOMEMO, NS_OLDMEMO):
        messages, errors = await alice.encrypt(
            bare_jids=frozenset({BOB_BARE_JID}),
            plaintext={ns: f"ns-{ns}".encode()},
            backend_priority_order=[ns],
        )
        assert not errors
        message = next(iter(messages.keys()))
        plaintext, _, _ = await bob.decrypt(message)
        assert plaintext == f"ns-{ns}".encode()
