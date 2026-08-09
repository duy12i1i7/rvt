"""RB-17 -- generation identity, dispositions and the V2 supervision-row binding.

Three identities that were previously conflated are separated here:

* **scientific row identity** -- one expert decision for one dense decision
  state, robot and topology context. It never contains a candidate index.
* **candidate evaluation identity** -- one of the nine counterfactual
  continuations behind that decision.
* **execution attempt identity** -- chunking, workers and retries. Purely
  operational: it can change freely without moving anything scientific.

Nothing here writes a dataset. The row builder produces the additive V2
supervision-row *binding* so the schema can be round-tripped and audited;
official generation remains unauthorized.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from ..phase8.common import canonical_json_bytes

GENERATION_IDENTITY_SCHEMA_VERSION = "rvt-residual-generation-identity/v2"
RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION = "rvt-residual-supervision-row/v2"
DISPOSITION_SCHEMA_VERSION = "rvt-residual-generation-disposition/v1"

# ---------------------------------------------------------------------------
# RB17-9 -- the disposition taxonomy
# ---------------------------------------------------------------------------
LABELED = "LABELED"
NO_ELIGIBLE_ACTION = "NO_ELIGIBLE_ACTION"
EXECUTION_INVALID = "EXECUTION_INVALID"
INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"

DISPOSITIONS: Tuple[str, ...] = (
    LABELED, NO_ELIGIBLE_ACTION, EXECUTION_INVALID, INFRASTRUCTURE_FAILURE)

# Which dispositions emit a residual supervision row, and which still count in
# the attempted-state denominator. NO_ELIGIBLE_ACTION emits nothing and counts:
# that is the whole point of separating it from EXECUTION_INVALID.
EMITS_TARGET_ROW: Mapping[str, bool] = {
    LABELED: True,
    NO_ELIGIBLE_ACTION: False,
    EXECUTION_INVALID: False,
    INFRASTRUCTURE_FAILURE: False,
}
COUNTS_IN_SCIENTIFIC_DENOMINATOR: Mapping[str, bool] = {
    LABELED: True,
    NO_ELIGIBLE_ACTION: True,
    EXECUTION_INVALID: True,
    INFRASTRUCTURE_FAILURE: False,      # not a scientific outcome; it is retried
}


class GenerationContractError(ValueError):
    """A contract violation the generator must not paper over."""


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(payload))).hexdigest()


# ---------------------------------------------------------------------------
# RB17-3 -- scientific row identity
# ---------------------------------------------------------------------------
#: The minimum complete key. The first five fields are the frozen residual cell
#: (`generation_budget_v1.json#job_identity_contract.residual_cell`); the next
#: five are the frozen dense-row canonical order (`dense_row_contract`); the
#: last pins the label contract, because a different expert specification is a
#: different label for the same state.
SCIENTIFIC_ROW_KEY: Tuple[str, ...] = (
    "study", "split", "family", "layout_sha256", "team_size",
    "episode_id", "timestep", "robot_id", "topology_id", "graph_fingerprint",
    "residual_expert_spec_sha256",
)


def residual_scientific_row_id(key: Mapping[str, Any]) -> str:
    """Canonical identity of one residual supervision row.

    `candidate_index` is deliberately absent: the nine candidates are *how* the
    expert decides, not nine different scientific observations. Passing one is
    an error rather than a silently ignored field.
    """
    missing = [name for name in SCIENTIFIC_ROW_KEY if name not in key]
    if missing:
        raise GenerationContractError(f"scientific row key is missing {missing}")
    extra = [name for name in key if name not in SCIENTIFIC_ROW_KEY]
    if extra:
        raise GenerationContractError(
            f"scientific row key must not carry {extra}; candidate, replica, chunk "
            "and attempt dimensions are not scientific identity")
    return _digest({name: key[name] for name in SCIENTIFIC_ROW_KEY})


# ---------------------------------------------------------------------------
# RB17-4 -- candidate evaluation identity
# ---------------------------------------------------------------------------
CANDIDATE_EVALUATION_KEY: Tuple[str, ...] = (
    "residual_scientific_row_id", "candidate_index", "replica_index",
    "matched_stream_identity_sha256",
)


def candidate_evaluation_id(key: Mapping[str, Any]) -> str:
    """Canonical identity of one of the nine counterfactual continuations."""
    missing = [name for name in CANDIDATE_EVALUATION_KEY if name not in key]
    if missing:
        raise GenerationContractError(f"candidate evaluation key is missing {missing}")
    extra = [name for name in key if name not in CANDIDATE_EVALUATION_KEY]
    if extra:
        raise GenerationContractError(
            f"candidate evaluation key must not carry {extra}")
    index = key["candidate_index"]
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 9:
        raise GenerationContractError("candidate index must be one of the frozen nine")
    return _digest({name: key[name] for name in CANDIDATE_EVALUATION_KEY})


# ---------------------------------------------------------------------------
# RB17-5 -- execution attempt identity
# ---------------------------------------------------------------------------
EXECUTION_ATTEMPT_KEY: Tuple[str, ...] = (
    "chunk_id", "worker_id", "attempt_index", "task_range",
)


def execution_attempt_id(key: Mapping[str, Any]) -> str:
    """Operational identity only. Nothing scientific may be derived from it."""
    missing = [name for name in EXECUTION_ATTEMPT_KEY if name not in key]
    if missing:
        raise GenerationContractError(f"execution attempt key is missing {missing}")
    return _digest({name: key[name] for name in EXECUTION_ATTEMPT_KEY})


# ---------------------------------------------------------------------------
# RB17-12/16 -- the additive V2 supervision-row binding
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResidualSupervisionRowV2:
    """The frozen dense row plus exactly what model V2 additionally needs.

    The frozen `DenseActionSample` references its features by `feature_sha256`
    and carries no frame context, so it alone cannot rebuild a model V2 input.
    This binding adds two things and no scientific information: the
    mission-to-world orientation the repaired residual head consumes, and the
    content hash of the serialized ego-graph record the features come from.
    """

    schema_version: str
    residual_scientific_row_id: str
    dense_row: Mapping[str, Any]
    mission_orientation_cos_sin: Tuple[float, float]
    ego_graph_record_sha256: str
    ego_graph_schema_version: str
    model_input_schema_version: str
    model_schema_version: str
    residual_expert_spec_sha256: str
    selector_sha256: str
    decision_snapshot_sha256: str
    matched_stream_identity_sha256: str
    selected_candidate_index: int
    selected_candidate_evaluation_id: str
    disposition: str

    def __post_init__(self) -> None:
        if self.schema_version != RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION:
            raise GenerationContractError("unknown residual supervision row schema")
        if self.disposition != LABELED:
            raise GenerationContractError(
                "only a LABELED decision produces a supervision row")
        orientation = self.mission_orientation_cos_sin
        if len(orientation) != 2:
            raise GenerationContractError("orientation context must have two components")
        norm = sum(float(value) ** 2 for value in orientation) ** 0.5
        if abs(norm - 1.0) > 1e-9:
            raise GenerationContractError("orientation context must be a unit vector")
        target = self.dense_row.get("residual_target_world_acceleration")
        if target is None or len(target) != 2:
            raise GenerationContractError(
                "a labeled row requires a two-component WORLD residual target")
        if not 0 <= int(self.selected_candidate_index) < 9:
            raise GenerationContractError("selected candidate index is out of range")

    def canonical_payload(self) -> Mapping[str, Any]:
        return {
            "schema_version": self.schema_version,
            "residual_scientific_row_id": self.residual_scientific_row_id,
            "dense_row": {key: value for key, value in sorted(self.dense_row.items())},
            "mission_orientation_cos_sin": [float(v)
                                            for v in self.mission_orientation_cos_sin],
            "ego_graph_record_sha256": self.ego_graph_record_sha256,
            "ego_graph_schema_version": self.ego_graph_schema_version,
            "model_input_schema_version": self.model_input_schema_version,
            "model_schema_version": self.model_schema_version,
            "residual_expert_spec_sha256": self.residual_expert_spec_sha256,
            "selector_sha256": self.selector_sha256,
            "decision_snapshot_sha256": self.decision_snapshot_sha256,
            "matched_stream_identity_sha256": self.matched_stream_identity_sha256,
            "selected_candidate_index": int(self.selected_candidate_index),
            "selected_candidate_evaluation_id": self.selected_candidate_evaluation_id,
            "disposition": self.disposition,
        }

    def canonical_sha256(self) -> str:
        return _digest(self.canonical_payload())


# ---------------------------------------------------------------------------
# RB17-10 -- disposition accounting
# ---------------------------------------------------------------------------
@dataclass
class DispositionCounts:
    """Attempted decision states never vanish; that is the point."""

    attempted: int = 0
    labeled: int = 0
    no_eligible_action: int = 0
    execution_invalid: int = 0
    infrastructure_failure: int = 0
    target_rows_emitted: int = 0

    def record(self, disposition: str) -> None:
        if disposition not in DISPOSITIONS:
            raise GenerationContractError(f"unknown disposition {disposition!r}")
        if COUNTS_IN_SCIENTIFIC_DENOMINATOR[disposition]:
            self.attempted += 1
        if disposition == LABELED:
            self.labeled += 1
            self.target_rows_emitted += 1
        elif disposition == NO_ELIGIBLE_ACTION:
            self.no_eligible_action += 1
        elif disposition == EXECUTION_INVALID:
            self.execution_invalid += 1
        else:
            self.infrastructure_failure += 1

    def as_dict(self) -> Mapping[str, int]:
        return {
            "attempted_expert_decision_states": self.attempted,
            "labeled_states": self.labeled,
            "no_eligible_states": self.no_eligible_action,
            "execution_invalid_states": self.execution_invalid,
            "infrastructure_failures": self.infrastructure_failure,
            "target_rows_emitted": self.target_rows_emitted,
        }

    def consistent(self) -> bool:
        return (self.attempted == self.labeled + self.no_eligible_action
                + self.execution_invalid
                and self.target_rows_emitted == self.labeled)
