#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="${EJABBERD_INTEROP_CONFIG:-$ROOT/docker/ejabberd/ejabberd.yml}"
SPOOL="${EJABBERD_INTEROP_SPOOL:-/tmp/omemo-ejabberd-spool}"
LOGS="${EJABBERD_INTEROP_LOGS:-/tmp/omemo-ejabberd-logs}"
export EJABBERD_CONFIG_PATH="$CONFIG"
export SPOOL_DIR="$SPOOL"
export LOGS_DIR="$LOGS"
export HOME="${EJABBERD_INTEROP_HOME:-/tmp/omemo-ejabberd-home}"
export EJABBERD_NODE="${EJABBERD_NODE:-ejabberd@localhost}"
if [[ "$(uname -s)" == "Darwin" ]]; then
  export PATH="/opt/homebrew/sbin:/usr/local/sbin:$PATH"
fi
if [[ "$(uname -s)" != "Darwin" ]] && command -v sudo >/dev/null 2>&1; then
  sudo -E ejabberdctl stop 2>/dev/null || true
else
  ejabberdctl stop 2>/dev/null || true
fi
