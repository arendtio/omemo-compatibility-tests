# Technical Architecture

## Components

| Component | Role |
|-----------|------|
| `config/implementations.yaml` | Registry of upstream repos, clone paths, test commands |
| `config/interop-matrix.yaml` | Client pair wire scenarios (Conversations/Siskin/Monal) |
| `config/server-matrix.yaml` | XMPP server profiles (ejabberd, Prosody, Tigase) |
| `scripts/download-implementations.py` | Clone/update `vendor/` trees |
| `scripts/run-interop-matrix.py` | Gradle client matrix over ejabberd |
| `scripts/run-server-matrix.py` | slixmpp roundtrip per server profile |
| `lib/omemo_interop/` | Shared harness (in-memory PEP, session managers) |
| `interop/clients/` | Gradle wire runners (Smack + libsignal-java proxies) |
| `interop/runners/wire_client.py` | Unified wire CLI (slixmpp, Gradle proxies) |
| `tests/cross_backend/` | Protocol-level cross-namespace tests (no server) |
| `tests/compatibility/` | Audit static checks + Conversations/Siskin/Monal wire |
| `tests/wire/` | Client matrix + server matrix pytest drivers |
| `docker/ejabberd/`, `docker/prosody/`, `docker/tigase/` | Server images |

## Test Layers

```
Layer 1: Upstream unit tests (vendor/*/pytest)
Layer 2: Cross-backend harness (in-memory, no network)
Layer 3: Standard conformance (XML/namespace validation)
Layer 4: Wire E2E (XMPP server + Gradle/slixmpp runners)
Layer 5: Static vendor control-flow audit (pinned source)
```

## Implementation Proxies

Gradle runners (`conversations`, `monal`, `siskin`) use **Smack 4.4.8 + smack-omemo-signal**
(`LegacyOmemoWireClient`). Vendor trees are compile-time pins and `VENDOR_REV` logging — not
native AxolotlService / MLOMEMO / MartinOMEMO on Linux CI today.

| Target native stack | Wire proxy today | Native bridge path |
|---------------------|------------------|-------------------|
| Conversations axolotl | Smack Gradle `conversations` | `interop/android/` (needs `ANDROID_HOME`) |
| Monal MLOMEMO | Smack Gradle `monal` | `interop/monal-native/` (macOS ObjC) |
| Siskin MartinOMEMO | Smack Gradle `siskin` | Swift/TigaseSwift (not wired on Linux) |
| Reference | slixmpp-omemo + python-oldmemo | In-memory harness |

`wire_client.py` routes `monal_native` and `monal_family` to Gradle proxies when built.

## Servers

| Profile | Docker | Open PEP for axolotl nodes |
|---------|--------|----------------------------|
| ejabberd | `docker/ejabberd/` | `force_node_config` access_model open |
| Prosody | `docker/prosody/` | `pep_auto_subscribe`, pubsub component |
| Tigase | `docker/tigase/` | Manual web setup; `OMEMO_TIGASE_READY=1` for tests |

Server-matrix tests run slixmpp OMEMO roundtrips against the active profile on port 5222.
