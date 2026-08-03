#!/usr/bin/env bash
# Build Monal MLOMEMO native wire on macOS (monalxmpp + headless MonalWire CLI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export OMEMO_INTEROP_ROOT="$ROOT"
OUT="$ROOT/interop/monal-native/build"
MONAL_DIR="$ROOT/vendor/monal/Monal"
MONAL_XCODE="$MONAL_DIR/Monal.xcodeproj"
MONAL_WORKSPACE="$MONAL_DIR/Monal.xcworkspace"
RUST_DIR="$ROOT/vendor/monal/rust"
RUST_PKG="$RUST_DIR/LibMonalRustSwiftBridge"
DERIVED="$OUT/DerivedData"
SDK=iphonesimulator

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

if ! command -v pod >/dev/null; then
  echo "CocoaPods (pod) required — install via gem install cocoapods" >&2
  exit 1
fi

if ! ruby -e 'require "xcodeproj"' 2>/dev/null; then
  echo "Installing xcodeproj gem for MonalWire target setup..."
  gem install xcodeproj --no-document
fi

ensure_rust_nightly() {
  if [[ -f "$HOME/.cargo/env" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
  fi
  if ! command -v rustc >/dev/null; then
    echo "Installing Rust nightly..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
  fi
  rustup toolchain install nightly 2>/dev/null || true
  rustup +nightly --version >/dev/null 2>&1 || rustup default nightly
}

echo "Installing MonalWire target into vendor Monal project..."
ruby "$ROOT/interop/monal-native/scripts/install-monal-wire-target.rb"

if [[ -f "$RUST_DIR/build-rust.sh" ]]; then
  echo "Building Monal rust bridge (LibMonalRustSwiftBridge)..."
  ensure_rust_nightly
  (cd "$RUST_DIR" && bash ./build-rust.sh)
fi

if [[ ! -d "$RUST_PKG" ]]; then
  echo "LibMonalRustSwiftBridge missing at $RUST_PKG — rust build required" >&2
  exit 1
fi

echo "pod install (Monal)..."
cd "$MONAL_DIR"
pod install

echo "Resolving Swift package dependencies..."
xcodebuild \
  -workspace "$MONAL_WORKSPACE" \
  -scheme monalxmpp \
  -configuration Debug \
  -sdk "$SDK" \
  -derivedDataPath "$DERIVED" \
  -resolvePackageDependencies \
  CODE_SIGNING_ALLOWED=NO \
  -quiet

echo "Building MonalWire (sdk=$SDK)..."
xcodebuild \
  -workspace "$MONAL_WORKSPACE" \
  -scheme MonalWire \
  -configuration Debug \
  -sdk "$SDK" \
  -derivedDataPath "$DERIVED" \
  CODE_SIGNING_ALLOWED=NO \
  -quiet

PRODUCTS="$DERIVED/Build/Products/Debug-${SDK}"
WIRE_BIN="$PRODUCTS/MonalWire.app/MonalWire"
if [[ ! -f "$WIRE_BIN" ]]; then
  WIRE_BIN="$PRODUCTS/MonalWire"
fi
if [[ ! -f "$WIRE_BIN" ]]; then
  echo "MonalWire binary missing under $PRODUCTS" >&2
  exit 1
fi

mkdir -p "$OUT/Frameworks"
cp -f "$WIRE_BIN" "$OUT/MonalWire"
chmod +x "$OUT/MonalWire"

# Stage simulator frameworks for DYLD_LIBRARY_PATH at runtime.
find "$PRODUCTS" -maxdepth 1 -name '*.framework' -exec cp -R {} "$OUT/Frameworks/" \;

echo "Built: $OUT/MonalWire"
echo "Frameworks: $OUT/Frameworks"
