#!/usr/bin/env bash
# OMEMO interoperability test orchestrator (legacy OMEMO focus).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUN_UPSTREAM=false
RUN_WIRE=false
RUN_LOCAL=true
SKIP_DOWNLOAD=false

for arg in "$@"; do
  case "$arg" in
    --upstream) RUN_UPSTREAM=true ;;
    --wire) RUN_WIRE=true ;;
    --local-only) RUN_UPSTREAM=false; RUN_WIRE=false ;;
    --skip-download) SKIP_DOWNLOAD=true ;;
    --help|-h)
      echo "Usage: $0 [--upstream] [--wire] [--local-only] [--skip-download]"
      exit 0
      ;;
  esac
done

if [[ "$RUN_UPSTREAM" == false && "$RUN_WIRE" == false && "$RUN_LOCAL" == true ]]; then
  RUN_UPSTREAM=true
fi

echo "=== OMEMO Interop Suite (legacy axolotl) ==="

if [[ "$SKIP_DOWNLOAD" == false ]]; then
  echo "--- Downloading implementations ---"
  python3 scripts/download-implementations.py --skip-optional
fi

echo "--- Installing suite ---"
pip install -q -e ".[dev]"

if [[ "$RUN_UPSTREAM" == true ]]; then
  echo "--- Upstream unit tests ---"
  python3 scripts/run-upstream-tests.py
fi

if [[ "$RUN_WIRE" == true ]]; then
  if command -v docker >/dev/null 2>&1; then
    echo "--- Starting ejabberd ---"
    docker compose -f docker/ejabberd/docker-compose.yml up -d --wait 2>/dev/null || \
      docker compose -f docker/ejabberd/docker-compose.yml up -d
    sleep 5
  fi
  echo "--- Building legacy wire clients ---"
  ./scripts/build-clients.sh
  if python3 -c "import socket; s=socket.create_connection(('127.0.0.1',5222),2); s.close()" 2>/dev/null; then
    echo "--- Client interop matrix ---"
    python3 scripts/run-interop-matrix.py --pair conversations-vs-monal --build
  fi
  PYTEST_MARK="-m wire"
else
  PYTEST_MARK="-m 'not wire and not omemo2'"
fi

echo "--- Tests (${PYTEST_MARK}) ---"
eval "python3 -m pytest tests/ -v ${PYTEST_MARK}"

if [[ "$RUN_WIRE" == true ]] && command -v docker >/dev/null 2>&1; then
  docker compose -f docker/ejabberd/docker-compose.yml down
fi

echo "=== Suite complete ==="
