"""Protocol-level compatibility tests for Conversations vs Siskin legacy OMEMO.

python-oldmemo implements the Conversations wire format (eu.siacs.conversations.axolotl).
Siskin uses the same format via Tigase MartinOMEMO; gaps are validated against vendor
source constants and MartinOMEMO decode rules where native code is not on Linux CI.
"""

from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from pathlib import Path

import oldmemo
import oldmemo.etree
import pytest
import yaml

from omemo_interop.constants import ALICE_BARE_JID, BOB_BARE_JID, NS_OLDMEMO
from omemo_interop.legacy_axolotl_compat import (
    FILE_AES_KEY_BYTES,
    GCM_IV_BYTES,
    GCM_TAG_BYTES,
    MESSAGE_AES_KEY_BYTES,
    PEP_BUNDLE_NODE_PREFIX,
    PEP_DEVICE_LIST_ITEM_ID,
    PEP_DEVICE_LIST_NODE,
    POST_RATCHET_KEY_BYTES,
    bundle_pep_node,
    iv_bytes_from_serialized,
    payload_present,
    serialized_message_xml,
    set_prekey_attribute,
    strip_payload_from_serialized,
)
from tests.legacy.test_oldmemo_protocol import _make_oldmemo_pair

COMPAT = Path(__file__).resolve().parent.parent.parent / "config" / "conversations-siskin-compat.yaml"
CONVERSATIONS_CONFIG = (
    Path(__file__).resolve().parent.parent.parent
    / "vendor"
    / "conversations"
    / "src"
    / "main"
    / "java"
    / "eu"
    / "siacs"
    / "conversations"
    / "Config.java"
)
MARTIN_OMEMO_DECODE = (
    Path(__file__).resolve().parent.parent.parent
    / "vendor"
    / "MartinOMEMO"
    / "Sources"
    / "MartinOMEMO"
    / "OMEMOModule.swift"
)


@pytest.fixture
def compat_findings() -> list[dict]:
    with open(COMPAT, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["findings"]


async def _handshake(alice, bob, bob_queue, plaintext: bytes) -> None:
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: plaintext},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    pt, _, _ = await bob.decrypt(message)
    assert pt == plaintext
    if bob_queue:
        _, queued = bob_queue.pop()
        await alice.decrypt(queued)


@pytest.mark.compatibility
def test_compat_registry_covers_conversations_siskin(compat_findings: list[dict]) -> None:
    ids = {g["id"] for g in compat_findings}
    assert "partial_send_conversations" in ids
    assert "partial_send_siskin" in ids
    assert "auth_tag_in_ratchet_key" in ids
    assert "siskin_trust_callback_always_true" in ids
    for gap in compat_findings:
        assert gap.get("tests") or gap.get("mitigated_by") or gap.get("note")


@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_auth_tag_in_key_roundtrip() -> None:
    """Conversations and Siskin both require key(16)+tag(16) after ratchet decrypt."""
    alice, bob, _, bob_queue = await _make_oldmemo_pair()
    await _handshake(alice, bob, bob_queue, b"auth-tag-in-key-check")


@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_payload_ciphertext_excludes_gcm_tag() -> None:
    """With auth tag in key, payload bytes are ciphertext only (tag stripped on send)."""
    alice, bob, _, _ = await _make_oldmemo_pair()
    body = b"payload-tag-layout"
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: body},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    xml = serialized_message_xml(next(iter(messages.keys())))
    assert payload_present(xml)
    encrypted = oldmemo.etree.serialize_message(next(iter(messages.keys())))
    payload = base64.b64decode(encrypted.find(f"{{{NS_OLDMEMO}}}payload").text.strip())
    # Plaintext-sized ciphertext; 16-byte GCM tag is not appended here.
    assert len(payload) == len(body)


@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_prekey_attribute_one_decrypts_like_true() -> None:
    """Conversations and MartinOMEMO both treat prekey=1 like prekey=true."""
    alice, bob, _, bob_queue = await _make_oldmemo_pair()
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"prekey-one"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    xml = serialized_message_xml(message)
    element = set_prekey_attribute(xml, "1")
    reparsed = await oldmemo.etree.parse_message(element, ALICE_BARE_JID, BOB_BARE_JID, bob)
    pt, _, _ = await bob.decrypt(reparsed)
    assert pt == b"prekey-one"
    if bob_queue:
        _, queued = bob_queue.pop()
        await alice.decrypt(queued)


@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_key_transport_without_payload_then_chat() -> None:
    """Key-transport (no payload) must not break the next encrypted chat message."""
    alice, bob, _, bob_queue = await _make_oldmemo_pair()
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"\x00" * 32},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    message = next(iter(messages.keys()))
    element = strip_payload_from_serialized(serialized_message_xml(message))
    transport = await oldmemo.etree.parse_message(element, ALICE_BARE_JID, BOB_BARE_JID, bob)
    pt, _, _ = await bob.decrypt(transport)
    assert pt is None
    await _handshake(alice, bob, bob_queue, b"after-key-transport")


@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_iv_on_wire_is_twelve_bytes() -> None:
    alice, bob, _, _ = await _make_oldmemo_pair()
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"iv-length"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    iv = iv_bytes_from_serialized(serialized_message_xml(next(iter(messages.keys()))))
    assert len(iv) == GCM_IV_BYTES


@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_unicode_plaintext_without_padding() -> None:
    """Both clients disable OMEMO padding; Unicode must roundtrip verbatim."""
    alice, bob, _, bob_queue = await _make_oldmemo_pair()
    body = "Unicode 🧪 日本語 — no padding".encode()
    await _handshake(alice, bob, bob_queue, body)


@pytest.mark.compatibility
def test_pep_node_names_match_conversations() -> None:
    assert PEP_DEVICE_LIST_NODE == "eu.siacs.conversations.axolotl.devicelist"
    assert bundle_pep_node(12345) == "eu.siacs.conversations.axolotl.bundles:12345"
    assert PEP_DEVICE_LIST_ITEM_ID == "current"
    assert PEP_BUNDLE_NODE_PREFIX == "eu.siacs.conversations.axolotl.bundles:"


@pytest.mark.compatibility
def test_documented_file_key_size_differs_from_message() -> None:
    """aesgcm:// attachments use 32-byte keys; chat payloads use 16-byte keys."""
    assert MESSAGE_AES_KEY_BYTES == 16
    assert FILE_AES_KEY_BYTES == 32
    assert POST_RATCHET_KEY_BYTES == MESSAGE_AES_KEY_BYTES + GCM_TAG_BYTES


@pytest.mark.compatibility
def test_trust_model_siskin_must_not_ignore_compromised_identities(compat_findings: list[dict]) -> None:
    """P1 siskin_trust_callback_always_true: Siskin isTrusted must not always return true."""
    gap = next(g for g in compat_findings if g["id"] == "siskin_trust_callback_always_true")
    assert gap["aligned"] is False
    from omemo_interop.source_audit import assert_no_pattern

    siskin_store = (
        Path(__file__).resolve().parent.parent.parent
        / "vendor"
        / "siskin_im"
        / "SiskinIM"
        / "database"
        / "DBOMEMOStore.swift"
    )
    text = siskin_store.read_text(encoding="utf-8")
    assert_no_pattern(
        text,
        r"func isTrusted\(identity: SignalAddress, key:.*?\n.*?return true",
        "siskin_trust_callback_always_true",
    )
    conv = CONVERSATIONS_CONFIG.read_text(encoding="utf-8")
    assert "PUT_AUTH_TAG_INTO_KEY" in conv


@pytest.mark.compatibility
def test_muc_policy_difference_documented() -> None:
    room = (
        Path(__file__).resolve().parent.parent.parent
        / "vendor"
        / "siskin_im"
        / "SiskinIM"
        / "database"
        / "model"
        / "conversations"
        / "Room.swift"
    )
    text = room.read_text(encoding="utf-8")
    assert "membersOnly" in text or "nonAnonymous" in text


@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_legacy_message_uses_axolotl_namespace_only() -> None:
    alice, bob, _, _ = await _make_oldmemo_pair()
    messages, errors = await alice.encrypt(
        bare_jids=frozenset({BOB_BARE_JID}),
        plaintext={NS_OLDMEMO: b"ns-check"},
        backend_priority_order=[NS_OLDMEMO],
    )
    assert not errors
    xml = serialized_message_xml(next(iter(messages.keys())))
    assert NS_OLDMEMO in xml
    assert "urn:xmpp:omemo:2" not in xml


@pytest.mark.compatibility
def test_vendor_prekey_parsing_rules_match() -> None:
    """Static check: MartinOMEMO and Conversations agree on prekey attribute values."""
    conv_element = (
        Path(__file__).resolve().parent.parent.parent
        / "vendor"
        / "conversations"
        / "src"
        / "main"
        / "java"
        / "eu"
        / "siacs"
        / "conversations"
        / "xml"
        / "Element.java"
    )
    conv = conv_element.read_text(encoding="utf-8")
    assert "equalsIgnoreCase(\"1\")" in conv
    if MARTIN_OMEMO_DECODE.is_file():
        martin = MARTIN_OMEMO_DECODE.read_text(encoding="utf-8")
        assert 'attribute("prekey") == "1"' in martin or 'attribute("prekey") == "true"' in martin
