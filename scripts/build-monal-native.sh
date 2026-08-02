#!/usr/bin/env bash
# Build Monal MLOMEMO native wire on macOS (monalxmpp + headless CLI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export OMEMO_INTEROP_ROOT="$ROOT"
OUT="$ROOT/interop/monal-native/build"
MONAL_XCODE="$ROOT/vendor/monal/Monal/Monal.xcodeproj"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Monal native wire is macOS-only (skipped on $(uname -s))"
  exit 0
fi

if ! command -v xcodebuild >/dev/null; then
  echo "Xcode / xcodebuild required for Monal native wire" >&2
  exit 1
fi

if [[ ! -d "$MONAL_XCODE" ]]; then
  echo "vendor/monal missing — run scripts/download-implementations.py" >&2
  exit 1
fi

mkdir -p "$OUT"
echo "Building monalxmpp framework from vendor Monal..."
xcodebuild \
  -project "$MONAL_XCODE" \
  -scheme monalxmpp \
  -configuration Debug \
  -derivedDataPath "$OUT/DerivedData" \
  CODE_SIGNING_ALLOWED=NO \
  -quiet

WIRE_DIR="$ROOT/interop/monal-native/MonalWire"
if [[ -f "$WIRE_DIR/MonalWire.xcodeproj/project.pbxproj" ]]; then
  echo "Building MonalWire CLI..."
  xcodebuild \
    -project "$WIRE_DIR/MonalWire.xcodeproj" \
    -scheme MonalWire \
    -configuration Debug \
    -derivedDataPath "$OUT/DerivedData" \
    CONFIGURATION_BUILD_DIR="$OUT" \
    CODE_SIGNING_ALLOWED=NO \
    -quiet
  echo "Built: $OUT/MonalWire"
else
  echo "MonalWire Xcode project not present yet — monalxmpp built; wire CLI pending."
  echo "See interop/monal-native/README.md"
fi
