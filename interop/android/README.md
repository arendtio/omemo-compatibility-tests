# Conversations Android crypto bridge (REAL vendor axolotl code)

This module compiles `vendor/conversations` axolotl sources and runs Robolectric
tests against `XmppAxolotlMessage`, `XmppAxolotlSession`, and `SQLiteAxolotlStore`.

Requires Android SDK + `ANDROID_HOME`.

## Proof status

| Client | Native crypto proof | Wire matrix |
|--------|---------------------|-------------|
| Conversations | **Green** — `conv-native` Robolectric tests | Smack proxy in `interop/clients`; native XMPP wire pending |
| Siskin IM | Audit + static tests; MartinOMEMO Swift needs macOS | Smack proxy (`monal_family` runner) |
| Monal | Audit + static tests; MLOMEMO/ObjC needs macOS | Smack proxy (`monal_native` runner) |

## Commands

```bash
export ANDROID_HOME=...
./scripts/build-conversations-native.sh
cd interop/android && ./gradlew :conv-native:conversationsCryptoWire -PwireMode=local_roundtrip
python3 scripts/run-native-wire-matrix.py --pair conversations-vs-conversations  # live XMPP
```

## Siskin / MartinOMEMO / Monal

Siskin uses Tigase Swift + MartinOMEMO on device. Monal uses MLOMEMO + SignalProtocolC.
Linux CI runs Smack proxies for wire interop; true Swift/ObjC native bridges are tracked
in `interop/monal-native/README.md` and require a macOS agent.
