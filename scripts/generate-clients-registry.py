#!/usr/bin/env python3
"""Generate config/clients-registry.yaml from omemo-top + known libraries."""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "config" / "clients-registry.yaml"
OMEMO_TOP_CLIENTS_URL = (
    "https://api.github.com/repos/bascht/omemo-top/contents/_data/clients"
)

# Libraries and stacks that participate in interop (not in omemo-top UI list)
LIBRARY_IMPLEMENTATIONS = [
    {
        "id": "python-omemo-oldmemo",
        "name": "python-omemo + oldmemo",
        "kind": "library",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://github.com/Syndace/python-omemo.git",
        "runner": "python_oldmemo_vendor",
        "wire_capable": True,
        "status": "active",
    },
    {
        "id": "slixmpp-omemo",
        "name": "slixmpp-omemo",
        "kind": "library",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://github.com/Syndace/slixmpp-omemo.git",
        "runner": "slixmpp_vendor",
        "wire_capable": True,
        "status": "active",
    },
    {
        "id": "python-nbxmpp",
        "name": "python-nbxmpp OMEMO module",
        "kind": "library",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://dev.gajim.org/gajim/python-nbxmpp.git",
        "runner": "nbxmpp_gajim_stack",
        "wire_capable": True,
        "status": "planned",
    },
    {
        "id": "omemo-dr",
        "name": "omemo-dr (Gajim crypto core)",
        "kind": "library",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://dev.gajim.org/gajim/omemo-dr.git",
        "runner": "gajim_omemo_dr",
        "wire_capable": True,
        "status": "planned",
    },
    {
        "id": "python-oldmemo",
        "name": "python-oldmemo",
        "kind": "library",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://github.com/Syndace/python-oldmemo.git",
        "runner": "python_oldmemo_vendor",
        "wire_capable": True,
        "status": "active",
    },
    {
        "id": "libomemo-c",
        "name": "libomemo-c",
        "kind": "library",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://github.com/signalapp/libsignal-protocol-c.git",
        "runner": "upstream_tests_only",
        "wire_capable": False,
        "status": "reference",
    },
    {
        "id": "converse-js",
        "name": "Converse.js",
        "kind": "client",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://github.com/conversejs/converse.js.git",
        "runner": "converse_js",
        "wire_capable": True,
        "status": "planned",
    },
    {
        "id": "movim",
        "name": "Movim",
        "kind": "client",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://github.com/movim/movim.git",
        "runner": "unimplemented",
        "wire_capable": False,
        "status": "planned",
    },
    {
        "id": "kaidan",
        "name": "Kaidan",
        "kind": "client",
        "namespace": "eu.siacs.conversations.axolotl",
        "repo": "https://invent.kde.org/network/kaidan.git",
        "runner": "kaidan_omemo",
        "wire_capable": True,
        "status": "planned",
    },
]

# Map omemo-top client filenames to our vendor ids and runners
CLIENT_RUNNER_MAP = {
    "conversations": ("conversations", "conversations_android_crypto"),
    "gajim": ("gajim", "gajim_omemo_dr"),
    "dino": ("dino", "dino_native"),
    "monal": ("monal", "monal_native"),
    "monal_im": ("monal", "monal_native"),
    "beagle_im": ("beagle_im", "monal_family"),
    "siskinim": ("siskinim", "monal_family"),
    "converse_js": ("converse", "converse_js"),
    "converse": ("converse", "converse_js"),
    "profanity": ("profanity", "profanity_omemo"),
    "pidgin": ("pidgin", "lurch_pidgin"),
    "psi": ("psi", "psi_omemo"),
    "psi_plus": ("psi_plus", "psi_omemo"),
    "kaidan": ("kaidan", "kaidan_omemo"),
    "chatsecure": ("chatsecure", "ios_legacy"),
    "a_talk": ("atalk", "android_conversations_family"),
    "atalk": ("atalk", "android_conversations_family"),
}


def fetch_omemo_top_clients() -> list[dict]:
    req = urllib.request.Request(
        OMEMO_TOP_CLIENTS_URL,
        headers={"Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        entries = yaml.safe_load(resp.read())  # actually JSON
    if not isinstance(entries, list):
        import json
        with urllib.request.urlopen(req, timeout=30) as resp:
            entries = json.loads(resp.read().decode())

    clients: list[dict] = []
    for entry in entries:
        if entry.get("type") != "file" or not entry["name"].endswith(".yml"):
            continue
        raw_url = entry["download_url"]
        with urllib.request.urlopen(raw_url, timeout=30) as resp:
            meta = yaml.safe_load(resp.read().decode())
        slug = entry["name"].replace(".yml", "")
        vendor_id, runner = CLIENT_RUNNER_MAP.get(slug, (slug, "unimplemented"))
        done = meta.get("done") in (True, "yes", "Yes")
        clients.append({
            "id": vendor_id if vendor_id != slug else slug,
            "omemo_top_slug": slug,
            "name": meta.get("name", slug),
            "kind": "client",
            "url": meta.get("url"),
            "namespace": "eu.siacs.conversations.axolotl",
            "omemo_top_done": done,
            "omemo_top_status": meta.get("status"),
            "os_support": meta.get("os_support", []),
            "runner": runner,
            "wire_capable": done,
            "status": "active" if runner not in ("unimplemented", "ios_legacy") else "planned",
            "tracking_issue": meta.get("tracking_issue"),
        })
    return clients


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    try:
        clients = fetch_omemo_top_clients()
    except Exception as exc:
        print(f"Warning: could not fetch omemo-top ({exc}), using embedded minimum set")
        clients = []

    if not clients:
        # Fallback embedded list if network fails
        clients = [
            {
                "id": "conversations",
                "name": "Conversations",
                "kind": "client",
                "namespace": "eu.siacs.conversations.axolotl",
                "runner": "conversations_android_crypto",
                "wire_capable": True,
                "status": "active",
            },
            {
                "id": "gajim",
                "name": "Gajim",
                "kind": "client",
                "namespace": "eu.siacs.conversations.axolotl",
                "runner": "gajim_omemo_dr",
                "wire_capable": True,
                "status": "planned",
            },
            {
                "id": "dino",
                "name": "Dino",
                "kind": "client",
                "namespace": "eu.siacs.conversations.axolotl",
                "runner": "dino_native",
                "wire_capable": True,
                "status": "planned",
            },
            {
                "id": "monal",
                "name": "Monal",
                "kind": "client",
                "namespace": "eu.siacs.conversations.axolotl",
                "runner": "monal_native",
                "wire_capable": True,
                "status": "planned",
            },
        ]

    implementations = clients + LIBRARY_IMPLEMENTATIONS

    registry = {
        "namespace": "eu.siacs.conversations.axolotl",
        "description": (
            "Registry of OMEMO clients and libraries for real-code interoperability testing. "
            "Sourced from omemo-top plus protocol libraries."
        ),
        "implementation_count": len(implementations),
        "implementations": implementations,
        "runner_types": {
            "conversations_android_crypto": "Compiles vendor/conversations axolotl Java on wire",
            "gajim_omemo_dr": "Gajim omemo_dr + nbxmpp from vendor",
            "slixmpp_vendor": "pip install -e vendor/slixmpp-omemo",
            "python_oldmemo_vendor": "python-omemo oldmemo harness from vendor",
            "dino_native": "Meson build dino omemo plugin",
            "monal_native": "Xcode monalxmpp MLOMEMO",
            "converse_js": "Headless converse.js + libsignal",
            "unimplemented": "Tracked; runner not yet built",
            "upstream_tests_only": "Clone + upstream unit tests only",
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Wrote {len(implementations)} implementations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
