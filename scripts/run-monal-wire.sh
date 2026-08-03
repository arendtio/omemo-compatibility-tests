#!/usr/bin/env bash
# Run MonalWire (iphonesimulator build) inside a booted iOS Simulator.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/interop/monal-native/build/MonalWire"
FRAMEWORKS="$ROOT/interop/monal-native/build/Frameworks"

if [[ ! -x "$BIN" ]]; then
  echo "MonalWire missing: $BIN" >&2
  exit 2
fi

boot_simulator() {
  if xcrun simctl list devices booted 2>/dev/null | grep -q Booted; then
    return 0
  fi
  local udid
  udid="$(xcrun simctl list devices available -j | python3 -c "
import json, sys
data = json.load(sys.stdin)
for runtime in sorted(data.get('devices', {}).keys(), reverse=True):
    if 'iOS' not in runtime:
        continue
    for dev in data['devices'][runtime]:
        if dev.get('isAvailable') and 'iPhone' in dev.get('name', ''):
            print(dev['udid'])
            sys.exit(0)
sys.exit(1)
")"
  echo "Booting simulator $udid"
  xcrun simctl boot "$udid" 2>/dev/null || true
  for _ in $(seq 1 30); do
    if xcrun simctl list devices booted 2>/dev/null | grep -q Booted; then
      return 0
    fi
    sleep 1
  done
  echo "No booted iOS Simulator" >&2
  exit 1
}

boot_simulator

export OMEMO_INTEROP_ROOT="${OMEMO_INTEROP_ROOT:-$ROOT}"
export OMEMO_XMPP_SECURITY="${OMEMO_XMPP_SECURITY:-auto}"
export DYLD_FRAMEWORK_PATH="${FRAMEWORKS}${DYLD_FRAMEWORK_PATH:+:$DYLD_FRAMEWORK_PATH}"

echo "MonalWire: spawning in iOS Simulator" >&2

exec xcrun simctl spawn booted env \
  OMEMO_INTEROP_ROOT="$OMEMO_INTEROP_ROOT" \
  OMEMO_XMPP_SECURITY="$OMEMO_XMPP_SECURITY" \
  MONAL_VENDOR_REV="${MONAL_VENDOR_REV:-}" \
  DYLD_FRAMEWORK_PATH="$DYLD_FRAMEWORK_PATH" \
  "$BIN" "$@"
