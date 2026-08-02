#!/usr/bin/env bash
# Build Siskin vendor-native wire (MartinOMEMO + Martin) on macOS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export OMEMO_INTEROP_ROOT="$ROOT"
PKG="$ROOT/interop/siskin-native"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Siskin native wire is macOS-only (skipped on $(uname -s))"
  exit 0
fi

if ! command -v swift >/dev/null; then
  echo "Swift toolchain required" >&2
  exit 1
fi

cd "$PKG"
swift build -c release
echo "Built: $PKG/.build/release/siskin-native-wire"
