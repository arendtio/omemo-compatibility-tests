"""Scenario DSL execution for multi-step OMEMO conversations."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Participant:
    alias: str
    implementation_id: str
    jid: str
    password: str


@dataclass
class ScenarioStep:
    action: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    id: str
    description: str
    participants: List[Participant]
    steps: List[ScenarioStep]
    timeout_seconds: int = 120


def load_scenario(path: Path) -> Scenario:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    participants = [
        Participant(
            alias=p["alias"],
            implementation_id=p["implementation"],
            jid=p["jid"],
            password=p["password"],
        )
        for p in raw["participants"]
    ]
    steps = [ScenarioStep(action=s["action"], params={k: v for k, v in s.items() if k != "action"}) for s in raw["steps"]]
    return Scenario(
        id=raw.get("id", path.stem),
        description=raw.get("description", ""),
        participants=participants,
        steps=steps,
        timeout_seconds=raw.get("timeout_seconds", 120),
    )


class WireProcess:
    """Long-lived wire client subprocess for one participant."""

    def __init__(self, implementation_id: str, participant: Participant, data_root: Path) -> None:
        self.implementation_id = implementation_id
        self.participant = participant
        self.data_dir = data_root / implementation_id / participant.alias
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._proc: Optional[subprocess.Popen] = None

    def start_wait(self, expect: str) -> None:
        cmd = [
            sys.executable,
            str(ROOT / "interop" / "runners" / "wire_client.py"),
            "--implementation",
            self.implementation_id,
            "--mode",
            "wait",
            "--expect",
            expect,
            "--jid",
            self.participant.jid,
            "--password",
            self.participant.password,
            "--host",
            "127.0.0.1",
            "--port",
            "5222",
            "--data-dir",
            str(self.data_dir),
        ]
        env = {**dict(**__import__("os").environ), "OMEMO_INTEROP_ROOT": str(ROOT)}
        self._proc = subprocess.Popen(cmd, cwd=ROOT, env=env)

    def send(self, peer_jid: str, body: str) -> int:
        cmd = [
            sys.executable,
            str(ROOT / "interop" / "runners" / "wire_client.py"),
            "--implementation",
            self.implementation_id,
            "--mode",
            "send",
            "--peer",
            peer_jid,
            "--send",
            body,
            "--jid",
            sender.jid,
            "--password",
            sender.password,
            "--host",
            "127.0.0.1",
            "--port",
            "5222",
            "--data-dir",
            str(self.data_dir),
        ]
        env = {**dict(**__import__("os").environ), "OMEMO_INTEROP_ROOT": str(ROOT)}
        return subprocess.call(cmd, cwd=ROOT, env=env, timeout=90)

    def poll(self) -> Optional[int]:
        if self._proc is None:
            return None
        return self._proc.poll()

    def kill(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.kill()


class ScenarioEngine:
    def __init__(self, data_root: Path = ROOT / "tmp" / "scenario-data") -> None:
        self.data_root = data_root
        self._aliases: Dict[str, Participant] = {}
        self._waiters: Dict[str, WireProcess] = {}

    def run(self, scenario: Scenario) -> int:
        self._aliases = {p.alias: p for p in scenario.participants}
        print(f"Scenario: {scenario.id} — {scenario.description}")

        for step in scenario.steps:
            rc = self._run_step(step)
            if rc != 0:
                print(f"FAIL step {step.action} {step.params}")
                self._cleanup()
                return rc
            print(f"  OK {step.action}")

        self._cleanup()
        print("Scenario PASS")
        return 0

    def _participant(self, alias: str) -> Participant:
        if alias not in self._aliases:
            raise KeyError(f"Unknown participant alias: {alias}")
        return self._aliases[alias]

    def _run_step(self, step: ScenarioStep) -> int:
        action = step.action
        p = step.params

        if action == "sleep":
            time.sleep(float(p.get("seconds", 1)))
            return 0

        if action == "wait_incoming":
            alias = p["who"]
            expect = p["body"]
            part = self._participant(alias)
            proc = WireProcess(part.implementation_id, part, self.data_root)
            proc.start_wait(expect)
            self._waiters[alias] = proc
            return 0

        if action == "send":
            from_alias = p["from"]
            to_alias = p.get("to")
            body = p["body"]
            sender = self._participant(from_alias)
            peer_jid = self._participant(to_alias).jid if to_alias else p["to_jid"]
            proc = WireProcess(sender.implementation_id, sender, self.data_root)
            return proc.send(peer_jid, body)

        if action == "await_delivery":
            alias = p["who"]
            proc = self._waiters.get(alias)
            if proc is None:
                print(f"No waiter for {alias}")
                return 1
            deadline = time.time() + float(p.get("timeout", 60))
            while time.time() < deadline:
                rc = proc.poll()
                if rc is not None:
                    del self._waiters[alias]
                    return rc
                time.sleep(0.2)
            proc.kill()
            return 1

        if action == "conversation_roundtrip":
            # Complex: A sends, B receives, B replies, A receives
            a = p["alice"]
            b = p["bob"]
            msg_a = p.get("message_a", "hello-roundtrip")
            msg_b = p.get("message_b", "reply-roundtrip")
            pa, pb = self._participant(a), self._participant(b)
            w_b = WireProcess(pb.implementation_id, pb, self.data_root)
            w_b.start_wait(msg_a)
            time.sleep(1)
            w_a = WireProcess(pa.implementation_id, pa, self.data_root)
            if w_a.send(pb.jid, msg_a) != 0:
                w_b.kill()
                return 1
            deadline = time.time() + 60
            while time.time() < deadline and w_b.poll() is None:
                time.sleep(0.2)
            if w_b.poll() != 0:
                return 1
            w_a_wait = WireProcess(pa.implementation_id, pa, self.data_root)
            w_a_wait.start_wait(msg_b)
            time.sleep(1)
            if w_b.send(pa.jid, msg_b) != 0:
                w_a_wait.kill()
                return 1
            deadline = time.time() + 60
            while time.time() < deadline and w_a_wait.poll() is None:
                time.sleep(0.2)
            return 0 if w_a_wait.poll() == 0 else 1

        raise ValueError(f"Unknown scenario action: {action}")

    def _cleanup(self) -> None:
        for proc in self._waiters.values():
            proc.kill()
        self._waiters.clear()
