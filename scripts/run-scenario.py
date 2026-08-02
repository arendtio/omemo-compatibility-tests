#!/usr/bin/env python3
"""Run a YAML scenario against live ejabberd."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from omemo_interop.scenario_engine import ScenarioEngine, load_scenario

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path, help="Path to scenario YAML")
    args = parser.parse_args()

    scenario = load_scenario(args.scenario)
    engine = ScenarioEngine()
    return engine.run(scenario)


if __name__ == "__main__":
    sys.exit(main())
