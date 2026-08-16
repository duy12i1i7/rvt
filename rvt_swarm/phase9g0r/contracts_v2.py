"""Recoverability V2 identity contracts -- additive to the V1 contracts.

Phase 9G-V2Q found that the frozen V1 row identity cannot express where a V2
row came from: it has no field for the source-acquisition protocol, so a V1 row
and a V2 row for the same realized coordinate would hash identically. Phase
9G-V2I carries the owner authorization (I9) for an **additive** Row Identity V2.

Nothing here modifies V1. `contracts.RECOVERABILITY_ROW_IDENTITY_FIELDS`,
`recoverability_scientific_row_id` and the V1 accounting stay exactly as they
are so V1 remains historically replayable.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from ..phase8.common import sha256_document
from ..phase9d_h1r.acquisition_v2 import (
    DEFAULT_K, REALIZED_TRAJECTORY_UNIFORM_K,
    frozen_acquisition_protocol_v2, frozen_acquisition_protocol_v2_sha256,
)
from ..topology_registry import COMPACT, LINE
from .contracts import Phase9G0RContractError

#: Explicit protocol versions. Dispatch is by this value, never by an ad-hoc
#: boolean flag, so a reader can always tell which science produced a record.
RECOVERABILITY_PROTOCOL_V1 = "RECOVERABILITY_V1"
RECOVERABILITY_PROTOCOL_V2 = "RECOVERABILITY_V2"
RECOVERABILITY_PROTOCOLS: Tuple[str, ...] = (
    RECOVERABILITY_PROTOCOL_V1, RECOVERABILITY_PROTOCOL_V2)

RECOVERABILITY_ROW_IDENTITY_V2_SCHEMA_VERSION = "rvt-recoverability-row-identity/v2"
RECOVERABILITY_ROW_BINDING_V2_SPEC_VERSION = "rvt-recoverability-row-binding/v2"

TARGET_V4_SHA256 = "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee"

#: The V2 scientific row identity. Two fields carry the whole point of V2:
#: `realized_source_timestep` (never a scheduled slot) and
#: `source_acquisition_protocol_sha256` (which acquisition produced the event).
RECOVERABILITY_ROW_IDENTITY_V2_FIELDS: Tuple[str, ...] = (
    "schema",
    "study",
    "split",
    "family",
    "layout_sha256",
    "team_size",
    "episode_id",
    "realized_source_timestep",
    "robot_id",
    "candidate_topology_id",
    "graph_fingerprint",
    "target_v4_contract_sha256",
    "source_acquisition_protocol_sha256",
    "recoverability_row_binding_v2_spec_sha256",
)

#: Anything that would let an outcome or an operational accident change a
#: scientific identity. Passing one is an error, never a silently ignored key.
PROHIBITED_ROW_IDENTITY_V2_FIELDS = frozenset({
    "label", "label_value", "aggregate_label", "candidate_outcome",
    "disposition", "target_v4_disposition", "model_prediction", "model_output",
    "worker", "worker_id", "chunk", "chunk_id", "attempt", "attempt_index",
    "retry", "retry_index", "execution_order", "wall_clock_time", "seconds",
    "filesystem_path", "serialization_path", "timeout",
    "infrastructure_retry_metadata",
})


def recoverability_row_binding_v2_spec() -> Mapping[str, Any]:
    """The canonical V2 row-binding contract, frozen prospectively (I9)."""
    return {
        "schema_version": RECOVERABILITY_ROW_BINDING_V2_SPEC_VERSION,
        "row_identity_schema": RECOVERABILITY_ROW_IDENTITY_V2_SCHEMA_VERSION,
        "identity_fields": list(RECOVERABILITY_ROW_IDENTITY_V2_FIELDS),
        "prohibited_fields": sorted(PROHIBITED_ROW_IDENTITY_V2_FIELDS),
        "owner_authorization": {
            "phase": "PHASE_9G_V2I",
            "clause": "I9",
            "authorized": True,
            "additive": True,
            "supersedes_v1_row_identity": False,
            "reason": "V2 changes the scientific source-event acquisition "
                      "provenance, so a V2 row must bind the exact "
                      "source-acquisition protocol",
        },
        "acquisition": {
            "rule": REALIZED_TRAJECTORY_UNIFORM_K,
            "K": DEFAULT_K,
            "source_acquisition_protocol_sha256":
                frozen_acquisition_protocol_v2_sha256(
                    frozen_acquisition_protocol_v2()),
        },
        "target_v4_contract_sha256": TARGET_V4_SHA256,
        "timestep_semantics": "realized_source_timestep is a control step the "
                              "source trajectory actually attained; it is never a "
                              "scheduled or nominal slot",
        "graph_fingerprint_semantics": "unchanged: the already-authoritative "
                                       "robot-local ego-graph fingerprint, with "
                                       "candidate topology bound outside it",
        "v1_row_identity_modified": False,
        "authorizes_official_generation": False,
    }


def recoverability_row_binding_v2_spec_sha256(
    spec: Optional[Mapping[str, Any]] = None,
) -> str:
    return sha256_document(dict(spec or recoverability_row_binding_v2_spec()))


def _require_exact_v2_fields(key: Mapping[str, Any]) -> None:
    forbidden = sorted(set(key) & PROHIBITED_ROW_IDENTITY_V2_FIELDS)
    if forbidden:
        raise Phase9G0RContractError(
            f"recoverability V2 row identity must not carry {forbidden}")
    expected = set(RECOVERABILITY_ROW_IDENTITY_V2_FIELDS)
    actual = set(key)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise Phase9G0RContractError(
            f"recoverability V2 row identity fields differ; missing={missing}, "
            f"extra={extra}")


def recoverability_scientific_row_id_v2(key: Mapping[str, Any]) -> str:
    """Canonical identity of one V2 robot-local recoverability row."""
    _require_exact_v2_fields(key)
    if key["schema"] != RECOVERABILITY_ROW_IDENTITY_V2_SCHEMA_VERSION:
        raise Phase9G0RContractError("recoverability V2 row identity schema mismatch")
    if int(key["candidate_topology_id"]) not in (COMPACT, LINE):
        raise Phase9G0RContractError("recoverability candidate must be COMPACT or LINE")
    for name in ("team_size", "robot_id", "realized_source_timestep"):
        value = key[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise Phase9G0RContractError(f"{name} must be a nonnegative integer")
    for name in ("layout_sha256", "graph_fingerprint", "target_v4_contract_sha256",
                 "source_acquisition_protocol_sha256",
                 "recoverability_row_binding_v2_spec_sha256"):
        if len(str(key[name])) != 64:
            raise Phase9G0RContractError(f"{name} is not a SHA-256 digest")
    return sha256_document(
        {name: key[name] for name in RECOVERABILITY_ROW_IDENTITY_V2_FIELDS})


def build_recoverability_row_key_v2(
    *, study: str, split: str, family: str, layout_sha256: str, team_size: int,
    episode_id: str, realized_source_timestep: int, robot_id: int,
    candidate_topology_id: int, graph_fingerprint: str,
    source_acquisition_protocol_sha256: str,
    row_binding_v2_spec_sha256: Optional[str] = None,
) -> Mapping[str, Any]:
    return {
        "schema": RECOVERABILITY_ROW_IDENTITY_V2_SCHEMA_VERSION,
        "study": study, "split": split, "family": family,
        "layout_sha256": layout_sha256, "team_size": int(team_size),
        "episode_id": episode_id,
        "realized_source_timestep": int(realized_source_timestep),
        "robot_id": int(robot_id),
        "candidate_topology_id": int(candidate_topology_id),
        "graph_fingerprint": graph_fingerprint,
        "target_v4_contract_sha256": TARGET_V4_SHA256,
        "source_acquisition_protocol_sha256": source_acquisition_protocol_sha256,
        "recoverability_row_binding_v2_spec_sha256":
            row_binding_v2_spec_sha256 or recoverability_row_binding_v2_spec_sha256(),
    }
