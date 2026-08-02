"""XEP-0384 structural validation helpers."""

import re
from typing import Final, Iterable, Set

from omemo_interop.constants import NS_OLDMEMO, NS_TWOMEMO

# XEP-0384 fingerprint: 32-byte Curve25519 identity key as 64 hex chars
FINGERPRINT_HEX_RE: Final = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_NAMESPACES: Final = frozenset({NS_OLDMEMO, NS_TWOMEMO})

# Device list node suffixes per namespace (PEP)
OLDMEMO_DEVICE_LIST_NODE: Final = "eu.siacs.conversations.axolotl.devicelist"
TWOMEMO_DEVICE_LIST_NODE: Final = "urn:xmpp:omemo:2:devicelist"


def fingerprint_is_valid_hex(identity_key_bytes: bytes) -> bool:
    """Identity key fingerprint must be 32 bytes encoded as lowercase hex."""
    if len(identity_key_bytes) != 32:
        return False
    return FINGERPRINT_HEX_RE.match(identity_key_bytes.hex()) is not None


def format_fingerprint_for_display(identity_key_bytes: bytes) -> str:
    """XEP-0384 recommends 8 groups of 8 hex characters for display."""
    hex_str = identity_key_bytes.hex()
    return " ".join(hex_str[i:i + 8] for i in range(0, 64, 8))


def namespaces_in_message_xml(xml: str) -> Set[str]:
    """Extract OMEMO namespace URIs present in serialized message XML."""
    found: Set[str] = set()
    for ns in REQUIRED_NAMESPACES:
        if ns in xml:
            found.add(ns)
    return found


def assert_message_has_required_omemo_elements(xml: str, namespace: str) -> None:
    """Verify minimal OMEMO message structure for a given namespace."""
    if namespace not in xml:
        raise ValueError(f"Namespace {namespace} not found in message XML")
    if f"<header xmlns='{namespace}'" not in xml.replace('"', "'"):
        if f'xmlns="{namespace}"' in xml and "header" in xml:
            return
        if "header" not in xml:
            raise ValueError(f"Missing header element for {namespace}")
