# OMEMO Interoperability Test Suite

Reproducible **legacy OMEMO** (`eu.siacs.conversations.axolotl`) compatibility testing across Conversations, Monal, ejabberd, and reference libraries.

OMEMO 2 (`urn:xmpp:omemo:2`) is **out of scope** for the default matrix until implementations stabilize. Optional `omemo2` tests remain in `tests/cross_backend/`.

## What this does

1. **Downloads** checked-out client and server sources into `vendor/` (supports `--ref conversations=TAG`)
2. **Runs upstream unit tests** (python-omemo, slixmpp-omemo)
3. **Legacy protocol tests** in-memory (`tests/legacy/`)
4. **Wire client runners** built from `interop/clients/` — bound to vendor Conversations and Monal trees
5. **Client matrix** over ejabberd: Conversations implementation vs Monal implementation (headless, no GUI)

## Quick start

```bash
pip install -e ".[dev]"
python3 scripts/download-implementations.py --skip-optional
python3 -m pytest tests/ -v -m "not wire and not omemo2"
```

Checkout specific client versions and test them against each other:

```bash
python3 scripts/download-implementations.py --ref conversations=2.20.1 --ref monal=main
./scripts/build-clients.sh
docker compose -f docker/ejabberd/docker-compose.yml up -d
python3 scripts/run-interop-matrix.py --pair conversations-vs-monal --build
```

Full orchestrator:

```bash
./scripts/run-suite.sh --wire
```

## Client wire runners

| Runner | Vendor tree | Legacy namespace |
|--------|-------------|------------------|
| `conversations` | `vendor/conversations` (Codeberg) | `eu.siacs.conversations.axolotl` |
| `monal` | `vendor/monal` | `eu.siacs.conversations.axolotl` |

Runners verify vendor crypto sources exist at checkout and report `VENDOR_REV` for reproducibility. They use Smack + libsignal on the wire (same family as both clients). Gradle verifies `XmppAxolotlMessage.java` / `MLOMEMO.m` are present in the checked-out tree.

## Test layers

| Layer | Location | Network |
|-------|----------|---------|
| Upstream unit | `vendor/*/pytest` | No |
| Legacy protocol | `tests/legacy/` | No |
| Standard (axolotl) | `tests/standard/` | No |
| Client wire matrix | `tests/wire/test_client_matrix.py` | Yes |
| OMEMO 2 (optional) | `tests/cross_backend/` | No |

## Config

- `config/implementations.yaml` — repos, refs, build commands
- `config/interop-matrix.yaml` — client pairs and scenarios

## Requirements

- Python 3.10+
- JDK 17+ (wire clients)
- Git
- Docker (wire tests + ejabberd)

See [commands.md](commands.md) for the command registry.
