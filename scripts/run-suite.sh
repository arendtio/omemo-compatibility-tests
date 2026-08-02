#!/usr/bin/env bash
# OMEMO interoperability test orchestrator.
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

# Default: run everything except wire (wire requires --wire)
if [[ "$RUN_UPSTREAM" == false && "$RUN_WIRE" == false && "$RUN_LOCAL" == true ]]; then
  RUN_UPSTREAM=true
fi

echo "=== OMEMO Interop Suite ==="

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
    WIRE_MARKER="-m wire"
  else
    echo "Docker not available; wire tests will be skipped by pytest"
    WIRE_MARKER="-m wire"
  fi
else
  WIRE_MARKER="-m 'not wire'"
fi

echo "--- Local interoperability tests ---"
eval "python3 -m pytest tests/ -v ${WIRE_MARKER}"

if [[ "$RUN_WIRE" == true ]] && command -v docker >/dev/null 2>&1; then
  echo "--- Stopping ejabberd ---"
  docker compose -f docker/ejabberd/docker-compose.yml down
fi

echo "=== Suite complete ==="
