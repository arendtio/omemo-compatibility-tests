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

if [[ ! -d "$ROOT/vendor/martin" ]]; then
  echo "Cloning vendor/martin (Tigase Swift)..."
  git clone --depth 1 --branch devel https://github.com/tigase/Martin.git "$ROOT/vendor/martin"
fi

MARTIN_OMEMO_PKG="$ROOT/vendor/MartinOMEMO/Package.swift"
if grep -q 'github.com/tigase/Martin' "$MARTIN_OMEMO_PKG"; then
  sed -i.bak 's|\.package(url: "https://github.com/tigase/Martin", branch: "devel")|.package(path: "../martin")|' "$MARTIN_OMEMO_PKG"
fi

cd "$PKG"
swift build -c release
echo "Built: $PKG/.build/release/siskin-native-wire"
