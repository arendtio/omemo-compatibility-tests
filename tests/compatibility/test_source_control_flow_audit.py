"""Static re-check of vendor control-flow patterns from the 2026-08-02 audit.

Tests FAIL when known bug patterns are still present in pinned vendor source.
"""

from pathlib import Path

import pytest
import yaml

from omemo_interop.source_audit import assert_no_pattern, assert_pattern, git_rev, read_vendor

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
def test_conversations_partial_send_must_not_silently_skip_null_keys() -> None:
    """P0 partial_send_conversations: addDevice must not skip null keys without aborting send."""
    msg = read_vendor(
        "vendor/conversations/src/main/java/eu/siacs/conversations/crypto/axolotl/XmppAxolotlMessage.java"
    )
    assert_no_pattern(
        msg,
        r"if \(key != null\)\s*\{\s*keys\.add\(key\)",
        "partial_send_conversations: null cipher keys must not be silently skipped",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_partial_send_must_not_drop_failed_encrypts() -> None:
    """P0 partial_send_siskin: encrypt failures must abort send, not compactMap to nil."""
    text = _martin_omemo_text()
    assert_no_pattern(
        text,
        r"catch \{\s*self\.logger\.error",
        "partial_send_siskin: encrypt catch must not swallow failures into nil keys",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_pep_failure_must_not_swallow_into_empty_addresses() -> None:
    """P0: PEP device-list fetch failure must propagate, not yield empty addresses via try?."""
    text = _martin_omemo_text()
    assert_no_pattern(
        text,
        r"try\? await pubsubModule\.retrieveItems\(from: jid, for: OMEMOModule\.DEVICES_LIST_NODE",
        "partial_send_siskin/pep: device-list retrieveItems must not use try? that hides PEP errors",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_bundle_publish_must_propagate_xmpp_errors() -> None:
    """P1 siskin_bundle_before_announce: bundle publish must not return on arbitrary XMPPError."""
    text = _martin_omemo_text()
    assert_no_pattern(
        text,
        r"guard error\.condition == \.item_not_found \|\| error\.condition == \.internal_server_error else \{\s*return;",
        "siskin_bundle_before_announce: publishDeviceBundleIfNeeded must not swallow XMPP errors",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_istrusted_must_not_always_return_true() -> None:
    """P1 siskin_trust_callback_always_true: isTrusted must reflect identity status."""
    text = read_vendor("vendor/siskin_im/SiskinIM/database/DBOMEMOStore.swift")
    assert_no_pattern(
        text,
        r"func isTrusted\(identity: SignalAddress, key:.*?\n.*?return true",
        "siskin_trust_callback_always_true: isTrusted(key) must not unconditionally return true",
    )
    assert_no_pattern(
        text,
        r"func isTrusted\(identity: SignalAddress, publicKeyData:.*?\n.*?return true",
        "siskin_trust_callback_always_true: isTrusted(publicKeyData) must not unconditionally return true",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_martin_device_list_precondition_retry_present() -> None:
    """Device-list publish reconfigures node on conflict (reference pattern for bundles)."""
    text = _martin_omemo_text()
    assert_pattern(text, r"error\.condition == \.conflict", "device list conflict branch")
    assert_pattern(text, r"configureNode\(at: jid, node: OMEMOModule\.DEVICES_LIST_NODE", "reconfigure device list")


@pytest.mark.compatibility
@pytest.mark.audit
def test_martin_bundle_publish_must_retry_on_conflict() -> None:
    """P1 audit gap: bundle publish should handle PEP conflict like device-list publish."""
    text = _martin_omemo_text()
    bundle_section = text.split("func publishDeviceBundle(signedPreKey", 1)[1][:2500]
    assert ".conflict" in bundle_section or "configureNode" in bundle_section, (
        "martin_bundle_publish: bundle publish must retry/reconfigure on PEP conflict"
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_conversations_bundle_precondition_retry_present() -> None:
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
