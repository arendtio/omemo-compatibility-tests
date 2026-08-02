"""Helpers for Conversations / Siskin legacy axolotl compatibility tests."""

from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from typing import Final

import oldmemo
import oldmemo.etree

NS: Final = f"{{{oldmemo.oldmemo.NAMESPACE}}}"

PEP_DEVICE_LIST_NODE: Final = "eu.siacs.conversations.axolotl.devicelist"
PEP_BUNDLE_NODE_PREFIX: Final = "eu.siacs.conversations.axolotl.bundles:"
PEP_DEVICE_LIST_ITEM_ID: Final = "current"

MESSAGE_AES_KEY_BYTES: Final = 16
FILE_AES_KEY_BYTES: Final = 32
GCM_IV_BYTES: Final = 12
GCM_TAG_BYTES: Final = 16
POST_RATCHET_KEY_BYTES: Final = MESSAGE_AES_KEY_BYTES + GCM_TAG_BYTES


def bundle_pep_node(device_id: int) -> str:
    return f"{PEP_BUNDLE_NODE_PREFIX}{device_id}"


def axolotl_encrypted_element(xml: str) -> ET.Element:
    root = ET.fromstring(xml)
    if root.tag == f"{NS}encrypted":
        return root
    encrypted = root.find(f"{NS}encrypted")
    if encrypted is None:
        raise ValueError("No axolotl encrypted element in XML")
    return encrypted


def serialized_message_xml(message: oldmemo.Message) -> str:
    return ET.tostring(oldmemo.etree.serialize_message(message), encoding="unicode")


def iv_bytes_from_serialized(xml: str) -> bytes:
    encrypted = axolotl_encrypted_element(xml)
    iv_elt = encrypted.find(f"{NS}header").find(f"{NS}iv")
    if iv_elt is None or not iv_elt.text:
        raise ValueError("missing IV")
    return base64.b64decode(iv_elt.text.strip())


def strip_payload_from_serialized(xml: str) -> ET.Element:
    encrypted = axolotl_encrypted_element(xml)
    payload = encrypted.find(f"{NS}payload")
    if payload is not None:
        encrypted.remove(payload)
    return encrypted


def set_prekey_attribute(xml: str, value: str) -> ET.Element:
    encrypted = axolotl_encrypted_element(xml)
    header = encrypted.find(f"{NS}header")
    for key_elt in header.findall(f"{NS}key"):
        if key_elt.get("prekey") is not None:
            key_elt.set("prekey", value)
    return encrypted


def payload_present(xml: str) -> bool:
    encrypted = axolotl_encrypted_element(xml)
    return encrypted.find(f"{NS}payload") is not None
