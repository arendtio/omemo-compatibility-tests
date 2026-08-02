"""Static re-check of vendor control-flow patterns from the 2026-08-02 audit."""

from pathlib import Path

import pytest
import yaml

from omemo_interop.source_audit import assert_pattern, git_rev, read_vendor, vendor_path

PINS = Path(__file__).resolve().parent.parent.parent / "config" / "audit-source-pins.yaml"
COMPAT = Path(__file__).resolve().parent.parent.parent / "config" / "conversations-siskin-compat.yaml"

def _martin_omemo_text() -> str:
    return read_vendor("vendor/MartinOMEMO/Sources/MartinOMEMO/OMEMOModule.swift")


@pytest.fixture
def audit_pins() -> dict:
    with open(PINS, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def compat_findings() -> list[dict]:
    with open(COMPAT, encoding="utf-8") as f:
        return yaml.safe_load(f)["findings"]


@pytest.mark.compatibility
@pytest.mark.audit
def test_vendored_conversations_commit_matches_audit_pin(audit_pins: dict) -> None:
    pin = audit_pins["audits"]["conversations_siskin_monal_2026-08-02"]["clients"]["conversations"]["commit"]
    rev = git_rev("vendor/conversations")
    if rev:
        assert rev.startswith(pin[:8])


@pytest.mark.compatibility
@pytest.mark.audit
def test_conversations_partial_send_pattern_documented() -> None:
    """P0: buildHeader calls addDevice without checking processSending null."""
    axolotl = read_vendor(
        "vendor/conversations/src/main/java/eu/siacs/conversations/crypto/axolotl/AxolotlService.java"
    )
    msg = read_vendor(
        "vendor/conversations/src/main/java/eu/siacs/conversations/crypto/axolotl/XmppAxolotlMessage.java"
    )
    assert_pattern(axolotl, r"axolotlMessage\.addDevice\(session\)", "buildHeader addDevice call")
    assert_pattern(msg, r"void addDevice\(XmppAxolotlSession session", "addDevice is void")
    assert_pattern(msg, r"if \(key != null\)\s*\{\s*keys\.add\(key\)", "null key silently skipped")


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_partial_send_pattern_documented() -> None:
    """P0: MartinOMEMO drops failed session ciphers from header via compactMap nil."""
    text = _martin_omemo_text()
    assert_pattern(text, r"destinations\.compactMap\(\{ addr -> SignalSessionCipher\.Key\?", "compactMap encrypt per device")
    assert_pattern(text, r"catch \{\s*self\.logger\.error", "encrypt catch logs error")
    assert_pattern(text, r"return nil;\s*\}\s*\}\)\.compactMap", "encrypt catch returns nil before header compactMap")
    assert_pattern(text, r"\.compactMap\(\{ \(key: SignalSessionCipher\.Key\) -> Element\?", "nil keys omitted from header")


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_pep_failure_swallowed_pattern() -> None:
    """P0: addresses(for:) uses try? on PEP fetch; failure yields empty device set."""
    text = _martin_omemo_text()
    assert_pattern(
        text,
        r"try\? await pubsubModule\.retrieveItems\(from: jid, for: OMEMOModule\.DEVICES_LIST_NODE",
        "try? device-list retrieveItems",
    )
    assert_pattern(text, r"else \{\s*return \[\];", "empty addresses on missing/invalid list")


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_bundle_publish_error_handling() -> None:
    """P1: unexpected bundle read errors are swallowed (return without throw)."""
    text = _martin_omemo_text()
    assert_pattern(
        text,
        r"publishDeviceBundleIfNeeded.*?catch let error as XMPPError",
        "publishDeviceBundleIfNeeded XMPPError catch",
    )
    assert_pattern(
        text,
        r"guard error\.condition == \.item_not_found \|\| error\.condition == \.internal_server_error else \{\s*return;",
        "non-item_not_found errors return without throw",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_istrusted_always_true() -> None:
    text = read_vendor("vendor/siskin_im/SiskinIM/database/DBOMEMOStore.swift")
    assert_pattern(text, r"func isTrusted\(identity: SignalAddress, key:.*?\n.*?return true", "isTrusted key")
    assert_pattern(text, r"func isTrusted\(identity: SignalAddress, publicKeyData:.*?\n.*?return true", "isTrusted data")


@pytest.mark.compatibility
@pytest.mark.audit
def test_martin_device_list_precondition_retry() -> None:
    """Device-list publish reconfigures node on conflict (audit recommended for bundles too)."""
    text = _martin_omemo_text()
    assert_pattern(text, r"error\.condition == \.conflict", "device list conflict branch")
    assert_pattern(text, r"configureNode\(at: jid, node: OMEMOModule\.DEVICES_LIST_NODE", "reconfigure device list")


@pytest.mark.compatibility
@pytest.mark.audit
def test_martin_bundle_publish_lacks_precondition_retry() -> None:
    """Audit gap: bundle publish has open access but no conflict/precondition retry loop."""
    text = _martin_omemo_text()
    assert_pattern(text, r"func publishDeviceBundle\(signedPreKey", "bundle publish exists")
    assert_pattern(
        text,
        r"publishItem\(at: nil, to: bundleNode",
        "bundle publishItem",
    )
    # Device list has conflict handling; bundle publish does not reference conflict.
    assert "bundleNode" in text and ".conflict" in text
    bundle_section = text.split("func publishDeviceBundle(signedPreKey", 1)[1][:2000]
    assert ".conflict" not in bundle_section


@pytest.mark.compatibility
@pytest.mark.audit
def test_conversations_bundle_precondition_retry() -> None:
    """Conversations retries bundle publish after precondition-not-met."""
    text = read_vendor(
        "vendor/conversations/src/main/java/eu/siacs/conversations/crypto/axolotl/AxolotlService.java"
    )
    assert_pattern(text, r"preconditionNotMet\(response\)", "preconditionNotMet check")
    assert_pattern(text, r"pushNodeConfiguration", "push node configuration")


@pytest.mark.compatibility
@pytest.mark.audit
def test_compat_registry_lists_p0_findings(compat_findings: list[dict]) -> None:
    p0 = [f for f in compat_findings if f.get("severity") == "P0"]
    ids = {f["id"] for f in p0}
    assert "partial_send_conversations" in ids
    assert "partial_send_siskin" in ids
    assert "partial_send_monal" in ids
