#!/usr/bin/env python3
"""Run legacy OMEMO client interop matrix over ejabberd."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "config" / "interop-matrix.yaml"
CLIENTS_DIR = ROOT / "interop" / "clients"

from omemo_interop.native_wire import popen_native_wire, run_native_wire
from omemo_interop.siskin_native_wire import (
    build_siskin_native,
    native_macos_wire_enabled,
    popen_siskin_native_wire,
    run_siskin_native_wire,
    siskin_native_binary,
)
from omemo_interop.monal_native_wire import (
    build_monal_native,
    monal_native_binary,
    popen_monal_native_wire,
    run_monal_native_wire,
)


def run(cmd: list[str], env: dict | None = None, timeout: int = 120, cwd: Path | None = None) -> int:
    print(f"$ {' '.join(cmd)}")
    merged = os.environ.copy()
    if env:
        merged.update(env)
    merged["OMEMO_INTEROP_ROOT"] = str(ROOT)
    try:
        return subprocess.call(cmd, cwd=cwd or ROOT, env=merged, timeout=timeout)
    except subprocess.TimeoutExpired:
        print("TIMEOUT")
        return 124


def gradle_module(client_id: str, matrix: dict) -> str:
    client_cfg = matrix.get("clients", {}).get(client_id, {})
    return client_cfg.get("gradle_module", client_id)


def gradle_client_task(module: str) -> str:
    return f":{module}:installDist"


def client_launcher(client_id: str, matrix: dict) -> Path:
    module = gradle_module(client_id, matrix)
    return CLIENTS_DIR / module / "build" / "install" / module / "bin" / module


def build_clients(client_ids: set[str], matrix: dict) -> int:
    modules = {gradle_module(c, matrix) for c in client_ids}
    tasks = [gradle_client_task(m) for m in sorted(modules)]
    gradlew = CLIENTS_DIR / "gradlew"
    if not gradlew.exists():
        print("Gradle wrapper missing in interop/clients", file=sys.stderr)
        return 1
    return run([str(gradlew), *tasks, "-q"], cwd=CLIENTS_DIR)


def wire_env() -> dict[str, str]:
    return {
        **os.environ,
        "OMEMO_INTEROP_ROOT": str(ROOT),
        "OMEMO_XMPP_SECURITY": os.environ.get("OMEMO_XMPP_SECURITY", "auto"),
    }


def wants_native_client(
    client_id: str,
    pair: dict,
    as_matrix_left: bool,
    native_conversations: bool,
) -> bool:
    """Pair yaml native_left/native_right selects vendor wire per side."""
    if as_matrix_left and client_id == pair.get("left") and pair.get("native_left"):
        return True
    if not as_matrix_left and client_id == pair.get("right") and pair.get("native_right"):
        return True
    if native_conversations and client_id == "conversations" and as_matrix_left:
        return True
    return False


def use_native_wire(
    client_id: str,
    pair: dict,
    as_matrix_left: bool,
    native_conversations: bool,
) -> bool:
    if os.environ.get("OMEMO_FORCE_SMACK_PROXY") == "1":
        return False
    if not wants_native_client(client_id, pair, as_matrix_left, native_conversations):
        return False
    if client_id == "conversations":
        return True
    if client_id == "siskin_im" and native_macos_wire_enabled():
        return siskin_native_binary().exists()
    if client_id == "monal" and native_macos_wire_enabled():
        return monal_native_binary().exists()
    return False


def wait_boot(
    client_id: str,
    pair: dict,
    native_conversations: bool,
    as_matrix_left: bool,
    short: bool = False,
) -> None:
    if short and not use_native_wire(client_id, pair, as_matrix_left, native_conversations):
        time.sleep(1)
    elif client_id == "conversations" and use_native_wire(client_id, pair, as_matrix_left, native_conversations):
        time.sleep(35)
    elif use_native_wire(client_id, pair, as_matrix_left, native_conversations):
        # wait_native_wire_process replaces fixed sleep for spawned receivers.
        time.sleep(5)
    else:
        time.sleep(12)


NATIVE_WIRE_WAIT_TIMEOUT = 600


def wait_after_spawn_wait(
    client_id: str,
    matrix: dict,
    pair: dict,
    mode: str,
    native_conversations: bool,
    as_matrix_left: bool,
    proc: subprocess.Popen,
    data_dir: Path,
) -> int | None:
    """Boot a spawned wire client; return exit code on early failure."""
    if mode not in ("wait", "hold-send"):
        wait_boot(client_id, pair, native_conversations, as_matrix_left)
        return None
    if (
        client_id in ("siskin_im", "monal", "conversations")
        and use_native_wire(client_id, pair, as_matrix_left, native_conversations)
    ):
        early = wait_native_wire_process(client_id, proc, data_dir)
        if early is not None:
            dump_wire_log(data_dir)
            return early
        if not (data_dir / "wire-ready").is_file():
            dump_wire_log(data_dir)
            return 1
    else:
        wait_boot(client_id, pair, native_conversations, as_matrix_left)
    if proc.poll() is not None:
        dump_wire_log(data_dir)
        return proc.poll() or 1
    return None


def wait_native_wire_process(
    client_id: str,
    proc: subprocess.Popen,
    data_dir: Path,
    timeout: int = NATIVE_WIRE_WAIT_TIMEOUT,
) -> int | None:
    """Wait until wire-ready marker or child exit. Returns exit code if child died."""
    ready = data_dir / "wire-ready"
    if ready.exists():
        ready.unlink()
    for elapsed in range(timeout):
        rc = proc.poll()
        if rc is not None:
            print(f"wait_native: {client_id} exited early with {rc} after {elapsed}s", flush=True)
            return rc
        if ready.is_file():
            print(f"wait_native: {client_id} ready after {elapsed}s", flush=True)
            return None
        time.sleep(1)
    rc = proc.poll()
    if rc is not None:
        return rc
    print(f"wait_native: {client_id} not ready after {timeout}s", flush=True)
    return None


def dump_wire_log(data_dir: Path) -> None:
    for name in ("wire-popen.log", "wire-debug.log"):
        log = data_dir / name
        if log.is_file():
            print(f"--- wire log {log} ---", flush=True)
            print(log.read_text(encoding="utf-8", errors="replace"), flush=True)


def prewarm_omemo_publish(
    client_id: str,
    matrix: dict,
    pair: dict,
    jid: str,
    password: str,
    native_conversations: bool,
    as_matrix_left: bool,
    data_dir: Path,
) -> int:
    """Connect briefly so PEP device list is on the server before the peer waits."""
    print(f"prewarm: {client_id} OMEMO publish for {jid}", flush=True)
    return invoke_client(
        client_id,
        matrix,
        pair,
        "publish",
        jid,
        password,
        native_conversations,
        as_matrix_left,
        data_dir=data_dir,
    )


def prewarm_conversations_native_wire() -> int:
    """Compile Conversations vendor + Robolectric wire once so scenario sends stay fast."""
    if not os.environ.get("ANDROID_HOME"):
        return 0
    d = ROOT / "tmp" / "wire-prewarm"
    d.mkdir(parents=True, exist_ok=True)
    print("prewarm: conversations native wire (local_roundtrip)", flush=True)
    return run_native_wire(
        "local_roundtrip",
        "alice@localhost",
        "alicepass",
        d,
        timeout=600,
    )


def invoke_client(
    client_id: str,
    matrix: dict,
    pair: dict,
    mode: str,
    jid: str,
    password: str,
    native_conversations: bool,
    as_matrix_left: bool,
    peer: str | None = None,
    send: str | None = None,
    expect: str | None = None,
    data_dir: Path | None = None,
) -> int:
    d = data_dir or ROOT / "tmp" / "wire-data" / client_id / jid.split("@")[0]
    d.mkdir(parents=True, exist_ok=True)
    if use_native_wire(client_id, pair, as_matrix_left, native_conversations):
        print(f"NATIVE_WIRE client={client_id} mode={mode} jid={jid}", flush=True)
        if client_id == "conversations":
            return run_native_wire(
                mode, jid, password, d, peer=peer, send=send, expect=expect,
            )
        if client_id == "siskin_im":
            return run_siskin_native_wire(
                mode, jid, password, d, peer=peer, send=send, expect=expect,
            )
        if client_id == "monal":
            return run_monal_native_wire(
                mode, jid, password, d, peer=peer, send=send, expect=expect,
            )
    return run_client(
        client_id, matrix, mode, jid, password, peer, send, expect, d,
    )


def spawn_client(
    client_id: str,
    matrix: dict,
    pair: dict,
    mode: str,
    jid: str,
    password: str,
    native_conversations: bool,
    as_matrix_left: bool,
    peer: str | None = None,
    send: str | None = None,
    expect: str | None = None,
    data_dir: Path | None = None,
) -> subprocess.Popen:
    d = data_dir or ROOT / "tmp" / "wire-data" / client_id / jid.split("@")[0]
    d.mkdir(parents=True, exist_ok=True)
    if use_native_wire(client_id, pair, as_matrix_left, native_conversations):
        print(f"NATIVE_WIRE client={client_id} mode={mode} jid={jid}", flush=True)
        if client_id == "conversations":
            return popen_native_wire(
                mode, jid, password, d, peer=peer, send=send, expect=expect,
            )
        if client_id == "siskin_im":
            return popen_siskin_native_wire(
                mode, jid, password, d, peer=peer, send=send, expect=expect,
            )
        if client_id == "monal":
            return popen_monal_native_wire(
                mode, jid, password, d, peer=peer, send=send, expect=expect,
            )
    launcher = client_launcher(client_id, matrix)
    args = [
        str(launcher),
        "--mode", mode,
        *(["--peer", peer] if peer else []),
        *(["--send", send] if send else []),
        *(["--expect", expect] if expect else []),
        "--",
        "--jid", jid,
        "--password", password,
        "--host", "127.0.0.1",
        "--port", "5222",
        "--data-dir", str(d),
    ]
    return subprocess.Popen(args, cwd=ROOT, env=wire_env())


def run_client(
    client_id: str,
    matrix: dict,
    mode: str,
    jid: str,
    password: str,
    peer: str | None = None,
    send: str | None = None,
    expect: str | None = None,
    data_dir: Path | None = None,
) -> int:
    launcher = client_launcher(client_id, matrix)
    if not launcher.exists():
        print(f"Client binary missing: {launcher}", file=sys.stderr)
        return 1

    d = data_dir or ROOT / "tmp" / "wire-data" / client_id / jid.split("@")[0]
    d.mkdir(parents=True, exist_ok=True)

    args = [
        str(launcher),
        "--mode", mode,
        "--",
        "--jid", jid,
        "--password", password,
        "--host", "127.0.0.1",
        "--port", "5222",
        "--data-dir", str(d),
    ]
    if peer:
        args = [
            str(launcher),
            "--mode", mode,
            "--peer", peer,
            *(["--send", send] if send else []),
            *(["--expect", expect] if expect else []),
            "--",
            "--jid", jid,
            "--password", password,
            "--host", "127.0.0.1",
            "--port", "5222",
            "--data-dir", str(d),
        ]
    return run(args, timeout=90)


def scenario_bob_sends_alice_replies(
    left: str, right: str, matrix: dict, pair: dict, native_conversations: bool = False,
) -> int:
    """Bob (right) initiates; Alice (left) replies — tests reverse prekey handshake."""
    alice_jid = "alice@localhost"
    bob_jid = "bob@localhost"
    tag = f"{right}-to-{left}"

    bob_data = ROOT / "tmp" / "wire-data" / right / "bob"
    rc = prewarm_omemo_publish(
        right, matrix, pair, bob_jid, "bobpass", native_conversations, False, bob_data,
    )
    if rc != 0:
        return rc

    alice_data = ROOT / "tmp" / "wire-data" / left / "alice"
    alice_proc = spawn_client(
        left, matrix, pair, "wait", alice_jid, "alicepass", native_conversations, True,
        peer=bob_jid,
        expect=f"hello-{tag}",
        data_dir=alice_data,
    )
    rc = wait_after_spawn_wait(
        left, matrix, pair, "wait", native_conversations, True, alice_proc, alice_data,
    )
    if rc is not None:
        return rc

    rc = invoke_client(
        right, matrix, pair, "send", bob_jid, "bobpass", native_conversations, False,
        peer=alice_jid,
        send=f"hello-{tag}",
        data_dir=ROOT / "tmp" / "wire-data" / right / "bob",
    )
    if rc != 0:
        alice_proc.kill()
        return rc

    try:
        alice_rc = alice_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        alice_proc.kill()
        return 1
    if alice_rc != 0:
        return alice_rc

    rc = prewarm_omemo_publish(
        left, matrix, pair, alice_jid, "alicepass", native_conversations, True, alice_data,
    )
    if rc != 0:
        return rc

    bob_proc = spawn_client(
        right, matrix, pair, "wait", bob_jid, "bobpass", native_conversations, False,
        peer=alice_jid,
        expect=f"reply-{tag}",
        data_dir=bob_data,
    )
    rc = wait_after_spawn_wait(
        right, matrix, pair, "wait", native_conversations, False, bob_proc, bob_data,
    )
    if rc is not None:
        return rc
    time.sleep(15)
    rc = invoke_client(
        left, matrix, pair, "send", alice_jid, "alicepass", native_conversations, True,
        peer=bob_jid,
        send=f"reply-{tag}",
        data_dir=ROOT / "tmp" / "wire-data" / left / "alice",
    )
    if rc != 0:
        bob_proc.kill()
        return rc
    try:
        return bob_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        bob_proc.kill()
        return 1


def scenario_unicode_body_roundtrip(
    left: str, right: str, matrix: dict, pair: dict, native_conversations: bool = False,
) -> int:
    alice_jid = "alice@localhost"
    bob_jid = "bob@localhost"
    tag = f"{left}-to-{right}"
    hello = f"hello-unicode-🧪-{tag}"
    reply = f"reply-unicode-🧪-{tag}"

    alice_data = ROOT / "tmp" / "wire-data" / left / "alice"
    bob_data = ROOT / "tmp" / "wire-data" / right / "bob"

    alice_proc = spawn_client(
        left, matrix, pair, "hold-send", alice_jid, "alicepass", native_conversations, True,
        peer=bob_jid,
        send=hello,
        data_dir=alice_data,
    )
    rc = wait_after_spawn_wait(
        left, matrix, pair, "hold-send", native_conversations, True, alice_proc, alice_data,
    )
    if rc is not None:
        return rc

    bob_proc = spawn_client(
        right, matrix, pair, "wait", bob_jid, "bobpass", native_conversations, False,
        peer=alice_jid,
        expect=hello,
        data_dir=bob_data,
    )
    rc = wait_after_spawn_wait(
        right, matrix, pair, "wait", native_conversations, False, bob_proc, bob_data,
    )
    if rc is not None:
        alice_proc.kill()
        return rc

    signal_hold_send(alice_data)
    try:
        alice_rc = alice_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        alice_proc.kill()
        bob_proc.kill()
        return 1
    if alice_rc != 0:
        bob_proc.kill()
        dump_wire_log(alice_data)
        return alice_rc

    try:
        bob_rc = bob_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        bob_proc.kill()
        return 1
    if bob_rc != 0:
        dump_wire_log(bob_data)
        return bob_rc

    bob_proc = spawn_client(
        right, matrix, pair, "hold-send", bob_jid, "bobpass", native_conversations, False,
        peer=alice_jid,
        send=reply,
        data_dir=bob_data,
    )
    rc = wait_after_spawn_wait(
        right, matrix, pair, "hold-send", native_conversations, False, bob_proc, bob_data,
    )
    if rc is not None:
        return rc

    alice_proc = spawn_client(
        left, matrix, pair, "wait", alice_jid, "alicepass", native_conversations, True,
        peer=bob_jid,
        expect=reply,
        data_dir=alice_data,
    )
    rc = wait_after_spawn_wait(
        left, matrix, pair, "wait", native_conversations, True, alice_proc, alice_data,
    )
    if rc is not None:
        bob_proc.kill()
        return rc

    signal_hold_send(bob_data)
    try:
        bob_rc = bob_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        bob_proc.kill()
        alice_proc.kill()
        return 1
    if bob_rc != 0:
        alice_proc.kill()
        dump_wire_log(bob_data)
        return bob_rc
    try:
        return alice_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        alice_proc.kill()
        return 1


def scenario_repeated_session_messages(
    left: str, right: str, matrix: dict, pair: dict, native_conversations: bool = False,
) -> int:
    """Two roundtrips on the same OMEMO stores — second leg uses established sessions."""
    for n in (1, 2):
        rc = scenario_alice_sends_bob_replies(left, right, matrix, pair, native_conversations)
        if rc != 0:
            print(f"Repeated session leg {n} failed")
            return rc
    return 0


SCENARIO_HANDLERS = {
    "alice_sends_bob_replies": None,  # defined below
    "cross_session_roundtrip": None,
    "bob_sends_alice_replies": scenario_bob_sends_alice_replies,
    "unicode_body_roundtrip": scenario_unicode_body_roundtrip,
    "repeated_session_messages": scenario_repeated_session_messages,
}


def signal_hold_send(data_dir: Path) -> None:
    """Tell a hold-send wire client to encrypt and send."""
    (data_dir / "wire-send-now").write_text("go", encoding="utf-8")


def scenario_alice_sends_bob_replies(
    left: str, right: str, matrix: dict, pair: dict, native_conversations: bool = False,
) -> int:
    alice_jid = "alice@localhost"
    bob_jid = "bob@localhost"
    tag = f"{left}-to-{right}"

    alice_data = ROOT / "tmp" / "wire-data" / left / "alice"
    bob_data = ROOT / "tmp" / "wire-data" / right / "bob"

    alice_proc = spawn_client(
        left, matrix, pair, "hold-send", alice_jid, "alicepass", native_conversations, True,
        peer=bob_jid,
        send=f"hello-{tag}",
        data_dir=alice_data,
    )
    rc = wait_after_spawn_wait(
        left, matrix, pair, "hold-send", native_conversations, True, alice_proc, alice_data,
    )
    if rc is not None:
        return rc

    bob_proc = spawn_client(
        right, matrix, pair, "wait", bob_jid, "bobpass", native_conversations, False,
        peer=alice_jid,
        expect=f"hello-{tag}",
        data_dir=bob_data,
    )
    rc = wait_after_spawn_wait(
        right, matrix, pair, "wait", native_conversations, False, bob_proc, bob_data,
    )
    if rc is not None:
        alice_proc.kill()
        return rc

    signal_hold_send(alice_data)
    try:
        alice_rc = alice_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        alice_proc.kill()
        bob_proc.kill()
        return 1
    if alice_rc != 0:
        bob_proc.kill()
        dump_wire_log(alice_data)
        return alice_rc

    try:
        bob_rc = bob_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        bob_proc.kill()
        return 1
    if bob_rc != 0:
        dump_wire_log(bob_data)
        return bob_rc

    bob_proc = spawn_client(
        right, matrix, pair, "hold-send", bob_jid, "bobpass", native_conversations, False,
        peer=alice_jid,
        send=f"reply-{tag}",
        data_dir=bob_data,
    )
    rc = wait_after_spawn_wait(
        right, matrix, pair, "hold-send", native_conversations, False, bob_proc, bob_data,
    )
    if rc is not None:
        return rc

    alice_proc = spawn_client(
        left, matrix, pair, "wait", alice_jid, "alicepass", native_conversations, True,
        peer=bob_jid,
        expect=f"reply-{tag}",
        data_dir=alice_data,
    )
    rc = wait_after_spawn_wait(
        left, matrix, pair, "wait", native_conversations, True, alice_proc, alice_data,
    )
    if rc is not None:
        bob_proc.kill()
        return rc

    signal_hold_send(bob_data)
    try:
        bob_rc = bob_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        bob_proc.kill()
        alice_proc.kill()
        return 1
    if bob_rc != 0:
        alice_proc.kill()
        dump_wire_log(bob_data)
        return bob_rc
    try:
        return alice_proc.wait(timeout=NATIVE_WIRE_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        alice_proc.kill()
        return 1


SCENARIO_HANDLERS["alice_sends_bob_replies"] = scenario_alice_sends_bob_replies
SCENARIO_HANDLERS["cross_session_roundtrip"] = scenario_alice_sends_bob_replies


def ejabberd_interop_env() -> dict[str, str]:
    env = os.environ.copy()
    config = env.get(
        "EJABBERD_INTEROP_CONFIG",
        str(ROOT / "docker" / "ejabberd" / "ejabberd.yml"),
    )
    spool = env.get("EJABBERD_INTEROP_SPOOL", "/tmp/omemo-ejabberd-spool")
    logs = env.get("EJABBERD_INTEROP_LOGS", "/tmp/omemo-ejabberd-logs")
    home = env.get("EJABBERD_INTEROP_HOME", "/tmp/omemo-ejabberd-home")
    env["EJABBERD_INTEROP_CONFIG"] = config
    env["EJABBERD_CONFIG_PATH"] = config
    env["EJABBERD_INTEROP_SPOOL"] = spool
    env["EJABBERD_INTEROP_LOGS"] = logs
    env["EJABBERD_INTEROP_HOME"] = home
    env["SPOOL_DIR"] = spool
    env["LOGS_DIR"] = logs
    env["HOME"] = home
    env.setdefault("EJABBERD_NODE", "ejabberd@localhost")
    if os.name == "posix" and os.uname().sysname == "Darwin":
        env["PATH"] = "/opt/homebrew/sbin:/usr/local/sbin:" + env.get("PATH", "")
    for key, value in env.items():
        os.environ[key] = value
    return env


def ejabberd_listening(host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, 5222), timeout=2):
            return True
    except OSError:
        return False


def ejabberd_simulator_reachable() -> bool:
    """True when ejabberd accepts C2S on the Mac LAN IP (needed for iOS Simulator Monal wire)."""
    if os.name != "posix" or os.uname().sysname != "Darwin":
        return True
    try:
        ip = subprocess.check_output(["ipconfig", "getifaddr", "en0"], text=True).strip()
        if ip and ejabberd_listening(ip):
            return True
    except (subprocess.CalledProcessError, OSError):
        pass
    return False


def ensure_ejabberd() -> int:
    env = ejabberd_interop_env()
    if ejabberd_listening() and ejabberd_simulator_reachable():
        print("ejabberd listening on 127.0.0.1:5222 and simulator LAN IP")
        return 0
    if ejabberd_listening():
        print("ejabberd on 127.0.0.1 only — restarting for simulator reachability")
    start = ROOT / "scripts" / "start-ejabberd-interop.sh"
    if start.exists():
        return subprocess.call([str(start)], cwd=ROOT, env=env)
    return 0


def ejabberdctl_cmd() -> list[str]:
    ejabberd_interop_env()
    base = ["ejabberdctl"]
    if os.name != "posix" or os.uname().sysname == "Darwin":
        return base
    if shutil.which("sudo"):
        return ["sudo", "-E", *base]
    return base


def reset_localhost_users() -> None:
    """Drop and recreate matrix users and wipe local OMEMO stores."""
    wire_root = ROOT / "tmp" / "wire-data"
    if wire_root.exists():
        shutil.rmtree(wire_root)
    env = ejabberd_interop_env()
    ctl = ejabberdctl_cmd()
    for user, password in [("alice", "alicepass"), ("bob", "bobpass")]:
        subprocess.call(ctl + ["unregister", user, "localhost"], cwd=ROOT, env=env)
        subprocess.call(ctl + ["register", user, "localhost", password], cwd=ROOT, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OMEMO client interop matrix")
    parser.add_argument("--pair", default="conversations-vs-siskin")
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        metavar="NAME",
        help="Run only these scenario(s); repeatable. Default: all scenarios for the pair.",
    )
    parser.add_argument("--build", action="store_true", help="Build client runners first")
    parser.add_argument(
        "--native-conversations",
        action="store_true",
        help="Use vendor AxolotlService wire for conversations (not Smack proxy)",
    )
    args = parser.parse_args()

    with open(MATRIX, encoding="utf-8") as f:
        matrix = yaml.safe_load(f)

    pairs = matrix.get("pairs", [])
    pair = next((p for p in pairs if p["id"] == args.pair), None)
    if pair is None:
        print(f"Unknown pair: {args.pair}", file=sys.stderr)
        return 1

    clients = {pair["left"], pair["right"]}
    native_conversations = args.native_conversations or bool(
        pair.get("native_left") and pair.get("left") == "conversations"
    )

    os.environ.setdefault("OMEMO_XMPP_SECURITY", "auto")
    rc = ensure_ejabberd()
    if rc != 0:
        return rc

    reset_localhost_users()

    needs_conv_native = (
        wants_native_client("conversations", pair, True, native_conversations)
        or wants_native_client("conversations", pair, False, native_conversations)
    )
    if needs_conv_native and not os.environ.get("ANDROID_HOME"):
        print("ANDROID_HOME required for native Conversations wire", file=sys.stderr)
        return 1

    if needs_conv_native:
        rc = prewarm_conversations_native_wire()
        if rc != 0:
            print(f"prewarm: conversations native wire failed ({rc})", file=sys.stderr)
            return rc

    if native_macos_wire_enabled() and (
        pair.get("native_left") or pair.get("native_right")
    ):
        needs_siskin = (
            (pair.get("left") == "siskin_im" and pair.get("native_left"))
            or (pair.get("right") == "siskin_im" and pair.get("native_right"))
        )
        needs_monal = (
            (pair.get("left") == "monal" and pair.get("native_left"))
            or (pair.get("right") == "monal" and pair.get("native_right"))
        )
        if needs_siskin and not siskin_native_binary().exists():
            rc = build_siskin_native()
            if rc != 0:
                return rc
        if needs_monal and not monal_native_binary().exists():
            rc = build_monal_native()
            if rc != 0:
                return rc

    clients_to_build = set()
    for c in clients:
        as_left = c == pair["left"]
        if use_native_wire(c, pair, as_left, native_conversations):
            continue
        clients_to_build.add(c)
    if args.build or any(not client_launcher(c, matrix).exists() for c in clients_to_build):
        rc = build_clients(clients_to_build, matrix)
        if rc != 0:
            return rc

    scenarios = args.scenarios if args.scenarios else pair["scenarios"]
    unknown = [s for s in scenarios if s not in pair["scenarios"]]
    if unknown:
        print(f"Unknown scenario(s) for pair {pair['id']}: {unknown}", file=sys.stderr)
        return 1

    for scenario in scenarios:
        print(f"\n=== Scenario: {scenario} ({pair['id']}) ===")
        handler = SCENARIO_HANDLERS.get(scenario)
        if handler is None:
            print(f"Unknown scenario: {scenario}")
            return 1
        rc = handler(pair["left"], pair["right"], matrix, pair, native_conversations)
        if rc != 0:
            print(f"FAIL scenario {scenario}")
            return rc
        print(f"PASS scenario {scenario}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
