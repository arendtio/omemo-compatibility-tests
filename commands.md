## Registry

- `python3 scripts/generate-clients-registry.py` — Build `config/clients-registry.yaml` (70 implementations)

## Build Commands

- `pip install -e ".[dev]"` — Install suite dependencies
- `python3 scripts/download-implementations.py` — Clone/update vendor trees
- `python3 scripts/download-implementations.py --ref martin_omemo=2e8435ec48dfb2a70ba414252cc1c8a3815bf24e` — Audit-pinned MartinOMEMO for static tests
- `./scripts/build-clients.sh` — Build Conversations + Monal wire runners (JDK 17+)

## Test Commands

- `python3 -m pytest tests/ -v -m "not wire and not omemo2"` — Default legacy suite
- `python3 -m pytest tests/ -v -m wire` — Wire tests (ejabberd required)
- `python3 -m pytest tests/ -v -m omemo2` — Optional OMEMO 2 tests
- `./scripts/run-suite.sh` — Download + upstream + legacy tests
- `./scripts/run-suite.sh --wire` — Includes client matrix over ejabberd
- `python3 scripts/run-scenario.py scenarios/legacy/full_conversation.yaml` — Multi-message scenario
- `python3 -m pytest tests/compatibility/ -v -m compatibility` — Conversations vs Siskin protocol + wire tests
- `python3 -m pytest tests/compatibility/ -v -m audit` — Static control-flow audit (pinned vendor source)
- `python3 scripts/run-interop-matrix.py --pair conversations-vs-siskin --build` — Conversations vs Siskin IM wire matrix

## Docker

- `docker compose -f docker/ejabberd/docker-compose.yml up -d`
- `docker compose -f docker/ejabberd/docker-compose.yml down`
- `./scripts/start-ejabberd-interop.sh` — Local ejabberd (apt) with interop YAML
- `./scripts/stop-ejabberd-interop.sh` — Stop local interop ejabberd

Wire matrix uses `OMEMO_XMPP_SECURITY=auto` by default (STARTTLS when offered). Set `disabled` for Docker interop ejabberd.
