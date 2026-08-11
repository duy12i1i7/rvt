"""Operational-only contracts for Phase 9G0-P production qualification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rvt_swarm.phase9g0p.benchmark import _scientific_projection, distribution
from rvt_swarm.phase9g0p.preflight import (
    EXPECTED_PROFILES,
    positive_preflight,
    run_negative_preflight,
)
from rvt_swarm.phase9g0r.contracts import (
    CandidateAggregateDisposition,
    Phase9G0RContractError,
    reconcile_candidate_pair,
)
from rvt_swarm.phase9g0r.writer import DIAGNOSTIC, CanonicalGenerationWriter
from rvt_swarm.topology_registry import COMPACT, LINE


ROOT = Path(__file__).resolve().parents[1]


def _transaction():
    compact = CandidateAggregateDisposition(
        "event", COMPACT, "RECOVERABLE_POSITIVE", 1, 1
    )
    line = CandidateAggregateDisposition(
        "event", LINE, "VALID_TASK_NEGATIVE", 0, 1
    )
    rows = tuple({"robot_id": robot} for robot in range(4))
    return reconcile_candidate_pair(
        compact,
        line,
        team_size=4,
        compact_rows=rows,
        line_rows=rows,
    )


def test_scientific_projection_excludes_only_declared_operational_metadata() -> None:
    source = {
        "scientific_row_id": "row",
        "candidate_utilities": [1.0, 2.0],
        "nested": {
            "operational_timing": {"seconds": 3.0},
            "worker_pid": 20,
            "selected_candidate_index": 1,
        },
        "write": {"path": "/tmp/diagnostic"},
    }
    assert _scientific_projection(source) == {
        "candidate_utilities": [1.0, 2.0],
        "nested": {"selected_candidate_index": 1},
        "scientific_row_id": "row",
    }


def test_distribution_reports_declared_quantiles_without_p99() -> None:
    result = distribution(range(1, 21))
    assert result["n"] == 20
    assert result["median"] == 10.5
    assert result["p90"] == pytest.approx(18.1)
    assert result["p95"] == pytest.approx(19.05)
    assert "p99" not in result


def test_writer_duplicate_resume_is_idempotent_and_conflicts_fail_closed(
    tmp_path: Path,
) -> None:
    writer = CanonicalGenerationWriter(tmp_path / "diagnostic", mode=DIAGNOSTIC)
    transaction = _transaction()
    first = writer.write_recoverability_transaction(transaction, {"attempt": "same"})
    replay = writer.write_recoverability_transaction(transaction, {"attempt": "same"})
    assert first["duplicate_replay"] is False
    assert replay["duplicate_replay"] is True
    assert first["canonical_sha256"] == replay["canonical_sha256"]
    with pytest.raises(Phase9G0RContractError, match="different canonical content"):
        writer.write_recoverability_transaction(transaction, {"attempt": "different"})


def test_writer_ignores_nondeterministic_timing_on_duplicate_resume(
    tmp_path: Path,
) -> None:
    writer = CanonicalGenerationWriter(tmp_path / "diagnostic", mode=DIAGNOSTIC)
    transaction = _transaction()
    first = writer.write_recoverability_transaction(
        transaction, {"scientific": "same", "operational_timing": {"seconds": 1.0}}
    )
    replay = writer.write_recoverability_transaction(
        transaction, {"scientific": "same", "operational_timing": {"seconds": 2.0}}
    )
    assert first["canonical_sha256"] == replay["canonical_sha256"]
    assert replay["duplicate_replay"] is True
    persisted = json.loads(Path(first["path"]).read_text(encoding="ascii"))
    assert "operational_timing" not in persisted["audit"]


def test_partial_sidecar_is_never_published_and_resume_replaces_it(tmp_path: Path) -> None:
    writer = CanonicalGenerationWriter(tmp_path / "diagnostic", mode=DIAGNOSTIC)
    destination = tmp_path / "diagnostic" / "residual" / "state-row.json"
    destination.parent.mkdir(parents=True)
    destination.with_suffix(".json.partial").write_text("partial", encoding="ascii")
    result = writer.write_residual_attempt(
        scientific_row_id="row",
        disposition="NO_ELIGIBLE_ACTION",
        row=None,
        audit={"candidate_evaluations": 9},
    )
    persisted = json.loads(destination.read_text(encoding="ascii"))
    assert result["duplicate_replay"] is False
    assert persisted["scientific_completion_marker"] is True
    assert persisted["row"] is None
    assert not destination.with_suffix(".json.partial").exists()


def test_frozen_benchmark_manifests_exclude_sealed_scopes() -> None:
    recoverability = json.loads((
        ROOT / "results/rvt_fd24/phase9g0p_recoverability_benchmark_manifest_v1.json"
    ).read_text(encoding="ascii"))
    residual = json.loads((
        ROOT / "results/rvt_fd24/phase9g0p_residual_benchmark_manifest_v1.json"
    ).read_text(encoding="ascii"))
    assert recoverability["counts"] == {
        "candidate_aggregates": 24,
        "events": 12,
        "prospective_robot_candidate_row_capacity": 260,
        "replica_executions": 40,
    }
    assert residual["counts"] == {
        "candidate_evaluations": 225,
        "retained_state_units": 25,
        "source_episodes": 5,
    }
    for manifest in (recoverability, residual):
        assert manifest["mode"] == "DIAGNOSTIC"
        assert manifest["official_staging_writes"] == 0
        assert manifest["sealed_scope"] == {
            "final_test_accesses": 0,
            "study_a_n24_accesses": 0,
        }


def test_predeclared_production_profiles_are_branch_specific() -> None:
    assert EXPECTED_PROFILES["recoverability"] == {
        "profile_id": "PROFILE_RECOVERABILITY_V1",
        "workers": 12,
        "numeric_threads": 1,
        "chunk_size_atomic_units": 1,
        "infrastructure_timeout_seconds": 60.0,
    }
    assert EXPECTED_PROFILES["residual"] == {
        "profile_id": "PROFILE_RESIDUAL_V2_V1",
        "workers": 8,
        "numeric_threads": 1,
        "chunk_size_atomic_units": 1,
        "infrastructure_timeout_seconds": 360.0,
    }


def test_operational_preflight_and_negative_matrix_close() -> None:
    positive = positive_preflight(ROOT)
    negative = run_negative_preflight(ROOT)
    assert positive["status"] == "PASS"
    assert positive["command_count"] == 8
    assert positive["authorization_remains_false"] is True
    assert negative["case_count"] >= 22
    assert negative["escapes"] == 0


def test_phase9g0p_readiness_is_c_and_preserves_zero_isolation() -> None:
    readiness = json.loads((
        ROOT / "results/rvt_fd24/phase9_production_performance_readiness_v1.json"
    ).read_text(encoding="ascii"))
    expected = readiness.pop("phase9_production_performance_readiness_sha256")
    from rvt_swarm.phase8.common import sha256_document

    assert sha256_document(readiness) == expected
    assert readiness["verdict"] == "C"
    assert readiness["status"] == "READY_FOR_EXPLICIT_SCOPED_OWNER_AUTHORIZATION"
    assert readiness["authorization"]["authorization_remains_false"] is True
    assert readiness["preflight"]["negative_escapes"] == 0
    assert readiness["tests"]["local_complete_suite"]["passed"] == 3048
    assert readiness["tests"]["target_clean_detached_complete_suite"]["passed"] == 3048
    assert all(value == 0 for value in readiness["isolation"].values())
