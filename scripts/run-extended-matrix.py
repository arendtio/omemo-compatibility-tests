#!/usr/bin/env python3
"""Run smoke interop matrix across wire-capable implementations from registry."""

from __future__ import annotations

import argparse
import itertools
import subprocess
import sys
from pathlib import Path

from omemo_interop.runner_registry import wire_capable_implementations, ROOT
from omemo_interop.scenario_engine import ScenarioEngine, load_scenario

SCENARIO_SMOKE = ROOT / "scenarios" / "legacy" / "full_conversation.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=["smoke", "active"], default="smoke")
    parser.add_argument("--max-pairs", type=int, default=10)
    parser.add_argument("--scenario", type=Path, default=SCENARIO_SMOKE)
    args = parser.parse_args()

    impls = wire_capable_implementations()
    if args.tier == "smoke":
        impls = [i for i in impls if i.status == "active" and i.runner == "slixmpp_vendor"]
        if len(impls) < 2:
            impls = [i for i in wire_capable_implementations() if i.runner == "slixmpp_vendor"][:2]

    pairs = list(itertools.combinations(impls, 2))[: args.max_pairs]
    failed = 0

    for left, right in pairs:
        print(f"\n=== Pair: {left.id} vs {right.id} ===")
        scenario = load_scenario(args.scenario)
        # Rewrite participant implementations for this pair
        for p in scenario.participants:
            if p.alias == "alice":
                p.implementation_id = left.id
            elif p.alias == "bob":
                p.implementation_id = right.id
        rc = ScenarioEngine().run(scenario)
        if rc != 0:
            failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
