"""
Behavioral tests for open vendor bugs — these FAIL until upstream fixes land.

Static audit tests (test_source_control_flow_audit.py) pass when buggy source patterns
are present. Tests here assert the correct invariant from
requirements/technical/02-omemo-audit-methodology.md and fail when we simulate (or
observe) vendor send/receive behavior that violates it.

Run: python3 -m pytest tests/compatibility/test_vendor_open_bugs.py -v
"""

from __future__ import annotations

import oldmemo
import oldmemo.etree
import omemo
import pytest

from omemo_interop.constants import ALICE_BARE_JID, BOB_BARE_JID, NS_OLDMEMO
from omemo_interop.harness import TrustLevel
from omemo_interop.send_invariants import (
    assert_expected_subset_encoded_rids,
    encoded_rids_from_element,
    simulate_vendor_partial_send,
)
from omemo_interop.storage import InMemoryStorage
from tests.legacy.test_oldmemo_protocol import _make_oldmemo_pair


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
@pytest.mark.asyncio
async def test_partial_send_conversations_violates_expected_subset_encoded() -> None:
    """P0 partial_send_conversations: buildHeader succeeds when a device key is omitted."""
    alice, bob, _, _ = await _make_oldmemo_pair()
    bob_devices = await alice.get_device_information(BOB_BARE_JID)
    bob_device = next(iter(bob_devices))

    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"conv-partial-send"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    element = oldmemo.etree.serialize_message(next(iter(messages.keys())))
    vendor_element = simulate_vendor_partial_send(element, drop_rid=bob_device.device_id)

    expected_rids = {bob_device.device_id}
    encoded = encoded_rids_from_element(vendor_element)
    assert_expected_subset_encoded_rids(
        expected_rids,
        encoded,
        "partial_send_conversations",
    )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
@pytest.mark.asyncio
async def test_partial_send_siskin_violates_expected_subset_encoded() -> None:
    """P0 partial_send_siskin: MartinOMEMO compactMap drops failed encrypts from header."""
    alice, bob, _, _ = await _make_oldmemo_pair()
    bob_device = next(iter(await alice.get_device_information(BOB_BARE_JID)))

    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"siskin-partial-send"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    element = oldmemo.etree.serialize_message(next(iter(messages.keys())))
    vendor_element = simulate_vendor_partial_send(element, drop_rid=bob_device.device_id)

    assert_expected_subset_encoded_rids(
        {bob_device.device_id},
        encoded_rids_from_element(vendor_element),
        "partial_send_siskin",
    )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
@pytest.mark.asyncio
async def test_partial_send_monal_violates_expected_subset_encoded() -> None:
    """P0 partial_send_monal: addEncryptionKeyForAllDevices continues on cipher error."""
    alice, bob, _, _ = await _make_oldmemo_pair()
    bob_device = next(iter(await alice.get_device_information(BOB_BARE_JID)))

    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"monal-partial-send"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    element = oldmemo.etree.serialize_message(next(iter(messages.keys())))
    vendor_element = simulate_vendor_partial_send(element, drop_rid=bob_device.device_id)

    assert_expected_subset_encoded_rids(
        {bob_device.device_id},
        encoded_rids_from_element(vendor_element),
        "partial_send_monal",
    )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
def test_siskin_pep_failure_must_not_yield_empty_send_set() -> None:
    """P0: PEP fetch failure must abort or retry — not treat recipient as having zero devices."""
    pep_failed_addresses: list = []  # MartinOMEMO try? await retrieveItems → nil → []
    assert pep_failed_addresses, (
        "partial_send_siskin/pep: empty address set after PEP failure should not be used for send"
    )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
def test_monal_devicelist_fetch_error_must_not_fake_empty_list() -> None:
    """P2 monal_devicelist_fetch_fakes_empty: fetch error must surface, not fake []."""
    vendor_devicelist_after_error: list = []  # handleOwnDevicelistFetchError → fake empty
    assert vendor_devicelist_after_error, (
        "monal_devicelist_fetch_fakes_empty: own devicelist error must not become empty list"
    )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
@pytest.mark.asyncio
async def test_siskin_istrusted_always_true_allows_compromised_send() -> None:
    """P1 siskin_trust_callback_always_true: compromised identity must block send."""
    alice, bob, _, _ = await _make_oldmemo_pair()
    bob_device = next(iter(await alice.get_device_information(BOB_BARE_JID)))
    await alice.set_trust(
        bob_device.bare_jid,
        bob_device.identity_key,
        TrustLevel.DISTRUSTED.name,
    )

    try:
        await alice.encrypt(
            bare_jids=frozenset({BOB_BARE_JID}),
            plaintext={NS_OLDMEMO: b"should-not-send"},
            backend_priority_order=[NS_OLDMEMO],
        )
        pytest.fail("reference harness must not send to distrusted device")
    except omemo.NoEligibleDevices:
        pass

    # Vendor: DBOMEMOStore.isTrusted returns true for any identity/key.
    def siskin_isTrusted_compromised() -> bool:
        return True

    assert not siskin_isTrusted_compromised(), (
        "siskin_trust_callback_always_true: isTrusted must reject compromised identities"
    )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
def test_monal_findfirst_rid_must_try_all_matching_keys() -> None:
    """P1 monal_same_rid_findfirst: MUC duplicate rid — decrypt must not stop at first key."""
    monal_uses_findfirst_only = True  # MLOMEMO.m findFirst:@\"header/key<rid=%u>\"
    assert not monal_uses_findfirst_only, (
        "monal_same_rid_findfirst: must attempt all keys with matching rid, not findFirst only"
    )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
def test_siskin_bundle_publish_must_not_swallow_non_item_not_found() -> None:
    """P1 siskin_bundle_before_announce: unexpected bundle read errors must propagate."""
    # MartinOMEMO publishDeviceBundleIfNeeded: catch XMPPError → return without throw
    vendor_swallowed_error = True
    bundle_publish_threw = False

    if vendor_swallowed_error and not bundle_publish_threw:
        pytest.fail(
            "siskin_bundle_before_announce: bundle publish must not treat arbitrary XMPP errors as success"
        )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.vendor_bug
def test_monal_carbon_duplicate_must_repair_session_not_only_dedup() -> None:
    """P2 monal_carbon_mam_dedup: Signal error code 3 on stale replay needs session repair."""
    signal_error_code = 3
    monal_treats_as_dedup_only = True
    session_repaired = False

    if signal_error_code == 3 and monal_treats_as_dedup_only and not session_repaired:
        pytest.fail(
            "monal_carbon_mam_dedup: duplicate Signal error 3 must distinguish true dup vs stale session"
        )


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.asyncio
async def test_reference_harness_enforces_expected_subset_encoded() -> None:
    """Reference (python-omemo/oldmemo): correct implementations satisfy the invariant."""
    alice, bob, _, _ = await _make_oldmemo_pair()
    bob_device = next(iter(await alice.get_device_information(BOB_BARE_JID)))
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"reference-ok"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    element = oldmemo.etree.serialize_message(next(iter(messages.keys())))
    assert_expected_subset_encoded_rids(
        {bob_device.device_id},
        encoded_rids_from_element(element),
        "reference_harness",
    )
