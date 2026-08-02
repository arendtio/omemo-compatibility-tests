# OMEMO Interoperability Test Suite

Reproducible **legacy OMEMO** (`eu.siacs.conversations.axolotl`) interoperability across **70 tracked implementations** (omemo-top + libraries), prioritizing **real vendor code** on the wire.

OMEMO 2 is optional (`pytest -m omemo2`), not the default matrix.

## Registry (70 implementations)

```bash
python3 scripts/generate-clients-registry.py   # config/clients-registry.yaml
```

Includes all [omemo.top](https://omemo.top) clients plus libraries (slixmpp-omemo, python-omemo, omemo-dr, nbxmpp, …).

## Real-code wire runners

| Runner | Source |
|--------|--------|
| `slixmpp_vendor` | `pip install -e vendor/slixmpp-omemo` |
| `python_oldmemo_vendor` | vendor python-omemo / oldmemo |
| `conversations_android_crypto` | `vendor/conversations` axolotl (Android SDK) |
| `gajim_omemo_dr` | Gajim omemo_dr + nbxmpp (planned) |
| `monal_native`, `dino_native` | Native stacks (planned) |

Unified CLI: `interop/runners/wire_client.py`

## Complex conversation scenarios

YAML scripts in `scenarios/legacy/` — multi-message sessions, bursts, roundtrips:

```bash
docker compose -f docker/ejabberd/docker-compose.yml up -d
python3 scripts/run-scenario.py scenarios/legacy/full_conversation.yaml
python3 scripts/run-extended-matrix.py --tier smoke
```

## Version pinning

```bash
python3 scripts/download-implementations.py --ref conversations=2.20.1 --ref gajim=main
```

## Quick start

```bash
pip install -e ".[dev]"
python3 scripts/generate-clients-registry.py
python3 scripts/download-implementations.py --skip-optional
python3 -m pytest tests/ -v -m "not wire and not omemo2"
./scripts/run-suite.sh --wire
```

See [commands.md](commands.md).
