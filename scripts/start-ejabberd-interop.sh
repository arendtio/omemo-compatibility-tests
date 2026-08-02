#!/usr/bin/env bash
# Start ejabberd with the OMEMO interop config (plaintext C2S + open PEP for axolotl nodes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="${EJABBERD_INTEROP_CONFIG:-$ROOT/docker/ejabberd/ejabberd.yml}"
SPOOL="${EJABBERD_INTEROP_SPOOL:-/tmp/omemo-ejabberd-spool}"
LOGS="${EJABBERD_INTEROP_LOGS:-/tmp/omemo-ejabberd-logs}"

mkdir -p "$SPOOL" "$LOGS"
if command -v sudo >/dev/null 2>&1; then
  sudo chown ejabberd:ejabberd "$SPOOL" "$LOGS" 2>/dev/null || true
fi

export EJABBERD_INTEROP_CONFIG="$CONFIG"
export EJABBERD_INTEROP_SPOOL="$SPOOL"
export EJABBERD_INTEROP_LOGS="$LOGS"
export EJABBERD_CONFIG_PATH="$CONFIG"
export EJABBERD_NODE="${EJABBERD_NODE:-ejabberd@localhost}"
export OMEMO_XMPP_SECURITY="${OMEMO_XMPP_SECURITY:-auto}"

run_ctl() {
  if command -v sudo >/dev/null 2>&1; then
    sudo -E ejabberdctl "$@"
  else
    ejabberdctl "$@"
  fi
}

install_interop_config() {
  # Debian/apt ejabberd reads /etc/ejabberd/ejabberd.yml — EJABBERD_CONFIG_PATH only affects ctl.
  if [[ -d /etc/ejabberd ]] && command -v sudo >/dev/null 2>&1; then
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
