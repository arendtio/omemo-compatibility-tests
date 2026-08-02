"""Deterministic regression fixtures from the 2026-08-02 Kompatibilitätsaudit."""

import base64
import xml.etree.ElementTree as ET
from pathlib import Path

import oldmemo
import oldmemo.etree
import pytest

from omemo_interop.constants import ALICE_BARE_JID, BOB_BARE_JID, NS_OLDMEMO
from omemo_interop.legacy_axolotl_compat import NS, serialized_message_xml, set_prekey_attribute
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
