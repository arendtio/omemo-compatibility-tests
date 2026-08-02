#!/usr/bin/env bash
# Build headless legacy OMEMO wire client runners (Conversations + Monal vendor bindings).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export OMEMO_INTEROP_ROOT="$ROOT"
cd "$ROOT/interop/clients"
./gradlew :conversations:installDist :monal:installDist -q
echo "Clients installed under interop/clients/*/build/install/"
