"""RB-21 benchmark freeze and scheduler atomicity."""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase9c_rb21.rb21_manifest import (
    RB19_PROVENANCE_ROOT, RB20_REPRODUCTION_HASH, TARGET_V4_HASH,
    benchmark_cases, build_benchmark_manifest,
)
from rvt_swarm.phase9c_rb21.rb21_units import (
    AtomicUnitError, RecoverabilityAtomicUnit, ResidualAtomicUnit,
    reject_intra_unit_split,
)

ROOT = pathlib.Path("results/rvt_fd24")
MANIFEST = json.loads((ROOT / "rb21_benchmark_manifest_v1.json").read_text())


def test_benchmark_manifest_was_frozen_before_timing() -> None:
    body = {key: value for key, value in MANIFEST.items()
            if key != "rb21_benchmark_manifest_sha256"}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == MANIFEST[
        "rb21_benchmark_manifest_sha256"]
    assert MANIFEST == build_benchmark_manifest()
    assert MANIFEST["frozen_before_timing"] is True
    assert MANIFEST["selection_depends_on_measured_speed"] is False
    assert MANIFEST["scientific_roots"] == {
        "rb19_current_provenance_root": RB19_PROVENANCE_ROOT,
        "rb20_reproduction": RB20_REPRODUCTION_HASH,
        "target_v4": TARGET_V4_HASH,
    }


def test_manifest_has_larger_predeclared_coverage_without_sealed_domains() -> None:
    counts = MANIFEST["sample_counts"]
    assert counts["residual_atomic_units"] >= 30
    assert counts["residual_candidate_evaluations"] == (
        counts["residual_atomic_units"] * 9)
    assert counts["recoverability_atomic_units"] >= 30
    assert counts["p99_reporting_supported"] is False
    assert MANIFEST["coverage"]["team_sizes"] == [5, 8, 12, 16]
    assert MANIFEST["coverage"]["families"] == ["F1", "F5", "F8", "F9"]
    assert MANIFEST["coverage"]["study_a_n24"] == "SEALED_NOT_INCLUDED"
    assert MANIFEST["coverage"]["final_test"] == "SEALED_NOT_INCLUDED"


def test_residual_atomic_unit_contains_all_nine_candidates() -> None:
    case = benchmark_cases()[0]
    unit = ResidualAtomicUnit(case, case.decision_steps[0], case.robot_ids[0])
    assert unit.candidate_indices == tuple(range(9))
    reject_intra_unit_split(unit, tuple(range(9)))
    with pytest.raises(AtomicUnitError, match="all nine"):
        ResidualAtomicUnit(case, case.decision_steps[0], case.robot_ids[0], (0, 1))
    with pytest.raises(AtomicUnitError, match="candidate splitting"):
        reject_intra_unit_split(unit, (0, 1, 2))


def test_recoverability_atomic_unit_contains_all_frozen_replicas() -> None:
    f8 = next(case for case in benchmark_cases() if case.family == "F8")
    unit = RecoverabilityAtomicUnit(f8, f8.decision_steps[0], 2, (0, 1, 2))
    assert unit.replica_indices == (0, 1, 2)
    reject_intra_unit_split(unit, (0, 1, 2))
    with pytest.raises(AtomicUnitError, match="complete replica"):
        RecoverabilityAtomicUnit(f8, f8.decision_steps[0], 2, (0,))
    with pytest.raises(AtomicUnitError, match="replica splitting"):
        reject_intra_unit_split(unit, (0, 1))


def test_no_scheduler_unit_is_one_residual_candidate() -> None:
    assert MANIFEST["atomic_unit_contract"]["scheduler_level_candidate_split"] == (
        "PROHIBITED")
    assert all(unit["candidate_indices"] == list(range(9))
               for unit in MANIFEST["residual_atomic_units"])
    for unit in MANIFEST["recoverability_atomic_units"]:
        expected = [0, 1, 2] if unit["case"]["family"] in ("F8", "F9") else [0]
        assert unit["replica_indices"] == expected
