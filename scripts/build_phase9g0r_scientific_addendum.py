#!/usr/bin/env python3
"""Build the prospective Phase 9G0-R owner addendum and contract artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.contracts import (
    CANDIDATE_PAIR_TRANSACTION_SCHEMA_VERSION,
    COMMUNICATION_CONFIG_SCHEMA_VERSION,
    LIFECYCLE_CONFIG_SCHEMA_VERSION,
    OFFICIAL_ROLLOUT_CONFIG_SCHEMA_VERSION,
    PROHIBITED_OPERATIONAL_ROLLOUT_FIELDS,
    PROHIBITED_ROW_IDENTITY_FIELDS,
    RECOVERABILITY_EGO_PAYLOAD_SCHEMA_VERSION,
    RECOVERABILITY_ROW_IDENTITY_FIELDS,
    RECOVERABILITY_ROW_IDENTITY_SCHEMA_VERSION,
    RESIDUAL_DENSE_RETENTION_SCHEMA_VERSION,
    RESIDUAL_DENSE_STATE_UNIVERSE_SCHEMA_VERSION,
    RESIDUAL_RETENTION_K,
    lifecycle_configuration_payload,
)
from rvt_swarm.runtime_configuration import RuntimeConfig


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"
QUALIFIED_TEAM_SIZES = (5, 6, 8, 12, 16, 24)


def _file_sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _write(name: str, document: Dict[str, Any], hash_field: str) -> Dict[str, Any]:
    output = attach_canonical_hash(document, hash_field)
    (RESULTS / name).write_text(
        json.dumps(output, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return output


def _budget_cap_proof() -> Dict[str, Any]:
    budget = json.loads(
        (RESULTS / "datasets/generation_budget_v1.json").read_text(encoding="ascii")
    )
    by_dataset = []
    total_robot_episodes = 0
    for item in budget["datasets"]:
        if item["dataset_id"] == "study_a_n24_evaluation":
            continue
        robot_episodes = (
            int(item["layout_count"])
            * int(item["source_episodes_per_cell"])
            * sum(int(value) for value in item["team_sizes"])
        )
        total_robot_episodes += robot_episodes
        by_dataset.append({
            "dataset_id": item["dataset_id"],
            "robot_episodes": robot_episodes,
            "k16_upper_bound": RESIDUAL_RETENTION_K * robot_episodes,
        })
    cap = int(budget["exact_total_budget"]["dense_residual_action_records"])
    upper = RESIDUAL_RETENTION_K * total_robot_episodes
    return {
        "authoritative_budget_artifact": "results/rvt_fd24/datasets/generation_budget_v1.json",
        "authoritative_dense_state_cap": cap,
        "included_datasets": by_dataset,
        "excluded_scopes": ["study_a_n24_evaluation", "final_test"],
        "total_authorized_robot_episodes": total_robot_episodes,
        "retention_k": RESIDUAL_RETENTION_K,
        "strict_upper_bound": upper,
        "remaining_capacity": cap - upper,
        "passes": upper <= cap,
        "smallest_k_satisfying_cap": cap // total_robot_episodes,
    }


def main() -> None:
    row_identity = _write(
        "phase9_recoverability_row_identity_v1.json",
        {
            "schema_version": RECOVERABILITY_ROW_IDENTITY_SCHEMA_VERSION,
            "canonicalization": "existing project canonical JSON: ASCII, sorted keys, compact separators, no NaN",
            "digest": "SHA-256 over canonical JSON",
            "identity_fields_in_order": list(RECOVERABILITY_ROW_IDENTITY_FIELDS),
            "prohibited_fields": sorted(PROHIBITED_ROW_IDENTITY_FIELDS),
            "replica_semantics": "replicas determine aggregate label but never row identity",
            "label_semantics": "observed label is excluded from scientific input identity",
            "owner_decision": 1,
        },
        "phase9_recoverability_row_identity_sha256",
    )

    ego_binding = _write(
        "phase9_recoverability_ego_payload_binding_v1.json",
        {
            "schema_version": RECOVERABILITY_EGO_PAYLOAD_SCHEMA_VERSION,
            "authoritative_graph_schema": "rvt-ego-graph/v2",
            "authoritative_serialization": "rvt-ego-graph-serialization/v1",
            "authoritative_builder": "rvt_swarm.decentralized.ego_graph_v2.build_robot_local_ego_graph",
            "authoritative_model_path": "rvt_swarm.fd24.model",
            "payload_semantics": "canonical RobotLocalEgoGraph serialization by value",
            "fingerprint": "SHA-256 of canonical payload after removing content_sha256 and explicit metadata.candidate_topology_id",
            "candidate_conditioning": "candidate_topology_id is a separate row field; exact candidate-conditioned tensors remain by value",
            "included": [
                "schema and normalization versions",
                "feature schema and topology registry hashes",
                "runtime configuration hash",
                "units",
                "observer/root and local mission metadata",
                "mission_orientation_cos_sin",
                "node_x and all node masks/kinds/source keys",
                "edge_index, edge_attr and all edge masks/types",
            ],
            "excluded": [
                "explicit candidate_topology_id",
                "Target V4 label",
                "worker/chunk/retry metadata",
                "operational timing metadata",
            ],
            "node_feature_dimension": 35,
            "edge_feature_dimension": 19,
            "locality": "one RobotView plus one robot-local topology slice; no global pooled graph",
            "source_file_sha256": _file_sha256("rvt_swarm/decentralized/ego_graph_v2.py"),
            "owner_decision": 2,
        },
        "phase9_recoverability_ego_payload_binding_sha256",
    )

    lifecycle = _write(
        "phase9_lifecycle_config_hash_v1.json",
        {
            "schema_version": LIFECYCLE_CONFIG_SCHEMA_VERSION,
            "preimage": {
                "runtime_sections": [
                    "physical", "mission", "formation", "sensing", "protocol",
                    "controller", "safety",
                ],
                "transition_protocol_runtime_options": {
                    "transition_protocol_v1_enabled": True,
                },
            },
            "field_provenance": {
                "runtime_sections": "RuntimeConfig.for_team_size(N), rvt_swarm/runtime_configuration.py",
                "derived_behavior": "DERIVATION_VERSION in the canonical lifecycle payload",
                "transition_protocol_runtime_options": "SimulatorEpisodeSession._initialize_robots",
            },
            "excluded_operational_fields": [
                "hostname", "runtime timestamp", "Python repr/address",
                "worker", "chunk", "retry", "filesystem path",
            ],
            "qualified_team_size_hashes": {
                str(team_size): sha256_document(
                    lifecycle_configuration_payload(RuntimeConfig.for_team_size(team_size))
                )
                for team_size in QUALIFIED_TEAM_SIZES
            },
            "unresolved_behavior_affecting_fields": [],
            "runtime_configuration_source_sha256": _file_sha256("rvt_swarm/runtime_configuration.py"),
            "owner_decision": 4,
        },
        "phase9_lifecycle_config_hash_sha256",
    )

    communication = _write(
        "phase9_communication_config_hash_v1.json",
        {
            "schema_version": COMMUNICATION_CONFIG_SCHEMA_VERSION,
            "preimage_fields": [
                "schema_version",
                "runtime_configuration_schema_version",
                "team_size",
                "RuntimeConfig.communication complete source object",
                "compiled layout communication contract",
                "source-job communication seed",
                "counter-keyed communication stream identity",
            ],
            "field_provenance": {
                "runtime_communication": "RuntimeConfig.for_team_size(N).communication",
                "compiled_communication_contract": "ScenarioRuntimeBinding.communication_contract",
                "communication_seed": "phase9_job_manifest.source_episode_jobs[].seeds.communication",
                "communication_stream_identity": "CounterStream(seed, STREAM_COMMUNICATION).identity()",
            },
            "consumer": "rvt_swarm.phase9c_rb.channel.build_channel",
            "excluded_operational_fields": [
                "hostname", "runtime timestamp", "Python repr/address",
                "worker", "chunk", "retry", "filesystem path",
            ],
            "unresolved_behavior_affecting_fields": [],
            "owner_decision": 4,
        },
        "phase9_communication_config_hash_sha256",
    )

    rollout = _write(
        "phase9_official_rollout_configuration_v1.json",
        {
            "schema_version": OFFICIAL_ROLLOUT_CONFIG_SCHEMA_VERSION,
            "canonicalization": "existing project canonical JSON",
            "digest": "SHA-256 over canonical scientific configuration bundle",
            "preimage_fields": [
                "study/split/family/layout_sha256/team_size",
                "episode_id and decision event/timestep",
                "candidate topology and scientific replica identity",
                "matched disturbance seed and stream identity",
                "source-policy contract",
                "topology-registry contract",
                "base-controller contract",
                "transition/execution protocol contract",
                "safety contract",
                "simulator/runtime integration configuration",
                "Target V4 contract",
                "lifecycle configuration hash",
                "communication configuration hash",
            ],
            "prohibited_operational_fields": sorted(PROHIBITED_OPERATIONAL_ROLLOUT_FIELDS),
            "authoritative_references": {
                "rb19_generation_provenance": "e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571",
                "target_v4": "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee",
                "executable_protocol": "8da0b94e5ae83cf35ea38c38504d11d6e6fdce6da09766bf8cb14c4cc252158a",
            },
            "scheduling_invariance": True,
            "owner_decision": 3,
        },
        "phase9_official_rollout_configuration_sha256",
    )

    pair = _write(
        "phase9_recoverability_candidate_pair_transaction_v1.json",
        {
            "schema_version": CANDIDATE_PAIR_TRANSACTION_SCHEMA_VERSION,
            "reconciliation_boundary": "source decision event",
            "candidate_order": ["COMPACT", "LINE"],
            "candidate_topology_ids": [5, 2],
            "labelable_dispositions": ["RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"],
            "generation_invalid_disposition": "GENERATION_INVALID",
            "infrastructure_failure_disposition": "INFRASTRUCTURE_FAILURE",
            "complete_row_count_formula": "2 * team_size",
            "publication_atomicity": "complete 2*N row set plus provenance is one scientific commit",
            "matrix": {
                "both_labelable": "commit 2*N rows",
                "either_generation_invalid": "commit zero rows and retain both candidate audits",
                "infrastructure_unresolved": "no scientific reconciliation until retry/final infrastructure handling",
            },
            "partial_candidate_publication": "PROHIBITED",
            "owner_decision": 5,
        },
        "phase9_recoverability_candidate_pair_transaction_sha256",
    )

    retention = _write(
        "phase9_residual_dense_state_retention_v1.json",
        {
            "schema_version": RESIDUAL_DENSE_RETENTION_SCHEMA_VERSION,
            "universe_schema_version": RESIDUAL_DENSE_STATE_UNIVERSE_SCHEMA_VERSION,
            "sampling_unit": "robot within source episode",
            "eligibility": [
                "initialization completed successfully",
                "source runtime state scientifically valid",
                "episode not at frozen terminal condition",
                "valid robot-local decision input",
                "authoritative base action computable",
                "authoritative local safety context constructible",
                "Residual Expert V2 snapshot/counterfactual producer callable without invented state",
            ],
            "existing_runtime_enable_predicate": "none beyond active valid local action pipeline",
            "prohibited_filters": [
                "future outcome", "zero residual winner", "eventual label",
                "candidate utility", "future collision", "future success",
                "class balance", "difficulty", "bottleneck-only",
            ],
            "retention_k": RESIDUAL_RETENTION_K,
            "retention_formula": "index_j = floor(j*(M-1)/(K-1)), j=0..K-1, integer arithmetic",
            "original_timestep_preserved": True,
            "cap_proof": _budget_cap_proof(),
            "owner_decisions": [6, "6B"],
        },
        "phase9_residual_dense_state_retention_sha256",
    )

    row_binding = _write(
        "phase9_recoverability_row_binding_v1.json",
        {
            "schema_version": "rvt-recoverability-row-binding/v1",
            "row_identity_contract_sha256": row_identity[
                "phase9_recoverability_row_identity_sha256"
            ],
            "ego_payload_binding_sha256": ego_binding[
                "phase9_recoverability_ego_payload_binding_sha256"
            ],
            "candidate_pair_transaction_sha256": pair[
                "phase9_recoverability_candidate_pair_transaction_sha256"
            ],
            "mapping": "source event -> candidate aggregate -> N robot-local rows; both candidates atomically form 2*N rows",
        },
        "phase9_recoverability_row_binding_sha256",
    )

    contract_hashes = {
        "recoverability_row_identity": row_identity[
            "phase9_recoverability_row_identity_sha256"
        ],
        "recoverability_ego_payload_binding": ego_binding[
            "phase9_recoverability_ego_payload_binding_sha256"
        ],
        "recoverability_row_binding": row_binding[
            "phase9_recoverability_row_binding_sha256"
        ],
        "official_rollout_configuration": rollout[
            "phase9_official_rollout_configuration_sha256"
        ],
        "lifecycle_config_hash": lifecycle["phase9_lifecycle_config_hash_sha256"],
        "communication_config_hash": communication[
            "phase9_communication_config_hash_sha256"
        ],
        "candidate_pair_transaction": pair[
            "phase9_recoverability_candidate_pair_transaction_sha256"
        ],
        "residual_dense_state_retention": retention[
            "phase9_residual_dense_state_retention_sha256"
        ],
    }
    _write(
        "phase9_predata_generation_scientific_addendum_v1.json",
        {
            "schema_version": "rvt-phase9-predata-generation-scientific-addendum/v1",
            "phase": "PHASE_9G0_R",
            "status": "OWNER_DECISIONS_FROZEN_PROSPECTIVELY",
            "historical_9g0_evidence_commit": "9a4197b2182b667bc848c0e4100da0f4491e549a",
            "historical_9g0_binding_map_sha256": "3ca4b7108372d4ab89a862f8d6ed222242385a6ea480f398245a8c88b68b5d20",
            "scientific_roots": {
                "rb19": "e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571",
                "rb20": "8c55f4ef40be509dc6e0bc678467873e5ebd0ce60d0195a2227555676114b95a",
                "target_v4": "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee",
            },
            "owner_decisions": {
                "1_recoverability_row_identity": contract_hashes["recoverability_row_identity"],
                "2_recoverability_ego_payload": contract_hashes["recoverability_ego_payload_binding"],
                "3_official_rollout_configuration": contract_hashes["official_rollout_configuration"],
                "4_lifecycle_and_communication": {
                    "lifecycle": contract_hashes["lifecycle_config_hash"],
                    "communication": contract_hashes["communication_config_hash"],
                },
                "5_candidate_pair_transaction": contract_hashes["candidate_pair_transaction"],
                "6_residual_universe_and_retention": contract_hashes["residual_dense_state_retention"],
            },
            "contract_hashes": contract_hashes,
            "matched_randomness_authority_preserved": "87e206d22d3b3e893bc2c34ac87e97ceb5d9cb66e23d26456791bad552bcf851",
            "pre_addendum_isolation": {
                "official_scientific_data": 0,
                "official_rows": 0,
                "official_staging_writes": 0,
                "study_a_n24_accesses": 0,
                "final_test_accesses": 0,
                "training_operations": 0,
            },
            "prospective_freeze_proof": (
                "All owner decisions were recorded before any official run ID, "
                "official row, official staging write, sealed access, or training operation."
            ),
        },
        "phase9_predata_generation_scientific_addendum_sha256",
    )


if __name__ == "__main__":
    main()
