"""Phase 9G0 stops before inventing official scientific row semantics."""

from __future__ import annotations

import json
from pathlib import Path

from rvt_swarm.phase8.common import sha256_document


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _canonical(path: str, field: str):
    document = json.loads((RESULTS / path).read_text(encoding="ascii"))
    expected = document.pop(field)
    assert expected != "PENDING"
    assert sha256_document(document) == expected
    return document, expected


def test_startup_stop_commit_is_preserved_as_the_9g0_base() -> None:
    binding, _ = _canonical(
        "phase9_official_binding_map_v1.json",
        "phase9_official_binding_map_sha256",
    )
    roots = binding["authoritative_roots"]
    assert roots["startup_stop_commit"] == (
        "9e3363edae42287b3ad04a039bc1bf495cce58a1"
    )
    assert roots["startup_stop_artifact"] == (
        "72cab4f2d195322703c1de5f636c89dc918085b880ab79806d4a0721bd0834be"
    )


def test_binding_map_fail_closes_on_every_unfrozen_derivation() -> None:
    binding, _ = _canonical(
        "phase9_official_binding_map_v1.json",
        "phase9_official_binding_map_sha256",
    )
    unresolved = [entry for entry in binding["binding_entries"] if not entry["frozen"]]
    assert len(unresolved) == binding["hard_stop"]["unfrozen_entries"] == 6
    assert binding["hard_stop"]["frozen_entries"] == 18
    assert binding["status"] == "BLOCKED_NEW_SCIENTIFIC_DERIVATIONS_REQUIRED"
    assert binding["verdict"] == "A"


def test_matched_randomness_authority_is_resolved_without_operational_inputs() -> None:
    matched, _ = _canonical(
        "phase9_matched_randomness_binding_v1.json",
        "phase9_matched_randomness_binding_sha256",
    )
    proof = matched["invariance_proof"]
    assert proof["candidate_pair_seed_mismatches"] == 0
    assert proof["f8_f9_bad_six_rollout_groups"] == 0
    assert proof["f8_f9_replica_seed_distinctness_failures"] == 0
    assert not any(proof[name] for name in (
        "worker_id_in_payload",
        "chunk_id_in_payload",
        "retry_attempt_in_payload",
        "execution_order_in_payload",
    ))
    assert matched["matched_disturbance_seed"]["candidate_topology"] is None


def test_readiness_remains_zero_data_and_has_no_command_plan_v2() -> None:
    readiness, _ = _canonical(
        "phase9_generation_readiness_v3.json",
        "phase9_generation_readiness_v3_sha256",
    )
    assert readiness["status"] == "BLOCKED_NEW_SCIENTIFIC_DECISIONS_REQUIRED"
    assert readiness["verdict"] == "A"
    assert readiness["command_plan_v2"] == {
        "created": False,
        "executed": False,
        "reason": (
            "No executable producer may be prepared while required scientific "
            "derivations are unfrozen."
        ),
    }
    assert set(readiness["isolation"].values()) == {0}


def test_startup_history_was_not_rewritten() -> None:
    startup = json.loads(
        (RESULTS / "phase9_official_generation_startup_block_v1.json").read_text(
            encoding="ascii"
        )
    )
    expected = startup.pop("phase9_official_generation_startup_block_sha256")
    assert expected == "72cab4f2d195322703c1de5f636c89dc918085b880ab79806d4a0721bd0834be"
    assert sha256_document(startup) == expected
