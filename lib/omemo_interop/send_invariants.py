"""Send-path invariants from the Kompatibilitätsaudit (expected ⊆ encoded)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import FrozenSet, Set, Tuple

import oldmemo

NS = f"{{{oldmemo.oldmemo.NAMESPACE}}}"
BareDevice = Tuple[str, int]


def encoded_devices_from_element(encrypted_root: ET.Element) -> Set[BareDevice]:
    """Extract (bare_jid is unknown in XML — caller supplies jid for remote keys)."""
    header = encrypted_root.find(f"{NS}header")
    if header is None:
        return set()
    rids: Set[int] = set()
    for key_elt in header.findall(f"{NS}key"):
        rid = key_elt.get("rid")
        if rid is not None:
            rids.add(int(rid))
    return rids  # type: ignore[return-value]


def encoded_rids_from_element(element: ET.Element) -> Set[int]:
    encrypted = element
    if element.tag != f"{NS}encrypted":
        encrypted = element.find(f"{NS}encrypted")
    if encrypted is None:
        return set()
    header = encrypted.find(f"{NS}header")
    if header is None:
        return set()
    rids: Set[int] = set()
    for key_elt in header.findall(f"{NS}key"):
        rid = key_elt.get("rid")
        if rid is not None:
            rids.add(int(rid))
    return rids


def expected_remote_rids(
    expected: FrozenSet[BareDevice],
    sender_bare_jid: str,
) -> Set[int]:
    return {device_id for bare_jid, device_id in expected if bare_jid != sender_bare_jid}


def check_expected_subset_encoded_rids(
    expected_remote: Set[int],
    encoded_rids: Set[int],
) -> list[int]:
    """Return device ids in expected but missing from encoded header (violation list)."""
    return sorted(expected_remote - encoded_rids)


def assert_expected_subset_encoded_rids(
    expected_remote: Set[int],
    encoded_rids: Set[int],
    finding_id: str,
) -> None:
    missing = check_expected_subset_encoded_rids(expected_remote, encoded_rids)
    if missing:
        raise AssertionError(
            f"{finding_id}: expected ⊆ encoded violated; missing device rids: {missing}"
        )


def simulate_vendor_partial_send(element: ET.Element, drop_rid: int | None = None) -> ET.Element:
    """
    Conversations / Siskin / Monal P0: omit a recipient key but keep envelope.
    Mirrors addDevice(null skip), compactMap(nil), continue-on-error.
    """
    header = element.find(f"{NS}header")
    if header is None:
        return element
    keys = header.findall(f"{NS}key")
    if drop_rid is not None:
        for key_elt in keys:
            if key_elt.get("rid") == str(drop_rid):
                header.remove(key_elt)
                return element
    if keys:
        header.remove(keys[0])
    return element
