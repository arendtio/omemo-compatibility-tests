# Conversations Android crypto bridge (REAL vendor axolotl code)

This module compiles `vendor/conversations` axolotl sources and exposes a Gradle
task for wire-level interop. Requires Android SDK + `ANDROID_HOME`.

## Status

- Vendor verification: `verifyConversationsVendor` in `interop/clients/conversations`
- Full Robolectric wire bridge: requires `ANDROID_HOME` (CI uses `android-actions/setup-android`)

When the bridge is unavailable, wire tests for `conversations` skip with a clear message.

## Goal

Encrypt/decrypt using `XmppAxolotlMessage` / `AxolotlService` from the checked-out
Conversations tree, with Smack used only as XMPP transport.
