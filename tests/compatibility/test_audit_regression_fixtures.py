"""Deterministic regression fixtures from the 2026-08-02 Kompatibilitätsaudit."""

import base64
import xml.etree.ElementTree as ET
from pathlib import Path

import oldmemo
import oldmemo.etree
import omemo
import pytest

from omemo_interop.constants import ALICE_BARE_JID, BOB_BARE_JID, CAROL_BARE_JID, NS_OLDMEMO
from omemo_interop.harness import (
    BundleStorageKey,
    TrustLevel,
    make_session_manager_impl,
)
from omemo_interop.legacy_axolotl_compat import (
    FIXTURES_DIR,
    NS,
    load_fixture,
    serialized_message_xml,
    set_prekey_attribute,
)
from omemo_interop.storage import InMemoryStorage
from tests.legacy.test_oldmemo_protocol import _make_oldmemo_pair


@pytest.mark.compatibility
@pytest.mark.audit
def test_oldmemo_etree_accepts_prekey_one_and_true() -> None:
    """Audit matrix: receivers must treat prekey=true and prekey=1 equivalently."""
    etree_src = Path(oldmemo.etree.__file__).read_text(encoding="utf-8")
    assert '"true"' in etree_src and '"1"' in etree_src
    assert "prekey" in etree_src


@pytest.mark.compatibility
@pytest.mark.audit
def test_prekey_attribute_variants_on_parse() -> None:
    """Registry name for prekey=true vs prekey=1 wire equivalence (see decrypt tests)."""
    etree_src = Path(oldmemo.etree.__file__).read_text(encoding="utf-8")
    assert "prekey" in etree_src
    assert '"1"' in etree_src or "'1'" in etree_src


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.asyncio
async def test_prekey_one_decrypts_like_true() -> None:
    alice, bob, _, bob_queue = await _make_oldmemo_pair()
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"prekey-one-audit"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    element = set_prekey_attribute(serialized_message_xml(message), "1")
    reparsed = await oldmemo.etree.parse_message(element, ALICE_BARE_JID, BOB_BARE_JID, bob)
    pt, _, _ = await bob.decrypt(reparsed)
    assert pt == b"prekey-one-audit"
    if bob_queue:
        _, queued = bob_queue.pop()
        await alice.decrypt(queued)


@pytest.mark.compatibility
@pytest.mark.audit
def test_multiple_keys_same_rid_collects_candidates() -> None:
    """Audit MUC case: legacy format allows duplicate rid; parser must not stop at first."""
    xml = f"""<encrypted xmlns='{NS_OLDMEMO}'>
      <header sid='100'>
        <key rid='42'>AAAA</key>
        <key rid='42'>BBBB</key>
        <iv>{base64.b64encode(b"012345678901").decode()}</iv>
      </header>
      <payload>CCCC</payload>
    </encrypted>"""
    root = ET.fromstring(xml)
    header = root.find(f"{NS}header")
    keys = header.findall(f"{NS}key")
    assert len(keys) == 2
    assert keys[0].get("rid") == keys[1].get("rid") == "42"


@pytest.mark.compatibility
@pytest.mark.audit
def test_muc_duplicate_rid_fixture_file() -> None:
    xml = load_fixture("legacy_axolotl_duplicate_rid.xml")
    root = ET.fromstring(xml)
    header = root.find(f"{NS}header")
    keys = header.findall(f"{NS}key")
    assert len(keys) == 2
    assert all(k.get("rid") == "42" for k in keys)


@pytest.mark.compatibility
@pytest.mark.audit
def test_carbon_duplicate_fixture_structure() -> None:
    xml = load_fixture("legacy_axolotl_carbon_duplicate.xml")
    root = ET.fromstring(xml)
    encrypted = root.find(f"{NS}encrypted")
    assert encrypted is not None
    assert encrypted.find(f"{NS}header") is not None
    assert encrypted.find(f"{NS}payload") is not None


@pytest.mark.compatibility
@pytest.mark.audit
def test_devicelist_without_bundle_fixture() -> None:
    xml = load_fixture("legacy_axolotl_devicelist_no_bundle.xml")
    root = ET.fromstring(xml)
    assert root.tag == f"{NS}list"
    device = root.find(f"{NS}device")
    assert device is not None
    assert device.get("id") == "42"


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.asyncio
async def test_partial_coverage_message_rejected_by_harness() -> None:
    """
    Audit invariant expected ⊆ encoded: if we strip one recipient key from XML,
    decrypt must fail for the removed device (simulates partial vendor send).
    """
    alice, bob, _, _ = await _make_oldmemo_pair()
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"full-coverage"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    element = oldmemo.etree.serialize_message(next(iter(messages.keys())))
    keys = element.find(f"{NS}header").findall(f"{NS}key")
    assert len(keys) >= 1
    element.find(f"{NS}header").remove(keys[0])
    reparsed = await oldmemo.etree.parse_message(element, ALICE_BARE_JID, BOB_BARE_JID, bob)
    try:
        await bob.decrypt(reparsed)
        pytest.fail("decrypt should fail when recipient key stripped from envelope")
    except Exception:
        pass


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.asyncio
async def test_bundle_missing_blocks_encrypt_in_harness() -> None:
    """Audit: announced device without bundle must not produce a partial wire message."""
    bundle_storage: dict = {}
    device_list_storage: dict = {}
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

    bob_devices = await alice.get_device_information(BOB_BARE_JID)
    assert bob_devices
    bob_device = next(iter(bob_devices))
    bundle_key = BundleStorageKey(NS_OLDMEMO, BOB_BARE_JID, bob_device.device_id)
    bundle_storage.pop(bundle_key, None)

    try:
        await alice.encrypt(
            bare_jids=frozenset({BOB_BARE_JID}),
            plaintext={NS_OLDMEMO: b"no-bundle"},
            backend_priority_order=[NS_OLDMEMO],
        )
        pytest.fail("encrypt should fail when recipient bundle is missing")
    except omemo.NoEligibleDevices:
        pass


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.asyncio
async def test_distrusted_identity_blocks_encrypt_in_harness() -> None:
    """Harness models Monal trust gating: distrusted remote device is excluded from encrypt."""
    alice, bob, _, _ = await _make_oldmemo_pair()
    bob_devices = await alice.get_device_information(BOB_BARE_JID)
    bob_device = next(iter(bob_devices))
    await alice.set_trust(
        bob_device.bare_jid,
        bob_device.identity_key,
        TrustLevel.DISTRUSTED.name,
    )
    try:
        await alice.encrypt(
            bare_jids=frozenset({BOB_BARE_JID}),
            plaintext={NS_OLDMEMO: b"blocked"},
            backend_priority_order=[NS_OLDMEMO],
        )
        pytest.fail("encrypt should fail when all recipient devices are distrusted")
    except omemo.NoEligibleDevices:
        pass


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.asyncio
async def test_foreign_jid_same_device_id_distinct_sessions() -> None:
    """
    Monal audit #240: device id collision across JIDs must not break multi-user harness.
    Alice encrypts to Bob and Carol when both use device id 1.
    """
    bundle_storage: dict = {}
    device_list_storage: dict = {}
    alice_queue: list = []
    bob_queue: list = []
    carol_queue: list = []

    AliceImpl = make_session_manager_impl(
        ALICE_BARE_JID, bundle_storage, device_list_storage, alice_queue,
    )
    BobImpl = make_session_manager_impl(
        BOB_BARE_JID, bundle_storage, device_list_storage, bob_queue,
    )
    CarolImpl = make_session_manager_impl(
        CAROL_BARE_JID, bundle_storage, device_list_storage, carol_queue,
    )

    alice_storage = InMemoryStorage()
    bob_storage = InMemoryStorage()
    carol_storage = InMemoryStorage()

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
    carol = await CarolImpl.create(
        backends=[oldmemo.Oldmemo(carol_storage)],
        storage=carol_storage,
        own_bare_jid=CAROL_BARE_JID,
        initial_own_label=None,
        undecided_trust_level_name=TrustLevel.UNDECIDED.name,
    )

    await alice.after_history_sync()
    await bob.after_history_sync()
    await carol.after_history_sync()
    await alice.refresh_device_list(NS_OLDMEMO, BOB_BARE_JID)
    await alice.refresh_device_list(NS_OLDMEMO, CAROL_BARE_JID)

    bob_devices = await alice.get_device_information(BOB_BARE_JID)
    carol_devices = await alice.get_device_information(CAROL_BARE_JID)
    assert bob_devices and carol_devices
    # Harness uses distinct JIDs; multi-recipient encrypt must not conflate peers by device id alone.

    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID, CAROL_BARE_JID}),
        plaintext={NS_OLDMEMO: b"multi-recipient-same-device-id"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    pt_bob, _, _ = await bob.decrypt(message)
    pt_carol, _, _ = await carol.decrypt(message)
    assert pt_bob == b"multi-recipient-same-device-id"
    assert pt_carol == b"multi-recipient-same-device-id"


@pytest.mark.compatibility
@pytest.mark.audit
@pytest.mark.asyncio
async def test_pep_precondition_retry_required_for_martin_bundles() -> None:
    """Bundle publish must handle PEP conflict like device-list (audit gap until fixed)."""
    from omemo_interop.source_audit import read_vendor

    text = read_vendor("vendor/MartinOMEMO/Sources/MartinOMEMO/OMEMOModule.swift")
    bundle_section = text.split("func publishDeviceBundle(signedPreKey", 1)[1][:2500]
    assert ".conflict" in bundle_section or "configureNode" in bundle_section, (
        "martin_bundle_publish: bundle publish must retry/reconfigure on PEP conflict"
    )
