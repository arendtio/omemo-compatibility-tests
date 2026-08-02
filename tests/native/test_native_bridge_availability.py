"""Document native crypto bridge availability (real vendor code vs Smack proxies)."""

import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.native
def test_conversations_android_bridge_requires_android_home() -> None:
    gradlew = ROOT / "interop" / "android" / "gradlew"
    if not gradlew.exists():
        pytest.skip("interop/android gradlew not present")
    if not os.environ.get("ANDROID_HOME"):
        pytest.skip("ANDROID_HOME unset — Conversations axolotl bridge not built in CI")


@pytest.mark.native
def test_monal_gradle_proxy_binary_exists() -> None:
    launcher = ROOT / "interop" / "clients" / "monal" / "build" / "install" / "monal" / "bin" / "monal"
    if not launcher.exists():
        pytest.skip("Build monal Gradle proxy with ./scripts/build-clients.sh")
    assert launcher.is_file()


@pytest.mark.native
def test_siskin_gradle_proxy_binary_exists() -> None:
    launcher = ROOT / "interop" / "clients" / "siskin" / "build" / "install" / "siskin" / "bin" / "siskin"
    if not launcher.exists():
        pytest.skip("Build siskin Gradle proxy with ./scripts/build-clients.sh")
    assert launcher.is_file()


@pytest.mark.native
def test_martin_omemo_native_bridge_not_on_linux() -> None:
    """MartinOMEMO Swift bridge is not wired; Siskin wire uses Smack proxy."""
    swift = shutil.which("swift")
    if swift and (ROOT / "vendor" / "MartinOMEMO").exists():
        pytest.skip("Swift present but MartinOMEMO native bridge not implemented")
    pytest.skip("MartinOMEMO native bridge not available on this host")
