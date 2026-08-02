# Monal native wire bridge (MLOMEMO / SignalProtocolC)

## Status

**Not available on Linux CI.** Monal's OMEMO stack is Objective-C (`MLOMEMO.m`)
linked against Monal's SignalProtocolC fork. Headless wire tests on Linux use the
Gradle `monal` module, which is a **Smack + libsignal-java proxy** (same as
Conversations/Siskin Gradle runners).

## macOS path (planned)

1. Build Monal's SignalProtocolC fork from `vendor/monal`.
2. Expose encrypt/decrypt via a small ObjC CLI or XCTest host.
3. Wire `monal_native` in `interop/runners/wire_client.py` to that binary.
4. Use Smack (Java) or slixmpp (Python) for XMPP transport only.

## Current proxy

Until the native bridge lands, `monal_native` routes to the Gradle Smack proxy
when `interop/clients/monal/build/install/monal/bin/monal` exists.
