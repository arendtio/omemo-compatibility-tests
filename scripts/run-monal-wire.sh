#!/usr/bin/env bash
# Run MonalWire (iphonesimulator build) inside a booted iOS Simulator.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/interop/monal-native/build/MonalWire.app"
BIN="$APP/MonalWire"
FRAMEWORKS="$APP/Frameworks"
if [[ ! -f "$BIN" ]]; then
  BIN="$ROOT/interop/monal-native/build/MonalWire"
  FRAMEWORKS="$ROOT/interop/monal-native/build/Frameworks"
fi

if [[ ! -f "$BIN" ]]; then
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
  echo "Booting simulator $udid" >&2
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

# simctl spawn has no /usr/bin/env in the simulator; SIMCTL_CHILD_* passes env to child.
export SIMCTL_CHILD_OOMEMO_INTEROP_ROOT="$OMEMO_INTEROP_ROOT"
export SIMCTL_CHILD_OOMEMO_XMPP_SECURITY="$OMEMO_XMPP_SECURITY"
export SIMCTL_CHILD_MONAL_VENDOR_REV="${MONAL_VENDOR_REV:-}"
if [[ -n "${MONAL_WIRE_AWAIT_TIMEOUT:-}" ]]; then
  export SIMCTL_CHILD_MONAL_WIRE_AWAIT_TIMEOUT="$MONAL_WIRE_AWAIT_TIMEOUT"
fi
if [[ -d "$FRAMEWORKS" ]]; then
  export SIMCTL_CHILD_DYLD_FRAMEWORK_PATH="$FRAMEWORKS${DYLD_FRAMEWORK_PATH:+:$DYLD_FRAMEWORK_PATH}"
fi

echo "MonalWire: spawning $BIN in iOS Simulator" >&2

exec xcrun simctl spawn booted "$BIN" "$@"
