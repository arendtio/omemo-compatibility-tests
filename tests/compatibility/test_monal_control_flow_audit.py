"""Static Monal control-flow audit (Kompatibilitätsaudit P0/P1)."""

import pytest

from omemo_interop.source_audit import assert_pattern, git_rev, read_vendor

MONAL_OMEMO = "vendor/monal/Monal/Classes/MLOMEMO.m"
MONAL_STORE = "vendor/monal/Monal/Classes/MLSignalStore.m"


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_vendored_commit_matches_audit_pin() -> None:
    from pathlib import Path

    import yaml

    pins = Path(__file__).resolve().parent.parent.parent / "config" / "audit-source-pins.yaml"
    with open(pins, encoding="utf-8") as f:
        pin = yaml.safe_load(f)["audits"]["conversations_siskin_monal_2026-08-02"]["clients"]["monal"]["commit"]
    rev = git_rev("vendor/monal")
    if rev and pin:
        assert rev.startswith(pin[:8])


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_partial_send_add_encryption_continues_on_error() -> None:
    """P0: failed cipher in addEncryptionKeyForAllDevices only continues, encryptString still returns envelope."""
    text = read_vendor(MONAL_OMEMO)
    assert_pattern(text, r"addEncryptionKeyForAllDevices:", "addEncryptionKeyForAllDevices")
    assert_pattern(text, r"if\(error\)\s*\{[^}]*continue;", "encrypt error continue")
    assert_pattern(text, r"encryptString:.*return encrypted;", "encryptString returns envelope")


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_self_device_filter_not_jid_scoped() -> None:
    """P1: checkTrustOfAllDevices skips by device id alone (audit #240 class bug)."""
    text = read_vendor(MONAL_OMEMO)
    assert_pattern(
        text,
        r"if\(device\.unsignedIntValue == self\.monalSignalStore\.deviceid\)\s*continue;",
        "deviceid-only self skip in checkTrustOfAllDevices",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_decrypt_uses_findfirst_for_rid() -> None:
    """P1: MUC duplicate rid — only first matching key is selected on decrypt."""
    text = read_vendor(MONAL_OMEMO)
    assert_pattern(text, r"findFirst:@\"header/key<rid=%u>#", "findFirst single rid key")


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_duplicate_message_dedup_on_signal_error_3() -> None:
    """P2: Carbon/MAM duplicate — Signal error code 3 treated as dedup, no session repair."""
    text = read_vendor(MONAL_OMEMO)
    assert_pattern(text, r"error\.code == 3", "signal duplicate error code")
    assert_pattern(text, r"Deduplicated", "dedup log path")


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_devicelist_fetch_error_fakes_empty_list() -> None:
    """P2: own devicelist fetch failure fakes empty list instead of hard error."""
    text = read_vendor(MONAL_OMEMO)
    assert_pattern(text, r"handleOwnDevicelistFetchError", "own devicelist error handler")
    assert_pattern(text, r"faking empty devicelist", "fake empty list")


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_trust_gating_on_send() -> None:
    """Compromised/untrusted devices filtered via acceptedTrustLevel before send."""
    text = read_vendor(MONAL_OMEMO)
    store = read_vendor(MONAL_STORE)
    assert_pattern(text, r"acceptedTrustLevel:trustLevel", "trust check on send path")
    assert_pattern(store, r"acceptedTrustLevel:", "MLSignalStore trust helper")
