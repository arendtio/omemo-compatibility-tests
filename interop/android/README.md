# Conversations Android crypto bridge (REAL vendor axolotl code)

This module compiles `vendor/conversations` axolotl sources and exposes a Gradle
task for wire-level interop. Requires Android SDK + `ANDROID_HOME`.

## Status

- Vendor verification: `verifyConversationsVendor` in `interop/clients/conversations`
- Full Robolectric wire bridge: requires `ANDROID_HOME` (see `settings.gradle.kts`)

When `ANDROID_HOME` is unset, the bridge project configures but wire tests skip.

## Goal

Encrypt/decrypt using `XmppAxolotlMessage` / `AxolotlService` from the checked-out
Conversations tree, with Smack used only as XMPP transport.

## Siskin / MartinOMEMO

Siskin IM uses Tigase Swift + MartinOMEMO on device. A Linux-native Swift bridge
would compile `vendor/MartinOMEMO` with TigaseSwift — tracked separately from the
Smack proxy in `interop/clients/siskin`.
