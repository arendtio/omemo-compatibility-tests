#!/usr/bin/env python3
"""Run legacy OMEMO client interop matrix over ejabberd."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "config" / "interop-matrix.yaml"
CLIENTS_DIR = ROOT / "interop" / "clients"


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


def scenario_alice_sends_bob_replies(left: str, right: str, matrix: dict) -> int:
    alice_jid = "alice@localhost"
    bob_jid = "bob@localhost"
    tag = f"{left}-to-{right}"

    bob_proc = subprocess.Popen(
        [
            str(client_launcher(right, matrix)),
            "--mode", "wait",
            "--expect", f"hello-{tag}",
            "--",
            "--jid", bob_jid,
            "--password", "bobpass",
            "--host", "127.0.0.1",
            "--port", "5222",
            "--data-dir", str(ROOT / "tmp" / "wire-data" / right / "bob"),
        ],
        cwd=ROOT,
        env={**os.environ, "OMEMO_INTEROP_ROOT": str(ROOT), "OMEMO_XMPP_SECURITY": os.environ.get("OMEMO_XMPP_SECURITY", "auto")},
    )
    time.sleep(12)

    rc = run_client(
        left, matrix, "send",
        alice_jid, "alicepass",
        peer=bob_jid,
        send=f"hello-{tag}",
        data_dir=ROOT / "tmp" / "wire-data" / left / "alice",
    )
    if rc != 0:
        bob_proc.kill()
        return rc

    try:
        bob_rc = bob_proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        bob_proc.kill()
        return 1
    if bob_rc != 0:
        return bob_rc

    # Bob replies
    alice_proc = subprocess.Popen(
        [
            str(client_launcher(left, matrix)),
            "--mode", "wait",
            "--expect", f"reply-{tag}",
            "--",
            "--jid", alice_jid,
            "--password", "alicepass",
            "--host", "127.0.0.1",
            "--port", "5222",
            "--data-dir", str(ROOT / "tmp" / "wire-data" / left / "alice"),
        ],
        cwd=ROOT,
        env={**os.environ, "OMEMO_INTEROP_ROOT": str(ROOT), "OMEMO_XMPP_SECURITY": os.environ.get("OMEMO_XMPP_SECURITY", "auto")},
    )
    time.sleep(1)
    rc = run_client(
        right, matrix, "send",
        bob_jid, "bobpass",
        peer=alice_jid,
        send=f"reply-{tag}",
        data_dir=ROOT / "tmp" / "wire-data" / right / "bob",
    )
    if rc != 0:
        alice_proc.kill()
        return rc
    try:
        return alice_proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        alice_proc.kill()
        return 1


def ejabberdctl_cmd() -> list[str]:
    config = os.environ.get(
        "EJABBERD_INTEROP_CONFIG",
        str(ROOT / "docker" / "ejabberd" / "ejabberd.yml"),
    )
    os.environ["EJABBERD_CONFIG_PATH"] = config
    os.environ.setdefault("EJABBERD_NODE", "ejabberd@localhost")
    base = ["ejabberdctl"]
    if shutil.which("sudo"):
        return ["sudo", "-E", *base]
    return base


def ensure_ejabberd() -> int:
    start = ROOT / "scripts" / "start-ejabberd-interop.sh"
    if start.exists():
        return subprocess.call([str(start)], cwd=ROOT)
    return 0


def reset_localhost_users() -> None:
    """Drop and recreate matrix users and wipe local OMEMO stores."""
    wire_root = ROOT / "tmp" / "wire-data"
    if wire_root.exists():
        shutil.rmtree(wire_root)
    config = os.environ.get(
        "EJABBERD_INTEROP_CONFIG",
        str(ROOT / "docker" / "ejabberd" / "ejabberd.yml"),
    )
    os.environ["EJABBERD_CONFIG_PATH"] = config
    ctl = ejabberdctl_cmd()
    for user, password in [("alice", "alicepass"), ("bob", "bobpass")]:
        subprocess.call(ctl + ["unregister", user, "localhost"], cwd=ROOT)
        subprocess.call(ctl + ["register", user, "localhost", password], cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OMEMO client interop matrix")
    parser.add_argument("--pair", default="conversations-vs-siskin")
    parser.add_argument("--build", action="store_true", help="Build client runners first")
    args = parser.parse_args()

    with open(MATRIX, encoding="utf-8") as f:
        matrix = yaml.safe_load(f)

    pair = next(p for p in matrix["pairs"] if p["id"] == args.pair)
    clients = {pair["left"], pair["right"]}

    os.environ.setdefault("OMEMO_XMPP_SECURITY", "auto")
    rc = ensure_ejabberd()
    if rc != 0:
        return rc

    reset_localhost_users()

    if args.build or not all(client_launcher(c, matrix).exists() for c in clients):
        rc = build_clients(clients, matrix)
        if rc != 0:
            return rc

    for scenario in pair["scenarios"]:
        print(f"\n=== Scenario: {scenario} ({pair['id']}) ===")
        if scenario in {"alice_sends_bob_replies", "cross_session_roundtrip"}:
            rc = scenario_alice_sends_bob_replies(pair["left"], pair["right"], matrix)
        else:
            print(f"Unknown scenario: {scenario}")
            return 1
        if rc != 0:
            print(f"FAIL scenario {scenario}")
            return rc
        print(f"PASS scenario {scenario}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
