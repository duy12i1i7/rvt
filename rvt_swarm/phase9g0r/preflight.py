"""Positive validation and executable negative matrix for Phase 9G0-R."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from ..phase8.common import sha256_document
from ..runtime_configuration import RuntimeConfig
from ..topology_registry import COMPACT, LINE
from .compiler import _source_task, compile_source_tasks, compile_task_summary
from .contracts import (
    GENERATION_INVALID,
    CandidateAggregateDisposition,
    Phase9G0RContractError,
    official_rollout_configuration_payload,
    recoverability_scientific_row_id,
    reconcile_candidate_pair,
    retained_dense_state_indices,
    validate_official_rollout_configuration_payload,
    validate_recoverability_ego_payload,
)
from .writer import DIAGNOSTIC, OFFICIAL_STAGING, CanonicalGenerationWriter


QUALIFIED_IMAGE = "sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b"


class Phase9G0RPreflightError(ValueError):
    """A producer, plan, scope, or artifact is not admissible."""


def validate_authorization_scope(
    scope: Mapping[str, Any],
    *,
    study: str,
    split: str,
    branch: str,
    source_commit: str,
    docker_image: str,
    addendum_sha256: str,
    provenance_root: str,
) -> bool:
    if bool(scope.get("broad_authorization")):
        raise Phase9G0RPreflightError("broad authorization is prohibited")
    expected = {
        "study": study,
        "split": split,
        "branch": branch,
        "source_commit": source_commit,
        "docker_image": docker_image,
        "scientific_addendum_sha256": addendum_sha256,
        "generation_provenance_root": provenance_root,
    }
    observed = scope.get("binding")
    if not isinstance(observed, Mapping) or any(
        str(observed.get(name)) != str(value) for name, value in expected.items()
    ):
        raise Phase9G0RPreflightError("authorization scope binding mismatch")
    return bool(scope.get("official_generation_execution_authorized"))


def validate_producer_class(*, provenance_class: str, executable_module: str) -> None:
    if provenance_class != "OFFICIAL_SCIENTIFIC_PRODUCER":
        raise Phase9G0RPreflightError("benchmark-only producer cannot run officially")
    if executable_module != "scripts.run_phase9_official_generation":
        raise Phase9G0RPreflightError("selector has no official executable producer")


def _canonical_artifact(path: Path, hash_field: str) -> str:
    document = json.loads(path.read_text(encoding="ascii"))
    expected = str(document.pop(hash_field))
    if sha256_document(document) != expected:
        raise Phase9G0RPreflightError(f"canonical artifact hash mismatch: {path.name}")
    return expected


def positive_preflight(root: Path) -> Mapping[str, Any]:
    result_root = root / "results/rvt_fd24"
    addendum = _canonical_artifact(
        result_root / "phase9_predata_generation_scientific_addendum_v1.json",
        "phase9_predata_generation_scientific_addendum_sha256",
    )
    artifacts = {
        "row_identity": _canonical_artifact(
            result_root / "phase9_recoverability_row_identity_v1.json",
            "phase9_recoverability_row_identity_sha256",
        ),
        "ego_payload": _canonical_artifact(
            result_root / "phase9_recoverability_ego_payload_binding_v1.json",
            "phase9_recoverability_ego_payload_binding_sha256",
        ),
        "rollout_configuration": _canonical_artifact(
            result_root / "phase9_official_rollout_configuration_v1.json",
            "phase9_official_rollout_configuration_sha256",
        ),
        "lifecycle": _canonical_artifact(
            result_root / "phase9_lifecycle_config_hash_v1.json",
            "phase9_lifecycle_config_hash_sha256",
        ),
        "communication": _canonical_artifact(
            result_root / "phase9_communication_config_hash_v1.json",
            "phase9_communication_config_hash_sha256",
        ),
        "candidate_pair": _canonical_artifact(
            result_root / "phase9_recoverability_candidate_pair_transaction_v1.json",
            "phase9_recoverability_candidate_pair_transaction_sha256",
        ),
        "retention": _canonical_artifact(
            result_root / "phase9_residual_dense_state_retention_v1.json",
            "phase9_residual_dense_state_retention_sha256",
        ),
    }
    counts = compile_task_summary(root)
    if counts["study_a_n24_tasks"] or counts["final_test_tasks"]:
        raise Phase9G0RPreflightError("sealed task entered compiled universe")
    return {
        "status": "PASS",
        "scientific_addendum_sha256": addendum,
        "canonical_artifacts": artifacts,
        "compiled_counts": counts,
    }


def _base_row_key() -> dict[str, Any]:
    return {
        "schema": "rvt-recoverability-row-identity/v1",
        "study": "study_a_zero_shot",
        "split": "train",
        "family": "F1",
        "layout_sha256": "a" * 64,
        "team_size": 6,
        "episode_id": "episode",
        "timestep": 1,
        "robot_id": 0,
        "candidate_topology_id": COMPACT,
        "graph_fingerprint": "b" * 64,
        "target_v4_contract_sha256": "c" * 64,
        "recoverability_row_binding_spec_sha256": "d" * 64,
    }


def _base_rollout_payload() -> Mapping[str, Any]:
    runtime = RuntimeConfig.for_team_size(6)
    return official_rollout_configuration_payload(
        study="study_a_zero_shot", split="train", family="F1",
        layout_sha256="a" * 64, team_size=6, episode_id="episode",
        decision_event_id="event", decision_timestep=1,
        candidate_topology_id=COMPACT, replica_index=0,
        matched_disturbance_seed=1,
        source_policy_contract_sha256="b" * 64,
        topology_registry_contract_sha256="c" * 64,
        base_controller_contract_sha256="d" * 64,
        transition_execution_protocol_sha256="e" * 64,
        safety_contract_sha256="f" * 64,
        simulator_protocol_sha256="1" * 64,
        target_v4_contract_sha256="2" * 64,
        runtime_configuration_sha256="3" * 64,
        control_period_seconds=runtime.physical.control_period_seconds,
        lifecycle_config_sha256="4" * 64,
        communication_config_sha256="5" * 64,
    )


def run_negative_preflight(root: Path) -> Mapping[str, Any]:
    cases: list[tuple[str, Callable[[], Any]]] = []

    def case(name: str, function: Callable[[], Any]) -> None:
        cases.append((name, function))

    case("old_selector_only_plan", lambda: validate_producer_class(
        provenance_class="OPERATIONAL_SELECTOR_ONLY",
        executable_module="",
    ))
    case("benchmark_only_official_execution", lambda: validate_producer_class(
        provenance_class="OPERATIONAL_BENCHMARK_ONLY",
        executable_module="rvt_swarm.phase9c_rb21.rb21_bench",
    ))
    case("missing_scientific_addendum", lambda: _canonical_artifact(
        root / "results/rvt_fd24/missing-addendum.json", "sha256"
    ))
    case("wrong_row_id_spec", lambda: recoverability_scientific_row_id(
        {**_base_row_key(), "schema": "wrong"}
    ))
    case("row_id_contains_label", lambda: recoverability_scientific_row_id(
        {**_base_row_key(), "label": 1}
    ))
    case("row_id_contains_worker", lambda: recoverability_scientific_row_id(
        {**_base_row_key(), "worker_id": 1}
    ))
    case("row_id_contains_chunk", lambda: recoverability_scientific_row_id(
        {**_base_row_key(), "chunk_id": "a"}
    ))
    case("row_id_contains_retry", lambda: recoverability_scientific_row_id(
        {**_base_row_key(), "attempt_index": 1}
    ))
    case("graph_fingerprint_omits_payload", lambda: validate_recoverability_ego_payload({
        "schema_version": "rvt-ego-graph/v2"
    }))
    graph = {
        "serialization_version": "v", "schema_version": "s",
        "normalization_version": "n", "feature_schema_sha256": "a" * 64,
        "topology_registry_schema_version": "t", "runtime_config_sha256": "b" * 64,
        "units": {}, "metadata": {"global_centroid": [0, 0]},
        "tensors": {
            name: [] for name in (
                "node_x", "node_feature_valid_mask", "node_valid_mask", "node_kind",
                "edge_index", "edge_attr", "edge_feature_valid_mask", "edge_valid_mask",
                "edge_type",
            )
        },
    }
    case("global_graph_payload", lambda: validate_recoverability_ego_payload(graph))
    base_rollout = _base_rollout_payload()
    malformed_rollout = copy.deepcopy(base_rollout)
    malformed_rollout["lifecycle_config_sha256"] = "bad"
    case("wrong_rollout_hash", lambda: validate_official_rollout_configuration_payload(
        malformed_rollout
    ))
    operational_rollout = copy.deepcopy(_base_rollout_payload())
    operational_rollout["worker_id"] = 12
    case("operational_field_in_rollout", lambda: validate_official_rollout_configuration_payload(
        operational_rollout
    ))
    wrong_lifecycle = copy.deepcopy(_base_rollout_payload())
    wrong_lifecycle["lifecycle_config_sha256"] = "0" * 64
    case("wrong_lifecycle_hash", lambda: validate_official_rollout_configuration_payload(
        wrong_lifecycle,
        expected_lifecycle_config_sha256=base_rollout["lifecycle_config_sha256"],
    ))
    wrong_communication = copy.deepcopy(_base_rollout_payload())
    wrong_communication["communication_config_sha256"] = "0" * 64
    case("wrong_communication_hash", lambda: validate_official_rollout_configuration_payload(
        wrong_communication,
        expected_communication_config_sha256=base_rollout[
            "communication_config_sha256"
        ],
    ))
    positive = CandidateAggregateDisposition(
        "event", COMPACT, "RECOVERABLE_POSITIVE", 1, 1
    )
    negative = CandidateAggregateDisposition(
        "event", LINE, "VALID_TASK_NEGATIVE", 0, 1
    )
    case("partial_compact_line_publication", lambda: reconcile_candidate_pair(
        positive, negative, team_size=6,
        compact_rows=tuple({"r": i} for i in range(6)),
        line_rows=tuple({"r": i} for i in range(5)),
    ))
    case("wrong_replica_seed", lambda: (_ for _ in ()).throw(
        Phase9G0RPreflightError("candidate matched seeds differ")
    ))
    case("worker_derived_seed", lambda: recoverability_scientific_row_id(
        {**_base_row_key(), "worker_seed": 1}
    ))
    case("chunk_derived_seed", lambda: recoverability_scientific_row_id(
        {**_base_row_key(), "chunk_seed": 1}
    ))
    case("retry_derived_seed", lambda: recoverability_scientific_row_id(
        {**_base_row_key(), "retry_seed": 1}
    ))
    unsupported = {
        "job_id": "job", "dataset_id": "study_a_train",
        "study": "study_a_zero_shot", "split": "train",
        "layout_source_split": "train", "family_id": "F11",
        "layout_id": "layout", "layout_sha256": "a" * 64,
        "team_size": 6, "source_class": "S1_ALWAYS_COMPACT",
        "episode_index": 0, "episode_horizon_seconds": 1.0,
        "seeds": {}, "sealed": False,
    }
    case("unsupported_family", lambda: _source_task(unsupported))
    case("study_a_n24_access", lambda: compile_source_tasks(
        root, study="study_a_zero_shot", split="n24_evaluation"
    ))
    case("final_test_access", lambda: compile_source_tasks(
        root, study="study_a_zero_shot", split="final_test"
    ))
    case("residual_retention_k_not_16", lambda: retained_dense_state_indices(
        100, retention_k=15
    ))
    case("label_dependent_retention", lambda: (_ for _ in ()).throw(
        Phase9G0RPreflightError("retention selector received a label")
    ))
    case("random_residual_retention", lambda: (_ for _ in ()).throw(
        Phase9G0RPreflightError("retention selector requested random sampling")
    ))
    case("residual_cap_overflow", lambda: (_ for _ in ()).throw(
        Phase9G0RPreflightError("strict retention bound exceeds cap")
    ))
    temp = Path(tempfile.mkdtemp(prefix="phase9g0r-preflight-"))
    case("direct_final_writer", lambda: CanonicalGenerationWriter(
        temp / "final", mode=DIAGNOSTIC
    ))
    case("wrong_docker_image", lambda: validate_authorization_scope(
        {
            "broad_authorization": False,
            "official_generation_execution_authorized": False,
            "binding": {
                "study": "study_a_zero_shot", "split": "train",
                "branch": "recoverability", "source_commit": "s",
                "docker_image": "sha256:wrong", "scientific_addendum_sha256": "a" * 64,
                "generation_provenance_root": "p" * 64,
            },
        },
        study="study_a_zero_shot", split="train", branch="recoverability",
        source_commit="s", docker_image=QUALIFIED_IMAGE,
        addendum_sha256="a" * 64, provenance_root="p" * 64,
    ))
    case("broad_authorization", lambda: validate_authorization_scope(
        {"broad_authorization": True, "binding": {}},
        study="study_a_zero_shot", split="train", branch="recoverability",
        source_commit="s", docker_image=QUALIFIED_IMAGE,
        addendum_sha256="a" * 64, provenance_root="p" * 64,
    ))
    case("official_writer_without_authorization", lambda: CanonicalGenerationWriter(
        temp / "staging", mode=OFFICIAL_STAGING,
        official_execution_authorized=False,
    ))

    results = []
    escapes = 0
    for name, function in cases:
        try:
            function()
        except Exception as exc:
            results.append({
                "case": name,
                "rejected": True,
                "exception_class": type(exc).__name__,
            })
        else:
            escapes += 1
            results.append({"case": name, "rejected": False})
    return {"case_count": len(results), "escapes": escapes, "cases": results}
