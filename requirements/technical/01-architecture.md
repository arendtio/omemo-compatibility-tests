# Technical Architecture

## Components

| Component | Role |
|-----------|------|
| `config/implementations.yaml` | Registry of upstream repos, clone paths, test commands |
| `scripts/download-implementations.py` | Clone/update `vendor/` trees |
| `scripts/run-suite.sh` | Orchestrator: download, upstream tests, local pytest, optional wire tests |
| `lib/omemo_interop/` | Shared harness (in-memory PEP, session managers) |
| `tests/cross_backend/` | Protocol-level cross-namespace tests (no server) |
| `tests/standard/` | XEP-0384 structural conformance |
| `tests/scenarios/` | Known interoperability bugs as regression tests |
| `tests/wire/` | slixmpp clients over ejabberd (Docker) |
| `docker/ejabberd/` | Server image and OMEMO pubsub configuration |

## Test Layers

```
Layer 1: Upstream unit tests (vendor/*/pytest)
Layer 2: Cross-backend harness (in-memory, no network)
Layer 3: Standard conformance (XML/namespace validation)
Layer 4: Wire E2E (ejabberd + slixmpp, requires Docker)
```

## Implementation Proxies

Full mobile/desktop clients (Conversations, Monal, Gajim) are not executed in CI. The suite uses Python libraries that implement the same wire formats:

| Client ecosystem | Namespace | Python proxy |
|------------------|-----------|--------------|
| Conversations, legacy Gajim | `eu.siacs.conversations.axolotl` | python-oldmemo |
| Monal, Dino, modern clients | `urn:xmpp:omemo:2` | python-twomemo |

Wire tests use slixmpp-omemo, which loads both backends like production clients.

## Server

ejabberd runs from `ghcr.io/processone/ejabberd` with `force_node_config` open access for OMEMO PEP nodes (required for Monal and cross-client bundle access).
