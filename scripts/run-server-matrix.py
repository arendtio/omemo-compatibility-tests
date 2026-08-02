#!/usr/bin/env python3
"""Run slixmpp OMEMO roundtrip against a server-matrix profile."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SERVER_MATRIX = ROOT / "config" / "server-matrix.yaml"
WIRE_RUNNER = ROOT / "interop" / "runners" / "wire_client.py"


def server_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_profile(profile: dict) -> int:
    compose = ROOT / profile["docker_compose"]
    if not compose.exists():
        print(f"Missing compose file: {compose}", file=sys.stderr)
        return 1
    return subprocess.call(
        ["docker", "compose", "-f", str(compose), "up", "-d", "--wait"],
        cwd=ROOT,
    )


def stop_profile(profile: dict) -> int:
    compose = ROOT / profile["docker_compose"]
    return subprocess.call(["docker", "compose", "-f", str(compose), "down"], cwd=ROOT)


def run_slixmpp_roundtrip(profile: dict) -> int:
    host = profile.get("host", "127.0.0.1")
    port = int(profile.get("port", 5222))
    domain = profile.get("domain", "localhost")
    users = profile.get("users", [])
    if len(users) < 2:
        print("Profile needs at least two users", file=sys.stderr)
        return 1

    alice = users[0]
    bob = users[1]
    alice_jid = f"{alice['user']}@{domain}"
    bob_jid = f"{bob['user']}@{domain}"
    data_root = ROOT / "tmp" / "server-matrix" / profile.get("id", "unknown")
    alice_dir = data_root / "alice"
    bob_dir = data_root / "bob"
    alice_dir.mkdir(parents=True, exist_ok=True)
    bob_dir.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "OMEMO_INTEROP_ROOT": str(ROOT),
        "OMEMO_XMPP_SECURITY": os.environ.get("OMEMO_XMPP_SECURITY", "disabled"),
    }

    bob_wait = subprocess.Popen(
        [
            sys.executable, str(WIRE_RUNNER),
            "--implementation", "slixmpp-omemo",
            "--mode", "wait",
            "--expect", "server-matrix-hello",
            "--jid", bob_jid,
            "--password", bob["password"],
            "--host", host,
            "--port", str(port),
            "--data-dir", str(bob_dir),
        ],
        cwd=ROOT,
        env=env,
    )
    time.sleep(12)
    rc = subprocess.call(
        [
            sys.executable, str(WIRE_RUNNER),
            "--implementation", "slixmpp-omemo",
            "--mode", "send",
            "--peer", bob_jid,
            "--send", "server-matrix-hello",
            "--jid", alice_jid,
            "--password", alice["password"],
            "--host", host,
            "--port", str(port),
            "--data-dir", str(alice_dir),
        ],
        cwd=ROOT,
        env=env,
        timeout=120,
    )
    if rc != 0:
        bob_wait.kill()
        return rc
    try:
        bob_rc = bob_wait.wait(timeout=90)
    except subprocess.TimeoutExpired:
        bob_wait.kill()
        return 1
    if bob_rc != 0:
        return bob_rc

    alice_wait = subprocess.Popen(
        [
            sys.executable, str(WIRE_RUNNER),
            "--implementation", "slixmpp-omemo",
            "--mode", "wait",
            "--expect", "server-matrix-reply",
            "--jid", alice_jid,
            "--password", alice["password"],
            "--host", host,
            "--port", str(port),
            "--data-dir", str(alice_dir),
        ],
        cwd=ROOT,
        env=env,
    )
    time.sleep(1)
    rc = subprocess.call(
        [
            sys.executable, str(WIRE_RUNNER),
            "--implementation", "slixmpp-omemo",
            "--mode", "send",
            "--peer", alice_jid,
            "--send", "server-matrix-reply",
            "--jid", bob_jid,
            "--password", bob["password"],
            "--host", host,
            "--port", str(port),
            "--data-dir", str(bob_dir),
        ],
        cwd=ROOT,
        env=env,
        timeout=120,
    )
    if rc != 0:
        alice_wait.kill()
        return rc
    try:
        return alice_wait.wait(timeout=90)
    except subprocess.TimeoutExpired:
        alice_wait.kill()
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OMEMO server-matrix slixmpp roundtrip")
    parser.add_argument("--profile", default=None, help="Server profile id (ejabberd, prosody, tigase)")
    parser.add_argument("--start", action="store_true", help="Start docker compose for profile first")
    parser.add_argument("--stop", action="store_true", help="Stop docker compose after run")
    args = parser.parse_args()

    with open(SERVER_MATRIX, encoding="utf-8") as f:
        matrix = yaml.safe_load(f)

    profile_id = args.profile or matrix.get("default_profile", "ejabberd")
    profile = matrix["profiles"][profile_id]
    profile = {**profile, "id": profile_id}

    if profile_id == "tigase" and not os.environ.get("OMEMO_TIGASE_READY"):
        print("Tigase profile requires pre-configured server; set OMEMO_TIGASE_READY=1", file=sys.stderr)
        return 2

    if args.start:
        rc = start_profile(profile)
        if rc != 0:
            return rc

    host = profile.get("host", "127.0.0.1")
    port = int(profile.get("port", 5222))
    if not server_reachable(host, port):
        print(f"Server not reachable at {host}:{port}", file=sys.stderr)
        return 1

    rc = run_slixmpp_roundtrip(profile)
    if args.stop:
        stop_profile(profile)
    return rc


if __name__ == "__main__":
    sys.exit(main())
