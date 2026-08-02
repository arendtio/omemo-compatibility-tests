#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
if [[ -z "$ANDROID_HOME" ]]; then
  echo "ANDROID_HOME required to build Conversations native crypto bridge" >&2
  exit 1
fi
cd "$ROOT/interop/android"
./gradlew :conv-native:conversationsNativeCryptoTest --no-daemon -q
echo "Conversations vendor axolotl native tests passed"
