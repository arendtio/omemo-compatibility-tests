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
    """P0: MartinOMEMO filters failed encrypt results out of header."""
    text = _martin_omemo_text()
    assert_pattern(text, r"case \.failure\(_\):\s*return nil", "_encode nil on failure")
    assert_pattern(text, r"\.filter\(\{ \(el\) -> Bool in", "_encode filter nil keys")


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_pep_failure_swallowed_pattern() -> None:
    """P0: addresses(for:) breaks on PEP failure instead of propagating."""
    text = _martin_omemo_text()
    assert_pattern(text, r"case \.failure\(_\):\s*break", "PEP failure break in addresses")


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_bundle_publish_error_handling() -> None:
    """P1: unexpected bundle read errors are treated like missing bundle."""
    text = _martin_omemo_text()
    assert_pattern(
        text,
        r"publishDeviceBundleIfNeeded.*?case \.failure\(let pubsubError\):",
        "publishDeviceBundleIfNeeded failure branch",
    )
    assert_pattern(text, r"guard pubsubError\.error == \.item_not_found", "only some errors throw")


@pytest.mark.compatibility
@pytest.mark.audit
def test_siskin_istrusted_always_true() -> None:
    text = read_vendor("vendor/siskin_im/SiskinIM/database/DBOMEMOStore.swift")
    assert_pattern(text, r"func isTrusted\(identity: SignalAddress, key:.*?\n.*?return true", "isTrusted key")
    assert_pattern(text, r"func isTrusted\(identity: SignalAddress, publicKeyData:.*?\n.*?return true", "isTrusted data")


@pytest.mark.compatibility
@pytest.mark.audit
def test_compat_registry_lists_p0_findings(compat_findings: list[dict]) -> None:
    p0 = [f for f in compat_findings if f.get("severity") == "P0"]
    ids = {f["id"] for f in p0}
    assert "partial_send_conversations" in ids
    assert "partial_send_siskin" in ids
