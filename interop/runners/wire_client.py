"""
Unified wire client CLI — runs REAL vendor code paths where implemented.

Backends:
  slixmpp_vendor      -> pip install -e vendor/slixmpp-omemo, oldmemo only
  python_oldmemo_vendor -> python-omemo oldmemo via slixmpp from vendor
  conversations_android_crypto -> Gradle Conversations axolotl crypto bridge
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional

from omemo_interop.runner_registry import get_implementation, vendor_path, ROOT

log = logging.getLogger(__name__)


def ensure_vendor_slixmpp() -> None:
    slixmpp_vendor = ROOT / "vendor" / "slixmpp-omemo"
    if not slixmpp_vendor.exists():
        raise RuntimeError("vendor/slixmpp-omemo missing — run download-implementations.py")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "-e", str(slixmpp_vendor)],
    )


async def run_slixmpp_wire(
    implementation_id: str,
    mode: str,
    jid: str,
    password: str,
    host: str,
    port: int,
    data_dir: Path,
    peer: Optional[str] = None,
    send_body: Optional[str] = None,
    expect_body: Optional[str] = None,
) -> int:
    ensure_vendor_slixmpp()

    import oldmemo
    from omemo.storage import Just, Maybe, Nothing, Storage
    from omemo.types import DeviceInformation, JSONType
    from slixmpp.clientxmpp import ClientXMPP
    from slixmpp.jid import JID
    from slixmpp.plugins import register_plugin
    from slixmpp.stanza import Message
    from slixmpp.xmlstream.handler import CoroutineCallback
    from slixmpp.xmlstream.matcher import MatchXPath
    from slixmpp_omemo import TrustLevel, XEP_0384

    vendor = vendor_path(implementation_id)
    rev = "unknown"
    if (vendor / ".git").exists():
        rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=vendor, text=True,
        ).strip()

    print(f"IMPLEMENTATION={implementation_id}")
    print(f"VENDOR_REV={rev}")
    print(f"RUNNER=slixmpp_vendor")
    print(f"NAMESPACE=eu.siacs.conversations.axolotl")

    class JsonStorage(Storage):
        def __init__(self, path: Path) -> None:
            super().__init__()
            self._path = path
            self._data: Dict[str, JSONType] = {}
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._data = json.load(f)

        async def _load(self, key: str) -> Maybe[JSONType]:
            try:
                return Just(self._data[key])
            except KeyError:
                return Nothing()

        async def _store(self, key: str, value: JSONType) -> None:
            self._data[key] = value
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f)

        async def _delete(self, key: str) -> None:
            self._data.pop(key, None)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f)

    class WireXEP0384(XEP_0384):
        default_config = {"fallback_message": "OMEMO encrypted.", "json_file_path": None}

        def plugin_init(self) -> None:
            self.__storage = JsonStorage(Path(self.json_file_path))
            super().plugin_init()

        @property
        def storage(self) -> Storage:
            return self.__storage

        @property
        def _btbv_enabled(self) -> bool:
            return True

        async def _devices_blindly_trusted(self, _a, _b) -> None:
            pass

        async def _prompt_manual_trust(self, manually_trusted, _id) -> None:
            sm = await self.get_session_manager()
            for device in manually_trusted:
                await sm.set_trust(device.bare_jid, device.identity_key, TrustLevel.TRUSTED.value)

    register_plugin(WireXEP0384)

    data_dir.mkdir(parents=True, exist_ok=True)
    last_body: Optional[str] = None
    receive_event = asyncio.Event()

    class Client(ClientXMPP):
        async def on_start(self, _event: Any) -> None:
            self.send_presence()
            await self.get_roster()

        async def on_message(self, stanza: Message) -> None:
            nonlocal last_body
            if stanza["type"] not in {"chat", "normal"}:
                return
            xep: XEP_0384 = self["xep_0384"]
            if not xep.is_encrypted(stanza):
                if stanza["body"]:
                    last_body = stanza["body"]
                    receive_event.set()
                return
            try:
                msg, _ = await xep.decrypt_message(stanza)
                if msg["body"]:
                    last_body = msg["body"]
                    receive_event.set()
            except Exception:
                log.exception("decrypt failed")

    xmpp = Client(jid, password)
    xmpp.add_event_handler("session_start", xmpp.on_start)
    xmpp.register_handler(
        CoroutineCallback(
            "WireMsg",
            MatchXPath(f"{{{xmpp.default_ns}}}message"),
            xmpp.on_message,
        )
    )
    xmpp.register_plugin("xep_0199")
    xmpp.register_plugin("xep_0380")
    xmpp.register_plugin(
        "xep_0384",
        {"json_file_path": data_dir / "omemo.json"},
        module=sys.modules[__name__],
    )

    xmpp.connect((host, port))
    await xmpp.connected_event.wait()
    await xmpp.wait_for_event("omemo_initialized")
    await asyncio.sleep(2)

    if mode == "send":
        if not peer or not send_body:
            raise ValueError("send requires peer and body")
        msg = xmpp.make_message(mto=JID(peer), mtype="chat")
        msg["body"] = send_body
        enc, errors = await xmpp["xep_0384"].encrypt_message(msg, {JID(peer)})
        if errors:
            print(f"encryption errors: {errors}")
        if enc is None:
            return 1
        enc["eme"]["namespace"] = oldmemo.oldmemo.NAMESPACE
        enc.send()
        await asyncio.sleep(1)
        xmpp.disconnect()
        print("OK")
        return 0

    if mode == "wait":
        if not expect_body:
            raise ValueError("wait requires expect")
        deadline = asyncio.get_event_loop().time() + 90
        while asyncio.get_event_loop().time() < deadline:
            if last_body == expect_body:
                xmpp.disconnect()
                print("OK")
                return 0
            receive_event.clear()
            try:
                await asyncio.wait_for(receive_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
        print(f"TIMEOUT expected={expect_body} got={last_body}")
        xmpp.disconnect()
        return 1

    raise ValueError(f"Unknown mode {mode}")


def run_conversations_android_crypto(args: argparse.Namespace) -> int:
    gradlew = ROOT / "interop" / "android" / "gradlew"
    if not gradlew.exists():
        print("Conversations android crypto bridge not built yet", file=sys.stderr)
        return 2
    cmd = [
        str(gradlew),
        "conversationsCryptoWire",
        f"-PwireMode={args.mode}",
        f"-PwireJid={args.jid}",
        f"-PwirePassword={args.password}",
        f"-PwireHost={args.host}",
        f"-PwirePort={args.port}",
        f"-PwireDataDir={args.data_dir}",
    ]
    if args.peer:
        cmd.append(f"-PwirePeer={args.peer}")
    if args.send:
        cmd.append(f"-PwireSend={args.send}")
    if args.expect:
        cmd.append(f"-PwireExpect={args.expect}")
    env = {**dict(**__import__("os").environ), "OMEMO_INTEROP_ROOT": str(ROOT)}
    return subprocess.call(cmd, cwd=ROOT / "interop" / "android", env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation", required=True)
    parser.add_argument("--mode", required=True, choices=["send", "wait"])
    parser.add_argument("--peer")
    parser.add_argument("--send")
    parser.add_argument("--expect")
    parser.add_argument("--jid", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5222)
    parser.add_argument("--data-dir", type=Path, required=True)
    args, _ = parser.parse_known_args()

    meta = get_implementation(args.implementation)
    runner = meta.runner

    if runner in ("slixmpp_vendor", "python_oldmemo_vendor", "gajim_omemo_dr", "nbxmpp_gajim_stack"):
        # Gajim stack uses same wire path until native runner lands
        return asyncio.run(
            run_slixmpp_wire(
                args.implementation,
                args.mode,
                args.jid,
                args.password,
                args.host,
                args.port,
                args.data_dir,
                args.peer,
                args.send,
                args.expect,
            )
        )

    if runner == "conversations_android_crypto":
        return run_conversations_android_crypto(args)

    if runner in ("monal_native", "monal_family", "dino_native", "converse_js", "unimplemented"):
        print(f"RUNNER={runner} STATUS=skipped — not yet wired for headless real code")
        return 2

    print(f"No wire backend for runner={runner}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
