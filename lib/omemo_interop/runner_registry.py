"""Load client registry and map implementation id -> vendor path."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = ROOT / "config" / "clients-registry.yaml"
IMPLEMENTATIONS = ROOT / "config" / "implementations.yaml"


@dataclass
class ImplementationMeta:
    id: str
    name: str
    runner: str
    wire_capable: bool
    status: str
    kind: str
    vendor_id: Optional[str] = None


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def get_registry() -> List[ImplementationMeta]:
    data = _load_yaml(REGISTRY)
    impls = []
    vendor_map = {i["id"]: i["id"] for i in _load_yaml(IMPLEMENTATIONS).get("implementations", [])}
    for entry in data.get("implementations", []):
        impl_id = entry["id"]
        impls.append(
            ImplementationMeta(
                id=impl_id,
                name=entry.get("name", impl_id),
                runner=entry.get("runner", "unimplemented"),
                wire_capable=bool(entry.get("wire_capable")),
                status=entry.get("status", "planned"),
                kind=entry.get("kind", "client"),
                vendor_id=vendor_map.get(impl_id, impl_id),
            )
        )
    return impls


def get_implementation(impl_id: str) -> ImplementationMeta:
    for impl in get_registry():
        if impl.id == impl_id:
            return impl
    raise KeyError(f"Unknown implementation: {impl_id}")


def vendor_path(impl_id: str) -> Path:
    meta = get_implementation(impl_id)
    vid = meta.vendor_id or meta.id
    return ROOT / "vendor" / vid


def wire_capable_implementations() -> List[ImplementationMeta]:
    return [i for i in get_registry() if i.wire_capable and i.runner not in ("unimplemented", "upstream_tests_only")]
