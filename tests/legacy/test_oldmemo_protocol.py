"""Legacy OMEMO protocol tests (in-memory, no network)."""

import pytest
import oldmemo

from omemo_interop.constants import ALICE_BARE_JID, BOB_BARE_JID, NS_OLDMEMO
from omemo_interop.harness import (
    BundleStorage,
    DeviceListStorage,
    TrustLevel,
    make_session_manager_impl,
)
from omemo_interop.storage import InMemoryStorage


async def _make_oldmemo_pair() -> tuple:
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
        backends=[oldmemo.Oldmemo(alice_storage)],
        storage=alice_storage,
        own_bare_jid=ALICE_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )
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
    await bob.refresh_device_list(NS_OLDMEMO, ALICE_BARE_JID)

    return alice, bob, alice_queue, bob_queue


@pytest.mark.asyncio
async def test_oldmemo_bidirectional() -> None:
    alice, bob, alice_queue, bob_queue = await _make_oldmemo_pair()

    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"legacy-hello"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    pt, _, _ = await bob.decrypt(message)
    assert pt == b"legacy-hello"

    if bob_queue:
        _, queued = bob_queue.pop()
        await alice.decrypt(queued)

    messages, errors = await bob.encrypt(
        bare_jids=frozenset({ALICE_BARE_JID}),
        plaintext={NS_OLDMEMO: b"legacy-reply"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    pt, _, _ = await alice.decrypt(message)
    assert pt == b"legacy-reply"
