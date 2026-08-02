# Monal native wire bridge (MLOMEMO / SignalProtocolC)

## Status

**Vendor-native wire on macOS.** Monal's OMEMO stack is Objective-C (`MLOMEMO.m`) inside the
`monalxmpp` framework (SignalProtocolC fork). Linux wire uses the deprecated Smack proxy unless
you force native macOS builds elsewhere.

## Build

```bash
python3 scripts/download-implementations.py --ref monal=c69bd05ac245f8ba1e206e4185a3ca92607ecaa8
./scripts/build-monal-native.sh
```

Produces:

- `interop/monal-native/build/DerivedData` — `monalxmpp` framework build
- `interop/monal-native/build/MonalWire` — headless CLI (when `MonalWire.xcodeproj` is present)

## Wire matrix

On macOS, pairs with `native_right: true` and `right: monal` use `MonalWire` instead of the
Gradle Smack proxy. Set `OMEMO_FORCE_SMACK_PROXY=1` to keep the old proxy for comparison.

Example:

```bash
export OMEMO_XMPP_SECURITY=disabled
python3 scripts/run-interop-matrix.py --pair conversations-native-vs-monal --native-conversations
```

## MonalWire CLI (in progress)

`interop/monal-native/MonalWire/` will host a thin ObjC CLI similar to Conversations
`NativeWireClient`: vendor `MLOMEMO` crypto + Smack or Martin transport. The build script already
compiles `monalxmpp` from `vendor/monal/Monal/Monal.xcodeproj`.

## Removing Smack proxy

Once `MonalWire` is green in CI and cross-wire matrix passes against Conversations native and
Siskin native, delete or gate `interop/clients/monal` and remove `deprecated_smack_proxy` pairs
from `config/interop-matrix.yaml`.
