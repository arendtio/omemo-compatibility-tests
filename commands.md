## Registry

- `python3 scripts/generate-clients-registry.py` — Build `config/clients-registry.yaml` (70 implementations)

## Build Commands

- `pip install -e ".[dev]"` — Install suite dependencies
- `python3 scripts/download-implementations.py` — Clone/update vendor trees
- `python3 scripts/download-implementations.py --ref martin_omemo=2e8435ec48dfb2a70ba414252cc1c8a3815bf24e` — Audit-pinned MartinOMEMO for static tests
- `python3 scripts/download-implementations.py --ref monal=c69bd05ac245f8ba1e206e4185a3ca92607ecaa8` — Audit-pinned Monal for static tests
- `./scripts/build-clients.sh` — Build Conversations + Monal + Siskin wire runners (JDK 17+)

## Test Commands

- `python3 -m pytest tests/ -v -m "not wire and not omemo2"` — Legacy suite (includes audit/vendor-bug tests; red while bugs open)
- `python3 -m pytest tests/ -v -m wire` — Wire tests (XMPP server required)
- `python3 -m pytest tests/ -v -m omemo2` — Optional OMEMO 2 tests
- `python3 -m pytest tests/ -v -m native` — Native bridge availability (mostly skipped)
- `./scripts/run-suite.sh` — Download + upstream + legacy tests
- `./scripts/run-suite.sh --wire` — Includes client matrix over ejabberd
- `python3 scripts/run-scenario.py scenarios/legacy/full_conversation.yaml` — Multi-message scenario
- `python3 -m pytest tests/compatibility/ -v -m compatibility` — Protocol + wire compatibility tests
- `python3 -m pytest tests/compatibility/ -v -m audit` — Static control-flow audit (pinned vendor source)
- `python3 scripts/run-interop-matrix.py --pair conversations-vs-siskin --build` — Conversations vs Siskin wire matrix
- `python3 scripts/run-interop-matrix.py --pair conversations-vs-monal --build` — Conversations vs Monal wire matrix
- `python3 scripts/run-server-matrix.py --profile ejabberd` — slixmpp roundtrip on active server
- `python3 scripts/run-server-matrix.py --profile prosody --start --stop` — Prosody docker smoke

## Docker

- `docker compose -f docker/ejabberd/docker-compose.yml up -d`
- `docker compose -f docker/ejabberd/docker-compose.yml down`
- `docker compose -f docker/prosody/docker-compose.yml up -d`
- `docker compose -f docker/prosody/docker-compose.yml down`
- `./scripts/start-ejabberd-interop.sh` — Local ejabberd (apt) with interop YAML
- `./scripts/stop-ejabberd-interop.sh` — Stop local interop ejabberd

Wire matrix uses `OMEMO_XMPP_SECURITY=auto` by default (STARTTLS when offered). Set `disabled` for Docker interop servers.

Tigase server-matrix tests require manual web setup — see `docker/tigase/README.md` and `OMEMO_TIGASE_READY=1`.
