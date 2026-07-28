"""Task 6 — results from different metric semantics must never be aggregated."""

from __future__ import annotations

import json

import pytest

from rvt_swarm.metrics import EVALUATION_SCHEMA_VERSION
from run_experiments import SchemaVersionError, load_json, require_schema_version, save_json


def test_saved_results_carry_the_schema_version(tmp_path) -> None:
    path = tmp_path / "summary.json"
    save_json({"success": 0.5}, path)
    raw = json.loads(path.read_text())
    assert raw["evaluation_schema_version"] == EVALUATION_SCHEMA_VERSION
    assert raw["data"] == {"success": 0.5}


def test_round_trip_returns_the_payload(tmp_path) -> None:
    path = tmp_path / "summary.json"
    save_json({"success": 0.5}, path)
    assert load_json(path) == {"success": 0.5}


def test_unstamped_legacy_file_is_rejected(tmp_path) -> None:
    """Pre-fix result files carry no version field at all."""
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"success": 0.315, "collision_free": 0.488}))
    with pytest.raises(SchemaVersionError, match="no evaluation_schema_version"):
        load_json(path)


def test_foreign_schema_version_is_rejected(tmp_path) -> None:
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"evaluation_schema_version": 1, "data": {"success": 0.3}}))
    with pytest.raises(SchemaVersionError, match="expected"):
        load_json(path)


def test_future_schema_version_is_rejected(tmp_path) -> None:
    path = tmp_path / "future.json"
    path.write_text(
        json.dumps({"evaluation_schema_version": EVALUATION_SCHEMA_VERSION + 1, "data": {}})
    )
    with pytest.raises(SchemaVersionError):
        load_json(path)


def test_require_schema_version_rejects_non_dict_payloads() -> None:
    with pytest.raises(SchemaVersionError):
        require_schema_version([1, 2, 3], path="inline")


def test_evaluator_rows_are_stamped() -> None:
    from rvt_swarm.config import Config
    from rvt_swarm.evaluate import run_policy_episode
    from rvt_swarm.splits import episode_seed

    out = run_policy_episode(
        "adaptive_formation", Config(), 4, "open_field", seed=episode_seed("test", 0, 4, 0)
    )
    assert out["evaluation_schema_version"] == float(EVALUATION_SCHEMA_VERSION)


def test_legacy_quarantine_directories_are_documented() -> None:
    from pathlib import Path

    for rel in ("results/legacy_pre_metric_fix/README.md", "checkpoints/legacy_pre_metric_fix/README.md"):
        readme = Path(__file__).resolve().parents[1] / rel
        assert readme.exists(), f"missing {rel}"
        text = readme.read_text()
        assert "invalid" in text.lower()
        assert "schema" in text.lower() or "semantics" in text.lower()
