# OMEMO Interoperability Test Suite

Reproducible compatibility testing for XMPP OMEMO (XEP-0384) across servers and client implementations.

## What this does

1. **Downloads** current upstream sources (ejabberd, python-omemo, slixmpp-omemo, Conversations, Monal, …) into `vendor/`
2. **Runs upstream unit tests** from python-omemo and slixmpp-omemo
3. **Cross-backend tests** simulate Conversations-style (`eu.siacs.conversations.axolotl`) vs Monal/Dino-style (`urn:xmpp:omemo:2`) clients without a network
4. **Standard conformance** checks XEP-0384 namespace URIs, fingerprint format, and wire XML structure
5. **Wire E2E tests** (optional) run two slixmpp clients against ejabberd over real XMPP

## Quick start

```bash
pip install -e ".[dev]"
python3 scripts/download-implementations.py --skip-optional
pytest tests/ -v -m "not wire"
```

Full suite (download + upstream + local):

```bash
./scripts/run-suite.sh --local-only   # no upstream
./scripts/run-suite.sh                # includes upstream tests
```

Wire tests (requires Docker):

```bash
docker compose -f docker/ejabberd/docker-compose.yml up -d
pytest tests/ -v -m wire
docker compose -f docker/ejabberd/docker-compose.yml down
```

Or:

```bash
./scripts/run-suite.sh --wire
```

## Test layers

| Layer | Location | Network |
|-------|----------|---------|
| Upstream unit | `vendor/*/pytest` | No |
| Cross-backend | `tests/cross_backend/` | No |
| Standard | `tests/standard/` | No |
| Scenarios | `tests/scenarios/` | No |
| Wire E2E | `tests/wire/` | Yes (ejabberd) |

## Implementation proxies

Mobile/desktop clients are not executed in CI. Python libraries implement the same wire formats:

| Ecosystem | Namespace | Proxy |
|-----------|-----------|-------|
| Conversations, legacy Gajim | `eu.siacs.conversations.axolotl` | python-oldmemo |
| Monal, Dino, modern clients | `urn:xmpp:omemo:2` | python-twomemo |
| Wire transport | both | slixmpp-omemo |

## Known incompatibility scenarios

Documented in `tests/scenarios/known_issues.yaml` with links to upstream bug reports (ejabberd PEP access, Monal bundle visibility, publish-options, key transport).

## Commands

See [commands.md](commands.md) for the full command registry.

## Requirements

- Python 3.10+
- Git
- Docker (optional, for wire tests)
