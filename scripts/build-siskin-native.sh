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
python3 - <<'PY' "$MARTIN_OMEMO_PKG"
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    '.package(url: "https://github.com/tigase/Martin", branch: "devel")',
    '.package(path: "../martin")',
)
old_deps = 'dependencies: ["Martin", "libsignal"]'
new_deps = (
    'dependencies: [\n'
    '                .product(name: "Martin", package: "martin"),\n'
    '                .product(name: "libsignal", package: "libsignal"),\n'
    '            ]'
)
if old_deps in text:
    text = text.replace(old_deps, new_deps)
path.write_text(text)
PY

cd "$PKG"
swift build -c release
echo "Built: $PKG/.build/release/siskin-native-wire"
