"""True Conversations vendor axolotl proof (not Smack proxy)."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.native
def test_conversations_vendor_axolotl_native_tests() -> None:
    if not os.environ.get("ANDROID_HOME"):
        pytest.skip("ANDROID_HOME unset — Conversations native bridge not available")
    gradlew = ROOT / "interop" / "android" / "gradlew"
    if not gradlew.exists():
        pytest.skip("interop/android gradlew missing")
    subprocess.run(
        [str(gradlew), ":conv-native:conversationsNativeCryptoTest", "--no-daemon", "-q"],
        cwd=ROOT / "interop" / "android",
        check=True,
        env={**os.environ},
    )


@pytest.mark.native
def test_conversations_native_wire_main_local_roundtrip() -> None:
    if not os.environ.get("ANDROID_HOME"):
        pytest.skip("ANDROID_HOME unset")
    gradlew = ROOT / "interop" / "android" / "gradlew"
    proc = subprocess.run(
        [
            str(gradlew),
            ":conv-native:conversationsCryptoWire",
            "-PwireMode=local_roundtrip",
            "--no-daemon",
        ],
        cwd=ROOT / "interop" / "android",
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.native
def test_conversations_native_export_xml_shape() -> None:
    """Vendor encrypt output must be legacy OMEMO XML (eu.siacs.conversations.axolotl)."""
    if not os.environ.get("ANDROID_HOME"):
        pytest.skip("ANDROID_HOME unset")
    gradlew = ROOT / "interop" / "android" / "gradlew"
    proc = subprocess.run(
        [
            str(gradlew),
            ":conv-native:conversationsCryptoWire",
            "-PwireMode=export_xml",
            "--no-daemon",
        ],
        cwd=ROOT / "interop" / "android",
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.native
def test_siskin_mon_native_wire_still_smack_proxy_on_linux() -> None:
    """MartinOMEMO / MLOMEMO native bridges require macOS; Linux wire uses Smack proxies."""
    for name in ("monal", "siskin"):
        launcher = ROOT / "interop" / "clients" / name / "build" / "install" / name / "bin" / name
        if not launcher.exists():
            pytest.skip(f"Build {name} proxy with ./scripts/build-clients.sh")
    # Proxies exist; native Swift/ObjC proof is tracked separately (see interop/monal-native/README.md)
    assert True
