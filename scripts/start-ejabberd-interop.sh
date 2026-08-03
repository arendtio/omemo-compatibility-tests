#!/usr/bin/env bash
# Start ejabberd with the OMEMO interop config (plaintext C2S + open PEP for axolotl nodes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="${EJABBERD_INTEROP_CONFIG:-$ROOT/docker/ejabberd/ejabberd.yml}"
SPOOL="${EJABBERD_INTEROP_SPOOL:-/tmp/omemo-ejabberd-spool}"
LOGS="${EJABBERD_INTEROP_LOGS:-/tmp/omemo-ejabberd-logs}"
HOME_DIR="${EJABBERD_INTEROP_HOME:-/tmp/omemo-ejabberd-home}"

mkdir -p "$SPOOL" "$LOGS" "$HOME_DIR"
if command -v sudo >/dev/null 2>&1 && [[ "$(uname -s)" != "Darwin" ]]; then
  sudo chown ejabberd:ejabberd "$SPOOL" "$LOGS" 2>/dev/null || true
fi

export EJABBERD_INTEROP_CONFIG="$CONFIG"
export EJABBERD_INTEROP_SPOOL="$SPOOL"
export EJABBERD_INTEROP_LOGS="$LOGS"
export EJABBERD_CONFIG_PATH="$CONFIG"
export SPOOL_DIR="$SPOOL"
export LOGS_DIR="$LOGS"
export HOME="$HOME_DIR"
export EJABBERD_NODE="${EJABBERD_NODE:-ejabberd@localhost}"
export OMEMO_XMPP_SECURITY="${OMEMO_XMPP_SECURITY:-auto}"
export EJABBERD_BYPASS_WARNINGS="${EJABBERD_BYPASS_WARNINGS:-true}"

if [[ "$(uname -s)" == "Darwin" ]]; then
  export PATH="/opt/homebrew/sbin:/usr/local/sbin:$PATH"
  short="$(hostname -s 2>/dev/null || hostname)"
  if [[ -n "$short" ]] && ! grep -qw "$short" /etc/hosts 2>/dev/null; then
    if command -v sudo >/dev/null 2>&1; then
      echo "127.0.0.1 $short" | sudo tee -a /etc/hosts >/dev/null || true
    fi
  fi
fi

use_sudo_ctl() {
  [[ "$(uname -s)" != "Darwin" ]] && command -v sudo >/dev/null 2>&1
}

run_ctl() {
  if use_sudo_ctl; then
    sudo -E ejabberdctl "$@"
  else
    ejabberdctl "$@"
  fi
}

install_interop_config() {
  # Debian/apt ejabberd reads /etc/ejabberd/ejabberd.yml — EJABBERD_CONFIG_PATH only affects ctl.
  if [[ -d /etc/ejabberd ]] && use_sudo_ctl; then
    sudo install -m 644 "$CONFIG" /etc/ejabberd/ejabberd.yml
  fi
}

was_running=false
if run_ctl status >/dev/null 2>&1; then
  was_running=true
fi

install_interop_config

if $was_running; then
  echo "Restarting ejabberd with interop config: $CONFIG"
  run_ctl restart
else
  echo "Starting ejabberd with $CONFIG"
  rm -rf "${SPOOL:?}"/* 2>/dev/null || sudo rm -rf "${SPOOL:?}"/* 2>/dev/null || true
  run_ctl start
fi

for _ in $(seq 1 30); do
  if run_ctl status >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! run_ctl status >/dev/null 2>&1; then
  echo "ejabberd failed to start" >&2
  exit 1
fi
echo "ejabberd ready (interop config: $CONFIG)"

run_ctl register alice localhost alicepass 2>/dev/null || true
run_ctl register bob localhost bobpass 2>/dev/null || true
