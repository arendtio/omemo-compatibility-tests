# Command Registry

All approved commands for this project.

## Setup

- `pip install -e ".[dev]"` — Install suite dependencies and harness
- `python3 scripts/download-implementations.py` — Clone/update upstream implementations into `vendor/`
- `python3 scripts/download-implementations.py --skip-optional` — Skip large optional client repos

## Test Commands

- `./scripts/run-suite.sh` — Full suite: download, upstream unit tests, local interoperability tests
- `./scripts/run-suite.sh --local-only` — Skip upstream and wire tests; run local pytest only
- `./scripts/run-suite.sh --upstream` — Run upstream unit tests in `vendor/`
- `./scripts/run-suite.sh --wire` — Include Docker ejabberd wire tests
- `python3 -m pytest tests/ -v` — Local interoperability tests only
- `python3 -m pytest tests/ -v -m wire` — Wire tests only (requires running ejabberd)
- `python3 -m pytest tests/ -v -m "not wire"` — Exclude wire tests

## Docker (wire tests)

- `docker compose -f docker/ejabberd/docker-compose.yml up -d` — Start ejabberd
- `docker compose -f docker/ejabberd/docker-compose.yml down` — Stop ejabberd

## Expected Outputs

- Successful local run: pytest exit code 0, all non-wire tests green
- Wire tests without Docker: skipped with reason "docker not available" or "ejabberd not reachable"
- Upstream failure: script reports implementation id and subprocess exit code
