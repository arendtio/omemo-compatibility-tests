"""Static Monal control-flow audit — tests FAIL when known bug patterns remain in source."""

import pytest

from omemo_interop.source_audit import assert_no_pattern, assert_pattern, git_rev, read_vendor

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
def test_monal_partial_send_must_not_continue_on_encrypt_error() -> None:
    """P0 partial_send_monal: per-device encrypt failure must abort send."""
    text = read_vendor(MONAL_OMEMO)
    assert_no_pattern(
        text,
        r"if\(error\)\s*\{[^}]*continue;",
        "partial_send_monal: addEncryptionKeyForAllDevices must not continue on cipher error",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_self_device_filter_must_be_jid_scoped() -> None:
    """P1 monal_self_device_filter_not_jid_scoped: self skip must compare JID + device id."""
    text = read_vendor(MONAL_OMEMO)
    assert_no_pattern(
        text,
        r"if\(device\.unsignedIntValue == self\.monalSignalStore\.deviceid\)\s*continue;",
        "monal_self_device_filter_not_jid_scoped: must not skip devices by id alone",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_decrypt_must_not_use_findfirst_for_rid_only() -> None:
    """P1 monal_same_rid_findfirst: decrypt must try all keys with matching rid."""
    text = read_vendor(MONAL_OMEMO)
    assert_no_pattern(
        text,
        r"findFirst:@\"header/key<rid=%u>#",
        "monal_same_rid_findfirst: must not use findFirst for single rid key",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_duplicate_message_must_repair_session_on_signal_error_3() -> None:
    """P2 monal_carbon_mam_dedup: Signal error 3 must not return early without session repair."""
    import re

    text = read_vendor(MONAL_OMEMO)
    if re.search(
        r"error\.code == 3\)[\s\S]*?Deduplicated[\s\S]*?return nil",
        text,
    ):
        pytest.fail(
            "monal_carbon_mam_dedup: Signal error code 3 path dedups and returns without rebuildSession"
        )


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_devicelist_fetch_error_must_not_fake_empty_list() -> None:
    """P2 monal_devicelist_fetch_fakes_empty: fetch error must not fake empty devicelist."""
    text = read_vendor(MONAL_OMEMO)
    assert_no_pattern(
        text,
        r"faking empty devicelist",
        "monal_devicelist_fetch_fakes_empty: must not fake empty devicelist on fetch error",
    )


@pytest.mark.compatibility
@pytest.mark.audit
def test_monal_trust_gating_on_send_present() -> None:
    """Monal filters untrusted devices via acceptedTrustLevel before send (expected good behavior)."""
    text = read_vendor(MONAL_OMEMO)
    store = read_vendor(MONAL_STORE)
    assert_pattern(text, r"acceptedTrustLevel:trustLevel", "trust check on send path")
    assert_pattern(store, r"acceptedTrustLevel:", "MLSignalStore trust helper")
