# Legacy OMEMO client wire runners

Headless JVM clients for `eu.siacs.conversations.axolotl` interop testing.

## conversations

- Binds to `vendor/conversations` (Codeberg `iNPUTmice/Conversations`)
- Verifies `crypto/axolotl/XmppAxolotlMessage.java` exists at checkout
- Uses Smack + signal-protocol-java (same stack as Conversations)

## monal

- Binds to `vendor/monal`
- Verifies `Monal/Classes/MLOMEMO.m` exists at checkout
- Uses legacy axolotl namespace (Monal does not use OMEMO 2 on wire today)

## Build

```bash
export OMEMO_INTEROP_ROOT=/path/to/repo
./gradlew :conversations:installDist :monal:installDist
```

Binaries: `conversations/build/install/conversations/bin/conversations` and `monal/...`.

## Version pinning

Check out client versions before building:

```bash
python3 scripts/download-implementations.py --ref conversations=2.20.1 --ref monal=main
./scripts/build-clients.sh
```

Each run prints `VENDOR_REV=` from the vendor git tree.
