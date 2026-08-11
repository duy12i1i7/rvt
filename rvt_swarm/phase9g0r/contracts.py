"""Owner-approved scientific contracts for Phase 9G0-R.

This module is additive. It binds existing simulator, graph, controller, safety,
protocol, Target V4, and Residual Expert V2 implementations without changing
their scientific behavior.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from ..decentralized.ego_graph_v2 import (
    EDGE_FEATURE_DIM,
    NODE_FEATURE_DIM,
    RobotLocalEgoGraph,
    dump_robot_local_ego_graph,
    load_robot_local_ego_graph,
)
from ..decentralized.transition_protocol import TransitionProtocolRuntimeOptions
from ..phase8.common import canonical_json_bytes, sha256_document
from ..phase9c_rb.streams import (
    STREAM_COMMUNICATION,
    STREAM_ROBOT_ACCELERATION,
    CounterStream,
)
from ..runtime_configuration import (
    DERIVATION_VERSION,
    RUNTIME_CONFIGURATION_SCHEMA_VERSION,
    RuntimeConfig,
)
from ..topology_registry import COMPACT, LINE


RECOVERABILITY_ROW_IDENTITY_SCHEMA_VERSION = "rvt-recoverability-row-identity/v1"
RECOVERABILITY_EGO_PAYLOAD_SCHEMA_VERSION = "rvt-recoverability-ego-payload-binding/v1"
OFFICIAL_ROLLOUT_CONFIG_SCHEMA_VERSION = "rvt-official-rollout-configuration/v1"
LIFECYCLE_CONFIG_SCHEMA_VERSION = "rvt-lifecycle-config-hash/v1"
COMMUNICATION_CONFIG_SCHEMA_VERSION = "rvt-communication-config-hash/v1"
CANDIDATE_PAIR_TRANSACTION_SCHEMA_VERSION = "rvt-recoverability-candidate-pair-transaction/v1"
RESIDUAL_DENSE_STATE_UNIVERSE_SCHEMA_VERSION = "rvt-residual-dense-state-universe/v1"
RESIDUAL_DENSE_RETENTION_SCHEMA_VERSION = "rvt-residual-dense-retention/v1"

RESIDUAL_RETENTION_K = 16
LABELABLE_DISPOSITIONS = frozenset({
    "RECOVERABLE_POSITIVE",
    "VALID_TASK_NEGATIVE",
})
GENERATION_INVALID = "GENERATION_INVALID"
INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"

RECOVERABILITY_ROW_IDENTITY_FIELDS: Tuple[str, ...] = (
    "schema",
    "study",
    "split",
    "family",
    "layout_sha256",
    "team_size",
    "episode_id",
    "timestep",
    "robot_id",
    "candidate_topology_id",
    "graph_fingerprint",
    "target_v4_contract_sha256",
    "recoverability_row_binding_spec_sha256",
)

PROHIBITED_ROW_IDENTITY_FIELDS = frozenset({
    "label",
    "label_value",
    "worker_id",
    "chunk_id",
    "attempt_index",
    "execution_order",
    "wall_clock_time",
    "filesystem_path",
    "timeout",
    "infrastructure_retry_metadata",
    "replica_index",
})

PROHIBITED_OPERATIONAL_ROLLOUT_FIELDS = frozenset({
    "worker_count",
    "worker_id",
    "chunk_size",
    "chunk_id",
    "attempt_index",
    "wall_clock_timestamp",
    "docker_path",
    "output_directory",
    "timeout",
    "infrastructure_retry_state",
})


class Phase9G0RContractError(ValueError):
    """A prospective official record violates an owner-frozen contract."""


def _require_exact_fields(
    payload: Mapping[str, Any], required: Sequence[str], *, kind: str,
) -> None:
    expected = set(required)
    actual = set(payload)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise Phase9G0RContractError(
            f"{kind} fields differ; missing={missing}, extra={extra}"
        )


def recoverability_scientific_row_id(key: Mapping[str, Any]) -> str:
    """Hash only the owner-approved scientific input identity fields."""
    _require_exact_fields(
        key, RECOVERABILITY_ROW_IDENTITY_FIELDS, kind="recoverability row identity"
    )
    if key["schema"] != RECOVERABILITY_ROW_IDENTITY_SCHEMA_VERSION:
        raise Phase9G0RContractError("recoverability row identity schema mismatch")
    if int(key["candidate_topology_id"]) not in (COMPACT, LINE):
        raise Phase9G0RContractError("recoverability candidate must be COMPACT or LINE")
    if min(int(key["team_size"]), int(key["robot_id"]), int(key["timestep"])) < 0:
        raise Phase9G0RContractError("recoverability row indices are invalid")
    for name in (
        "layout_sha256",
        "graph_fingerprint",
        "target_v4_contract_sha256",
        "recoverability_row_binding_spec_sha256",
    ):
        if len(str(key[name])) != 64:
            raise Phase9G0RContractError(f"{name} is not a SHA-256 digest")
    return sha256_document({name: key[name] for name in RECOVERABILITY_ROW_IDENTITY_FIELDS})


def recoverability_ego_payload(
    graph: RobotLocalEgoGraph,
) -> tuple[Mapping[str, Any], int]:
    """Return the by-value model graph and the separately bound candidate ID.

    The exact canonical tensors and model-input metadata are retained. The
    explicit candidate topology field is removed from the graph-fingerprint
    preimage and carried by the scientific row identity instead.
    """
    if not isinstance(graph, RobotLocalEgoGraph):
        raise TypeError("recoverability ego payload requires RobotLocalEgoGraph")
    raw = json.loads(dump_robot_local_ego_graph(graph))
    raw.pop("content_sha256")
    metadata = dict(raw["metadata"])
    candidate = int(metadata.pop("candidate_topology_id"))
    raw["metadata"] = metadata
    if int(graph.node_x.shape[1]) != NODE_FEATURE_DIM or NODE_FEATURE_DIM != 35:
        raise Phase9G0RContractError("frozen node feature dimension changed")
    if int(graph.edge_attr.shape[1]) != EDGE_FEATURE_DIM or EDGE_FEATURE_DIM != 19:
        raise Phase9G0RContractError("frozen edge feature dimension changed")
    return raw, candidate


def recoverability_graph_fingerprint(graph_payload: Mapping[str, Any]) -> str:
    metadata = graph_payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise Phase9G0RContractError("graph payload metadata is missing")
    if "candidate_topology_id" in metadata:
        raise Phase9G0RContractError(
            "candidate topology ID must remain outside graph fingerprint"
        )
    return sha256_document(dict(graph_payload))


def restore_recoverability_ego_graph(
    graph_payload: Mapping[str, Any],
    candidate_topology_id: int,
    runtime_config: RuntimeConfig,
) -> RobotLocalEgoGraph:
    """Rebuild the exact authoritative graph record consumed by FD24."""
    if int(candidate_topology_id) not in (COMPACT, LINE):
        raise Phase9G0RContractError("invalid recoverability candidate topology")
    document = json.loads(canonical_json_bytes(dict(graph_payload)).decode("ascii"))
    metadata = dict(document["metadata"])
    if "candidate_topology_id" in metadata:
        raise Phase9G0RContractError("graph payload already contains candidate topology")
    metadata["candidate_topology_id"] = int(candidate_topology_id)
    document["metadata"] = metadata
    document["content_sha256"] = sha256_document(document)
    serialized = canonical_json_bytes(document).decode("ascii") + "\n"
    return load_robot_local_ego_graph(serialized, runtime_config)


_LIFECYCLE_RUNTIME_SECTIONS: Tuple[str, ...] = (
    "physical",
    "mission",
    "formation",
    "sensing",
    "protocol",
    "controller",
    "safety",
)


def lifecycle_configuration_payload(runtime_config: RuntimeConfig) -> Mapping[str, Any]:
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("lifecycle configuration requires RuntimeConfig")
    options = TransitionProtocolRuntimeOptions(transition_protocol_v1_enabled=True)
    return {
        "schema_version": LIFECYCLE_CONFIG_SCHEMA_VERSION,
        "runtime_configuration_schema_version": RUNTIME_CONFIGURATION_SCHEMA_VERSION,
        "runtime_derivation_version": DERIVATION_VERSION,
        "runtime_sections": {
            name: asdict(getattr(runtime_config, name))
            for name in _LIFECYCLE_RUNTIME_SECTIONS
        },
        "transition_protocol_runtime_options": asdict(options),
    }


def lifecycle_configuration_sha256(runtime_config: RuntimeConfig) -> str:
    return sha256_document(lifecycle_configuration_payload(runtime_config))


def communication_configuration_payload(
    runtime_config: RuntimeConfig,
    compiled_communication_contract: Mapping[str, Any],
    communication_seed: int,
) -> Mapping[str, Any]:
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("communication configuration requires RuntimeConfig")
    stream = CounterStream(int(communication_seed), STREAM_COMMUNICATION)
    return {
        "schema_version": COMMUNICATION_CONFIG_SCHEMA_VERSION,
        "runtime_configuration_schema_version": RUNTIME_CONFIGURATION_SCHEMA_VERSION,
        "team_size": int(runtime_config.mission.team_size),
        "runtime_communication": asdict(runtime_config.communication),
        "compiled_communication_contract": json.loads(
            canonical_json_bytes(dict(compiled_communication_contract)).decode("ascii")
        ),
        "communication_seed": int(communication_seed),
        "communication_stream_identity": list(stream.identity()),
    }


def communication_configuration_sha256(
    runtime_config: RuntimeConfig,
    compiled_communication_contract: Mapping[str, Any],
    communication_seed: int,
) -> str:
    return sha256_document(communication_configuration_payload(
        runtime_config, compiled_communication_contract, communication_seed
    ))


def official_rollout_configuration_payload(
    *,
    study: str,
    split: str,
    family: str,
    layout_sha256: str,
    team_size: int,
    episode_id: str,
    decision_event_id: str,
    decision_timestep: int,
    candidate_topology_id: int,
    replica_index: int,
    matched_disturbance_seed: int,
    source_policy_contract_sha256: str,
    topology_registry_contract_sha256: str,
    base_controller_contract_sha256: str,
    transition_execution_protocol_sha256: str,
    safety_contract_sha256: str,
    simulator_protocol_sha256: str,
    target_v4_contract_sha256: str,
    runtime_configuration_sha256: str,
    control_period_seconds: float,
    lifecycle_config_sha256: str,
    communication_config_sha256: str,
) -> Mapping[str, Any]:
    if int(candidate_topology_id) not in (COMPACT, LINE):
        raise Phase9G0RContractError("official rollout candidate is invalid")
    if min(int(team_size), int(decision_timestep), int(replica_index)) < 0:
        raise Phase9G0RContractError("official rollout indices are invalid")
    if not math.isfinite(float(control_period_seconds)) or control_period_seconds <= 0.0:
        raise Phase9G0RContractError("control period must be finite and positive")
    stream = CounterStream(
        int(matched_disturbance_seed),
        f"{STREAM_ROBOT_ACCELERATION}:replica-{int(replica_index)}",
    )
    references = {
        "source_policy_contract_sha256": source_policy_contract_sha256,
        "topology_registry_contract_sha256": topology_registry_contract_sha256,
        "base_controller_contract_sha256": base_controller_contract_sha256,
        "transition_execution_protocol_sha256": transition_execution_protocol_sha256,
        "safety_contract_sha256": safety_contract_sha256,
        "simulator_protocol_sha256": simulator_protocol_sha256,
        "target_v4_contract_sha256": target_v4_contract_sha256,
    }
    for name, value in {
        **references,
        "layout_sha256": layout_sha256,
        "runtime_configuration_sha256": runtime_configuration_sha256,
        "lifecycle_config_sha256": lifecycle_config_sha256,
        "communication_config_sha256": communication_config_sha256,
    }.items():
        if len(str(value)) != 64:
            raise Phase9G0RContractError(f"{name} is not a SHA-256 digest")
    return {
        "schema_version": OFFICIAL_ROLLOUT_CONFIG_SCHEMA_VERSION,
        "study": study,
        "split": split,
        "family": family,
        "layout_sha256": layout_sha256,
        "team_size": int(team_size),
        "episode_id": episode_id,
        "decision_event_id": decision_event_id,
        "decision_timestep": int(decision_timestep),
        "candidate_topology_id": int(candidate_topology_id),
        "replica_index": int(replica_index),
        "matched_disturbance_seed": int(matched_disturbance_seed),
        "matched_stream_identity": list(stream.identity()),
        "scientific_contract_references": references,
        "physical_integration": {
            "runtime_configuration_sha256": runtime_configuration_sha256,
            "control_period_seconds": float(control_period_seconds),
        },
        "lifecycle_config_sha256": lifecycle_config_sha256,
        "communication_config_sha256": communication_config_sha256,
    }


def official_rollout_configuration_sha256(**kwargs: Any) -> str:
    if PROHIBITED_OPERATIONAL_ROLLOUT_FIELDS.intersection(kwargs):
        raise Phase9G0RContractError("operational fields entered rollout configuration")
    return sha256_document(official_rollout_configuration_payload(**kwargs))


def retained_dense_state_indices(
    eligible_count: int, *, retention_k: int = RESIDUAL_RETENTION_K,
) -> Tuple[int, ...]:
    """Owner-approved rational temporal retention, without libm or RNG."""
    if isinstance(eligible_count, bool) or not isinstance(eligible_count, int):
        raise TypeError("eligible count must be an integer")
    if eligible_count < 0:
        raise ValueError("eligible count must be nonnegative")
    if retention_k != RESIDUAL_RETENTION_K:
        raise Phase9G0RContractError("residual retention K must remain 16")
    if eligible_count <= retention_k:
        return tuple(range(eligible_count))
    indices = tuple(
        (j * (eligible_count - 1)) // (retention_k - 1)
        for j in range(retention_k)
    )
    if len(set(indices)) != retention_k or indices[0] != 0 or indices[-1] != eligible_count - 1:
        raise Phase9G0RContractError("retention index construction is invalid")
    return indices


@dataclass(frozen=True)
class CandidateAggregateDisposition:
    decision_event_id: str
    candidate_topology_id: int
    disposition: str
    aggregate_label: Optional[int]
    replica_count: int

    def __post_init__(self) -> None:
        if self.candidate_topology_id not in (COMPACT, LINE):
            raise Phase9G0RContractError("candidate aggregate topology is invalid")
        admitted = LABELABLE_DISPOSITIONS | {GENERATION_INVALID, INFRASTRUCTURE_FAILURE}
        if self.disposition not in admitted:
            raise Phase9G0RContractError("candidate aggregate disposition is invalid")
        if self.disposition == "RECOVERABLE_POSITIVE" and self.aggregate_label != 1:
            raise Phase9G0RContractError("positive aggregate must carry label one")
        if self.disposition == "VALID_TASK_NEGATIVE" and self.aggregate_label != 0:
            raise Phase9G0RContractError("valid negative aggregate must carry label zero")
        if self.disposition in (GENERATION_INVALID, INFRASTRUCTURE_FAILURE) and self.aggregate_label is not None:
            raise Phase9G0RContractError("non-labelable aggregate must not carry a label")


@dataclass(frozen=True)
class CandidatePairReconciliation:
    schema_version: str
    decision_event_id: str
    status: str
    scientifically_reconciled: bool
    training_rows_committable: bool
    expected_row_count: int
    actual_row_count: int
    audit_dispositions: Tuple[CandidateAggregateDisposition, ...]
    rows: Tuple[Mapping[str, Any], ...]


def reconcile_candidate_pair(
    compact: CandidateAggregateDisposition,
    line: CandidateAggregateDisposition,
    *,
    team_size: int,
    compact_rows: Sequence[Mapping[str, Any]] = (),
    line_rows: Sequence[Mapping[str, Any]] = (),
) -> CandidatePairReconciliation:
    if compact.decision_event_id != line.decision_event_id:
        raise Phase9G0RContractError("candidate pair crosses decision events")
    if compact.candidate_topology_id != COMPACT or line.candidate_topology_id != LINE:
        raise Phase9G0RContractError("candidate pair must be ordered COMPACT then LINE")
    expected = 2 * int(team_size)
    dispositions = (compact, line)
    if any(item.disposition == INFRASTRUCTURE_FAILURE for item in dispositions):
        status = "PENDING_INFRASTRUCTURE_RESOLUTION"
        reconciled = False
        committable = False
        rows: Tuple[Mapping[str, Any], ...] = ()
    elif any(item.disposition == GENERATION_INVALID for item in dispositions):
        status = "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID"
        reconciled = True
        committable = False
        rows = ()
    else:
        rows = tuple(compact_rows) + tuple(line_rows)
        if len(compact_rows) != int(team_size) or len(line_rows) != int(team_size):
            raise Phase9G0RContractError(
                f"labelable pair requires exactly N rows per candidate, got "
                f"{len(compact_rows)} and {len(line_rows)}"
            )
        status = "SCIENTIFICALLY_RECONCILED_LABELABLE"
        reconciled = True
        committable = True
    return CandidatePairReconciliation(
        CANDIDATE_PAIR_TRANSACTION_SCHEMA_VERSION,
        compact.decision_event_id,
        status,
        reconciled,
        committable,
        expected,
        len(rows),
        dispositions,
        rows,
    )
