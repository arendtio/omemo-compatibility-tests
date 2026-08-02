# Siskin / MartinOMEMO native wire (macOS)

Vendor-native wire client using pinned `vendor/MartinOMEMO` + `vendor/martin` (Tigase Swift).
This is Siskin's real crypto stack — not the Gradle Smack proxy.

## Build

```bash
python3 scripts/download-implementations.py \
  --ref martin_omemo=2e8435ec48dfb2a70ba414252cc1c8a3815bf24e
# martin is cloned automatically on first native build or:
git clone --depth 1 --branch devel https://github.com/tigase/Martin.git vendor/martin

./scripts/build-siskin-native.sh
```

Binary: `interop/siskin-native/.build/release/siskin-native-wire`

## Tests

```bash
cd interop/siskin-native && swift test
```

## Matrix

Pairs with `native_right: true` and `right: siskin_im` invoke this binary on macOS.

```bash
export OMEMO_XMPP_SECURITY=disabled
python3 scripts/run-interop-matrix.py --pair conversations-native-vs-siskin --native-conversations
```

Force Smack proxy (deprecated): `export OMEMO_FORCE_SMACK_PROXY=1`
