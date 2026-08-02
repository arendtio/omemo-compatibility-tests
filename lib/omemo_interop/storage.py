"""In-memory OMEMO storage for harness tests."""

from typing import Dict

import omemo


class InMemoryStorage(omemo.Storage):
    """Volatile storage with values held in memory."""

    def __init__(self) -> None:
        super().__init__(True)
        self._storage: Dict[str, omemo.JSONType] = {}

    async def _load(self, key: str) -> omemo.Maybe[omemo.JSONType]:
        try:
            return omemo.Just(self._storage[key])
        except KeyError:
            return omemo.Nothing()

    async def _store(self, key: str, value: omemo.JSONType) -> None:
        self._storage[key] = value

    async def _delete(self, key: str) -> None:
        self._storage.pop(key, None)
