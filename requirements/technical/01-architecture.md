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
(`LegacyOmemoWireClient`). On macOS, prefer vendor-native wire (`native_left` / `native_right` in
`config/interop-matrix.yaml`). Set `OMEMO_FORCE_SMACK_PROXY=1` to keep Smack for debugging.
Smack proxies are scheduled for removal once native matrix is green.

| Target native stack | Wire proxy today | Native bridge path |
|---------------------|------------------|-------------------|
| Conversations axolotl | Smack Gradle `conversations` (deprecated) | `interop/android/` (`ANDROID_HOME`) |
| Monal MLOMEMO | Smack Gradle `monal` (deprecated on macOS) | `interop/monal-native/` (`MonalWire` CLI + `monalxmpp`) |
| Siskin MartinOMEMO | Smack Gradle `siskin` (deprecated on macOS) | `interop/siskin-native/` (macOS Swift) |
| Reference | slixmpp-omemo + python-oldmemo | In-memory harness |

`wire_client.py` routes `monal_native` and `monal_family` to Gradle proxies when built.

## Servers

| Profile | Docker | Open PEP for axolotl nodes |
|---------|--------|----------------------------|
| ejabberd | `docker/ejabberd/` | `force_node_config` access_model open |
| Prosody | `docker/prosody/` | `pep_auto_subscribe`, pubsub component |
| Tigase | `docker/tigase/` | Manual web setup; `OMEMO_TIGASE_READY=1` for tests |

Server-matrix tests run slixmpp OMEMO roundtrips against the active profile on port 5222.
