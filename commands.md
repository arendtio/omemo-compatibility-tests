## Build Commands

- `pip install -e ".[dev]"` — Install suite dependencies
- `python3 scripts/download-implementations.py` — Clone/update vendor trees
- `python3 scripts/download-implementations.py --ref conversations=2.20.1` — Pin client version
- `./scripts/build-clients.sh` — Build Conversations + Monal wire runners (JDK 17+)

## Test Commands

- `python3 -m pytest tests/ -v -m "not wire and not omemo2"` — Default legacy suite
- `python3 -m pytest tests/ -v -m wire` — Wire tests (ejabberd required)
- `python3 -m pytest tests/ -v -m omemo2` — Optional OMEMO 2 tests
- `./scripts/run-suite.sh` — Download + upstream + legacy tests
- `./scripts/run-suite.sh --wire` — Includes client matrix over ejabberd
- `python3 scripts/run-interop-matrix.py --pair conversations-vs-monal --build` — Client interop only

## Docker

- `docker compose -f docker/ejabberd/docker-compose.yml up -d`
- `docker compose -f docker/ejabberd/docker-compose.yml down`
