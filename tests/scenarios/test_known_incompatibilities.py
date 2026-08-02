"""Regression tests tied to documented interoperability scenarios."""

from pathlib import Path

import pytest
import yaml


KNOWN_ISSUES = Path(__file__).parent / "known_issues.yaml"


@pytest.fixture
def scenarios() -> list:
    with open(KNOWN_ISSUES, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["scenarios"]


def test_known_issues_registry_loads(scenarios: list) -> None:
    assert len(scenarios) >= 5
    ids = {s["id"] for s in scenarios}
    assert "oldmemo_twomemo_cross_encrypt" in ids
    assert "pep_access_whitelist" in ids


@pytest.mark.scenario
def test_documented_scenarios_have_metadata(scenarios: list) -> None:
    for scenario in scenarios:
        assert "id" in scenario
        assert "title" in scenario
        assert "status" in scenario
        assert "affected" in scenario


@pytest.mark.scenario
def test_tested_scenarios_reference_valid_tests(scenarios: list) -> None:
    root = Path(__file__).resolve().parent.parent.parent
    for scenario in scenarios:
        test_ref = scenario.get("test")
        if not test_ref:
            continue
        if "::" in test_ref:
            path_part = test_ref.split("::")[0]
        else:
            path_part = test_ref
        assert (root / path_part).exists(), f"Missing test file for {scenario['id']}"
