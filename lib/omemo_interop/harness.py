"""
In-memory PEP/session harness for cross-backend OMEMO tests.

Adapted from python-omemo's test utilities (GPLv3). Simulates bundle/device-list
exchange without a live XMPP server.
"""

import enum
import sys
from typing import Dict, FrozenSet, List, Optional, Tuple, Type

import omemo

if sys.version_info >= (3, 11):
    from typing import assert_never
else:
    from typing_extensions import assert_never


class TrustLevel(enum.Enum):
    TRUSTED = "TRUSTED"
    UNDECIDED = "UNDECIDED"
    DISTRUSTED = "DISTRUSTED"


class BundleStorageKey:
    def __init__(self, namespace: str, bare_jid: str, device_id: int) -> None:
        self.namespace = namespace
        self.bare_jid = bare_jid
        self.device_id = device_id

    def __hash__(self) -> int:
        return hash((self.namespace, self.bare_jid, self.device_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BundleStorageKey):
            return False
        return (
            self.namespace == other.namespace
            and self.bare_jid == other.bare_jid
            and self.device_id == other.device_id
        )


class DeviceListStorageKey:
    def __init__(self, namespace: str, bare_jid: str) -> None:
        self.namespace = namespace
        self.bare_jid = bare_jid

    def __hash__(self) -> int:
        return hash((self.namespace, self.bare_jid))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DeviceListStorageKey):
            return False
        return self.namespace == other.namespace and self.bare_jid == other.bare_jid


BundleStorage = Dict[BundleStorageKey, omemo.Bundle]
DeviceListStorage = Dict[DeviceListStorageKey, omemo.DeviceList]
MessageQueue = List[Tuple[str, omemo.Message]]


def make_session_manager_impl(
    own_bare_jid: str,
    bundle_storage: BundleStorage,
    device_list_storage: DeviceListStorage,
    message_queue: MessageQueue,
) -> Type[omemo.SessionManager]:
    """Build a SessionManager that uses shared in-memory PEP storage."""

    class SessionManagerImpl(omemo.SessionManager):
        @staticmethod
        async def _upload_bundle(bundle: omemo.Bundle) -> None:
            bundle_storage[BundleStorageKey(
                namespace=bundle.namespace,
                bare_jid=bundle.bare_jid,
                device_id=bundle.device_id,
            )] = bundle

        @staticmethod
        async def _download_bundle(namespace: str, bare_jid: str, device_id: int) -> omemo.Bundle:
            try:
                return bundle_storage[BundleStorageKey(
                    namespace=namespace,
                    bare_jid=bare_jid,
                    device_id=device_id,
                )]
            except KeyError as exc:
                raise omemo.BundleDownloadFailed() from exc

        @staticmethod
        async def _delete_bundle(namespace: str, device_id: int) -> None:
            try:
                bundle_storage.pop(BundleStorageKey(
                    namespace=namespace,
                    bare_jid=own_bare_jid,
                    device_id=device_id,
                ))
            except KeyError as exc:
                raise omemo.BundleDeletionFailed() from exc

        @staticmethod
        async def _upload_device_list(namespace: str, device_list: omemo.DeviceList) -> None:
            key = DeviceListStorageKey(namespace=namespace, bare_jid=own_bare_jid)
            existing = device_list_storage.get(key, {})
            merged = dict(existing)
            merged.update(device_list)
            device_list_storage[key] = merged

        @staticmethod
        async def _download_device_list(namespace: str, bare_jid: str) -> omemo.DeviceList:
            try:
                return device_list_storage[DeviceListStorageKey(
                    namespace=namespace,
                    bare_jid=bare_jid,
                )]
            except KeyError:
                return {}

        async def _evaluate_custom_trust_level(self, device: omemo.DeviceInformation) -> omemo.TrustLevel:
            try:
                trust_level = TrustLevel(device.trust_level_name)
            except ValueError as exc:
                raise omemo.UnknownTrustLevel() from exc

            if trust_level is TrustLevel.TRUSTED:
                return omemo.TrustLevel.TRUSTED
            if trust_level is TrustLevel.UNDECIDED:
                return omemo.TrustLevel.UNDECIDED
            if trust_level is TrustLevel.DISTRUSTED:
                return omemo.TrustLevel.DISTRUSTED

            assert_never(trust_level)

        async def _make_trust_decision(
            self,
            undecided: FrozenSet[omemo.DeviceInformation],
            identifier: Optional[str],
        ) -> None:
            for device in undecided:
                await self.set_trust(device.bare_jid, device.identity_key, TrustLevel.TRUSTED.name)

        @staticmethod
        async def _send_message(message: omemo.Message, bare_jid: str) -> None:
            message_queue.append((bare_jid, message))

    return SessionManagerImpl


class InteropHarness:
    """Two-party (or multi-party) OMEMO test fixture with shared PEP storage."""

    def __init__(
        self,
        bare_jid: str,
        backends: List[omemo.Backend],
        bundle_storage: BundleStorage,
        device_list_storage: DeviceListStorage,
    ) -> None:
        self.bare_jid = bare_jid
        self.backends = backends
        self._bundle_storage = bundle_storage
        self._device_list_storage = device_list_storage
        self._message_queue: MessageQueue = []
        self._storage = None
        self.session_manager: Optional[omemo.SessionManager] = None

    async def initialize(self) -> omemo.SessionManager:
        from omemo_interop.storage import InMemoryStorage

        self._storage = InMemoryStorage()
        impl = make_session_manager_impl(
            self.bare_jid,
            self._bundle_storage,
            self._device_list_storage,
            self._message_queue,
        )
        self.session_manager = await impl.create(
            backends=self.backends,
            storage=self._storage,
            own_bare_jid=self.bare_jid,
            initial_own_label=None,
            undecided_trust_level_name=TrustLevel.UNDECIDED.name,
        )
        await self.session_manager.after_history_sync()
        return self.session_manager

    def drain_message_queue(self) -> MessageQueue:
        messages = list(self._message_queue)
        self._message_queue.clear()
        return messages
