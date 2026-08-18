"""Recoverability V3 contracts -- probabilistic (k, R) supervision.

Additive. Nothing here changes V1 or V2: the V1 and V2 identity builders, the
V2 candidate producer and the frozen pair reconciler are imported and reused
rather than reimplemented, so a V3 code path cannot drift from them.

Three ideas carry the whole module:

* **R is identity, not payload.** The frozen row binding says R is bound
  through ``recoverability_replica_protocol_v3_sha256``, so the protocol -- not
  the observed record count -- decides how many replicas a candidate has. A
  data-dependent R would break that, which is why
  :func:`evaluate_candidate_labelability` never recomputes R from the replicas
  it was handed; it checks them against it.
* **A scientifically invalid replica has no Bernoulli outcome.** It is not 0,
  not 1, and not a missing observation that may be dropped from the sum. So a
  candidate with any ``GENERATION_INVALID`` required replica yields no
  supervision at all -- :func:`build_candidate_supervision` returns ``None``
  and the constructor raises if anyone tries to build one anyway.
* **Infrastructure failure is not science.** It produces no disposition, so it
  can neither shrink R nor make a candidate non-labelable; it leaves the pair
  operationally unresolved for the frozen retry/resume path.

Authority: ``RECOVERABILITY_V3_REQUIRED_REPLICA_INVALIDITY_CONTRACT_V1``,
``66bdd9ff...``, frozen prospectively in Phase 9D-V3F-I.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..phase8.common import sha256_document, verify_canonical_hash
from ..topology_registry import COMPACT, LINE
from .contracts import (
    GENERATION_INVALID, INFRASTRUCTURE_FAILURE, LABELABLE_DISPOSITIONS,
    Phase9G0RContractError,
)

RECOVERABILITY_PROTOCOL_V3 = "RECOVERABILITY_V3"

RECOVERABILITY_ROW_IDENTITY_V3_SCHEMA_VERSION = "rvt-recoverability-row-identity/v3"
RECOVERABILITY_ROW_BINDING_V3_SPEC_VERSION = "rvt-recoverability-row-binding/v3"
CANDIDATE_SUPERVISION_V3_SCHEMA_VERSION = "rvt-recoverability-candidate-supervision/v3"
CANDIDATE_PAIR_TRANSACTION_V3_SCHEMA_VERSION = (
    "rvt-recoverability-candidate-pair-transaction/v3")
S8_ACCOUNTING_V3_SCHEMA_VERSION = "rvt-recoverability-s8-invalid-rate/v3"

# ---------------------------------------------------------------------------
# frozen scientific hashes -- never recomputed from a locally constructed dict
# ---------------------------------------------------------------------------
#: Prospectively frozen in Phase 9D-V3F and Phase 9D-V3F-L, and reverified
#: against the on-disk artifacts by :func:`verify_frozen_v3_contracts`.
PROBABILISTIC_TARGET_V3_SHA256 = (
    "a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6")
REPLICA_PROTOCOL_V3_SHA256 = (
    "6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a")
ROW_BINDING_V3_SPEC_SHA256 = (
    "bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c")
TRAINING_LOSS_V3_SHA256 = (
    "fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11")
BRIER_METRIC_V3_SHA256 = (
    "0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04")
SOURCE_ACQUISITION_PROTOCOL_SHA256 = (
    "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d")
TARGET_V4_CONTRACT_SHA256 = (
    "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee")
#: RECOVERABILITY_V3_REQUIRED_REPLICA_INVALIDITY_CONTRACT_V1 (Phase 9D-V3F-I).
INVALIDITY_CONTRACT_V3_SHA256 = (
    "66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75")
#: V3_LAYOUT_SPLIT_REGISTRY_V2 (Phase 9D-V3F-L). The 10-layout TRAIN version
#: below is superseded and official V3 code must refuse it.
LAYOUT_SPLIT_REGISTRY_V2_SHA256 = (
    "5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a")
SUPERSEDED_LAYOUT_SPLIT_REGISTRY_V1_SHA256 = (
    "d84d0fb9699dad7d6fe4783d2bd55e1b644ed027948291aeb75148e88ea54dae")

#: (artifact, inner field, outer field, expected inner hash). The V3F contracts
#: nest two canonical hashes: the inner root over the contract body, then the
#: outer artifact hash over body plus inner.
_FROZEN_ARTIFACTS: Tuple[Tuple[str, str, str, str], ...] = (
    ("results/rvt_fd24/phase9d_v3f_probabilistic_target_contract_v1.json",
     "recoverability_probabilistic_target_v3_sha256",
     "phase9d_v3f_probabilistic_target_contract_sha256",
     PROBABILISTIC_TARGET_V3_SHA256),
    ("results/rvt_fd24/phase9d_v3f_replica_protocol_v1.json",
     "recoverability_replica_protocol_v3_sha256",
     "phase9d_v3f_replica_protocol_sha256",
     REPLICA_PROTOCOL_V3_SHA256),
    ("results/rvt_fd24/phase9d_v3f_row_binding_v1.json",
     "recoverability_row_binding_v3_spec_sha256",
     "phase9d_v3f_row_binding_sha256",
     ROW_BINDING_V3_SPEC_SHA256),
    ("results/rvt_fd24/phase9d_v3f_training_loss_contract_v1.json",
     "recoverability_training_loss_v3_sha256",
     "phase9d_v3f_training_loss_contract_sha256",
     TRAINING_LOSS_V3_SHA256),
    ("results/rvt_fd24/phase9d_v3f_brier_metric_contract_v1.json",
     "recoverability_brier_metric_v3_sha256",
     "phase9d_v3f_brier_metric_contract_sha256",
     BRIER_METRIC_V3_SHA256),
    ("results/rvt_fd24/phase9d_v3f_i_invalidity_contract_v1.json",
     "recoverability_v3_required_replica_invalidity_contract_v1_sha256",
     "phase9d_v3f_i_invalidity_contract_sha256",
     INVALIDITY_CONTRACT_V3_SHA256),
)

#: The sixteen frozen V3 row-identity fields, in the frozen order.
RECOVERABILITY_ROW_IDENTITY_V3_FIELDS: Tuple[str, ...] = (
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
    "source_acquisition_protocol_sha256",
    "target_v4_contract_sha256",
    "recoverability_probabilistic_target_v3_sha256",
    "recoverability_replica_protocol_v3_sha256",
    "recoverability_row_binding_v3_spec_sha256",
)

#: Anything that would let an outcome or an operational accident move a
#: scientific identity. The invalidity contract hash is deliberately absent from
#: identity: the rule decides WHETHER a row exists, not WHAT it is.
PROHIBITED_ROW_IDENTITY_V3_FIELDS = frozenset({
    "observed_k", "observed_R_derived_fraction", "k_over_R", "k", "R",
    "label", "outcome", "aggregate_label", "disposition", "Y", "Y_r",
    "replica_target_v4_labels", "replica_dispositions",
    "worker", "worker_id", "retry", "retry_count", "path", "shard_path",
    "timestamp", "wall_time", "chunk", "chunk_index", "execution_order",
    "replica_index", "seconds",
    "recoverability_v3_required_replica_invalidity_contract_v1_sha256",
})

#: The frozen provenance-binding rule (Phase 9D-V3F-I, A4): an object binds the
#: invalidity contract hash iff the invalidity rule determines its content or
#: its admissibility.
INVALIDITY_CONTRACT_BINDING_SITES: Tuple[str, ...] = (
    "candidate_supervision_provenance",
    "pair_transaction_provenance",
    "dataset_manifest",
    "dataset_seal",
)
INVALIDITY_CONTRACT_NON_BINDING_SITES: Tuple[str, ...] = (
    "official_rollout_configuration",
    "candidate_task_provenance",
    "row_identity",
)

#: Frozen S8 thresholds, carried from label-audit gate 6. Strict inequalities.
S8_MAXIMUM_OVERALL_INVALID_RATE = 0.02
S8_MAXIMUM_FAMILY_INVALID_RATE = 0.05


class V3ContractError(Phase9G0RContractError):
    """A V3 contract violation that must fail closed rather than degrade."""


# ---------------------------------------------------------------------------
# frozen-contract verification
# ---------------------------------------------------------------------------
def verify_frozen_v3_contracts(root: Path) -> Mapping[str, str]:
    """Recompute every frozen V3 hash from its artifact, or raise.

    Both nesting levels are checked. A constant that merely *matches a string
    in a file* would not prove the file is intact, so the canonical hash is
    recomputed over the body as well.
    """
    resolved: Dict[str, str] = {}
    for relative, inner_field, outer_field, expected in _FROZEN_ARTIFACTS:
        path = Path(root) / relative
        if not path.exists():
            raise V3ContractError(f"frozen V3 artifact is missing: {relative}")
        document = json.loads(path.read_text(encoding="ascii"))
        if document.get(inner_field) != expected:
            raise V3ContractError(
                f"{relative} declares {inner_field} "
                f"{str(document.get(inner_field))[:16]}..., expected "
                f"{expected[:16]}...")
        body = {key: value for key, value in document.items() if key != outer_field}
        if not verify_canonical_hash(body, inner_field):
            raise V3ContractError(f"{relative} inner root does not recompute")
        if not verify_canonical_hash(document, outer_field):
            raise V3ContractError(f"{relative} artifact hash does not recompute")
        resolved[inner_field] = expected
    resolved["source_acquisition_protocol_sha256"] = SOURCE_ACQUISITION_PROTOCOL_SHA256
    resolved["target_v4_contract_sha256"] = TARGET_V4_CONTRACT_SHA256
    return resolved


def frozen_invalidity_contract_sha256(root: Path) -> str:
    """The invalidity contract root, verified rather than trusted."""
    return verify_frozen_v3_contracts(root)[
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"]


def require_invalidity_contract(value: Optional[str]) -> str:
    """Fail closed on a missing, empty or wrong invalidity-contract hash."""
    if not value or str(value) != INVALIDITY_CONTRACT_V3_SHA256:
        raise V3ContractError(
            "V3 requires the frozen required-replica invalidity contract "
            f"{INVALIDITY_CONTRACT_V3_SHA256}; refusing to proceed with "
            f"{str(value)[:16]!r}")
    return INVALIDITY_CONTRACT_V3_SHA256


# ---------------------------------------------------------------------------
# row identity
# ---------------------------------------------------------------------------
def recoverability_row_binding_v3_spec_sha256() -> str:
    """The frozen spec hash. It is authority, not a locally derived value."""
    return ROW_BINDING_V3_SPEC_SHA256


def build_recoverability_row_key_v3(
    *, study: str, split: str, family: str, layout_sha256: str, team_size: int,
    episode_id: str, realized_source_timestep: int, robot_id: int,
    candidate_topology_id: int, graph_fingerprint: str,
    source_acquisition_protocol_sha256: str = SOURCE_ACQUISITION_PROTOCOL_SHA256,
) -> Mapping[str, Any]:
    """Exactly the sixteen frozen fields. No outcome may be passed in."""
    return {
        "schema": RECOVERABILITY_ROW_IDENTITY_V3_SCHEMA_VERSION,
        "study": study, "split": split, "family": family,
        "layout_sha256": layout_sha256, "team_size": int(team_size),
        "episode_id": episode_id,
        "realized_source_timestep": int(realized_source_timestep),
        "robot_id": int(robot_id),
        "candidate_topology_id": int(candidate_topology_id),
        "graph_fingerprint": graph_fingerprint,
        "source_acquisition_protocol_sha256": source_acquisition_protocol_sha256,
        "target_v4_contract_sha256": TARGET_V4_CONTRACT_SHA256,
        "recoverability_probabilistic_target_v3_sha256":
            PROBABILISTIC_TARGET_V3_SHA256,
        "recoverability_replica_protocol_v3_sha256": REPLICA_PROTOCOL_V3_SHA256,
        "recoverability_row_binding_v3_spec_sha256": ROW_BINDING_V3_SPEC_SHA256,
    }


def recoverability_scientific_row_id_v3(key: Mapping[str, Any]) -> str:
    """Hash exactly the identity fields, refusing anything outcome-bearing."""
    offending = sorted(PROHIBITED_ROW_IDENTITY_V3_FIELDS & set(key))
    if offending:
        raise V3ContractError(
            f"prohibited V3 row-identity field(s): {', '.join(offending)}")
    missing = [name for name in RECOVERABILITY_ROW_IDENTITY_V3_FIELDS
               if name not in key]
    if missing:
        raise V3ContractError(
            f"V3 row identity is missing {', '.join(missing)}")
    if len(key) != len(RECOVERABILITY_ROW_IDENTITY_V3_FIELDS):
        raise V3ContractError("V3 row identity carries unexpected fields")
    if key["schema"] != RECOVERABILITY_ROW_IDENTITY_V3_SCHEMA_VERSION:
        raise V3ContractError("V3 row identity schema mismatch")
    if int(key["candidate_topology_id"]) not in (COMPACT, LINE):
        raise V3ContractError("V3 candidate must be COMPACT or LINE")
    for name in ("team_size", "robot_id", "realized_source_timestep"):
        value = key[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise V3ContractError(f"{name} must be a nonnegative integer")
    for name in ("layout_sha256", "graph_fingerprint",
                 "source_acquisition_protocol_sha256",
                 "target_v4_contract_sha256",
                 "recoverability_probabilistic_target_v3_sha256",
                 "recoverability_replica_protocol_v3_sha256",
                 "recoverability_row_binding_v3_spec_sha256"):
        if len(str(key[name])) != 64:
            raise V3ContractError(f"{name} is not a SHA-256 digest")
    return sha256_document(
        {name: key[name] for name in RECOVERABILITY_ROW_IDENTITY_V3_FIELDS})


# ---------------------------------------------------------------------------
# candidate labelability -- the frozen invalidity rule
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class V3CandidateLabelability:
    """What the required replica set of one candidate scientifically yields."""

    decision_event_id: str
    candidate_topology_id: int
    R_required: int                                            # noqa: N815
    executed_required_replicas: int
    generation_invalid_replica_indices: Tuple[int, ...]
    valid_replica_labels: Tuple[int, ...]
    labelable: bool
    k: Optional[int]
    infrastructure_unresolved: bool

    @property
    def supervision_exists(self) -> bool:
        return self.labelable

    def as_dict(self) -> Dict[str, Any]:
        return {
            "decision_event_id": self.decision_event_id,
            "candidate_topology_id": int(self.candidate_topology_id),
            "R_required": int(self.R_required),
            "executed_required_replicas": int(self.executed_required_replicas),
            "generation_invalid_replica_indices":
                list(self.generation_invalid_replica_indices),
            "valid_replica_labels": list(self.valid_replica_labels),
            "candidate_scientifically_labelable": bool(self.labelable),
            "k": self.k,
            "R": int(self.R_required),
            "infrastructure_unresolved": bool(self.infrastructure_unresolved),
        }


def evaluate_candidate_labelability(
    *, decision_event_id: str, candidate_topology_id: int, R_required: int,
    replicas: Sequence[Mapping[str, Any]],
    infrastructure_unresolved: bool = False,
) -> V3CandidateLabelability:
    """Apply the frozen invalidity rule to one candidate's replica evidence.

    ``R_required`` comes from the frozen replica protocol and is never inferred
    from ``len(replicas)``; the two are compared instead, so a short replica set
    is an error rather than a silently smaller R.
    """
    if int(candidate_topology_id) not in (COMPACT, LINE):
        raise V3ContractError("V3 candidate must be COMPACT or LINE")
    if int(R_required) < 1:
        raise V3ContractError("R_required must be at least one")

    if infrastructure_unresolved:
        # No scientific disposition exists for at least one required replica.
        # R is not reduced, (k, R) is not constructed, and the candidate is NOT
        # declared non-labelable -- it is simply not yet resolved.
        return V3CandidateLabelability(
            decision_event_id=decision_event_id,
            candidate_topology_id=int(candidate_topology_id),
            R_required=int(R_required),
            executed_required_replicas=len(replicas),
            generation_invalid_replica_indices=tuple(
                sorted(int(item["replica_index"]) for item in replicas
                       if item["disposition"] == GENERATION_INVALID)),
            valid_replica_labels=(),
            labelable=False, k=None, infrastructure_unresolved=True)

    if len(replicas) != int(R_required):
        raise V3ContractError(
            f"candidate executed {len(replicas)} required replicas against the "
            f"frozen R = {R_required}; R is never shrunk to the executed count")
    indices = sorted(int(item["replica_index"]) for item in replicas)
    if indices != list(range(int(R_required))):
        raise V3ContractError("required replica indices are not exactly 0..R-1")

    invalid = tuple(sorted(int(item["replica_index"]) for item in replicas
                           if item["disposition"] == GENERATION_INVALID))
    for item in replicas:
        disposition = str(item["disposition"])
        if disposition == INFRASTRUCTURE_FAILURE:
            raise V3ContractError(
                "an INFRASTRUCTURE_FAILURE replica is not a scientific outcome "
                "and must be resolved by the frozen retry/resume contract")
        if disposition not in LABELABLE_DISPOSITIONS | {GENERATION_INVALID}:
            raise V3ContractError(f"unknown replica disposition {disposition!r}")
        if disposition == GENERATION_INVALID and item.get("label") is not None:
            raise V3ContractError(
                "a GENERATION_INVALID replica must not carry a Bernoulli label")
        if disposition in LABELABLE_DISPOSITIONS and item.get("label") not in (0, 1):
            raise V3ContractError("a valid replica must carry Y in {0, 1}")

    if invalid:
        # Non-imputation: no k over the valid subset, no shrunk R, no Y.
        return V3CandidateLabelability(
            decision_event_id=decision_event_id,
            candidate_topology_id=int(candidate_topology_id),
            R_required=int(R_required),
            executed_required_replicas=len(replicas),
            generation_invalid_replica_indices=invalid,
            valid_replica_labels=tuple(
                int(item["label"]) for item in sorted(
                    replicas, key=lambda entry: int(entry["replica_index"]))
                if item["disposition"] in LABELABLE_DISPOSITIONS),
            labelable=False, k=None, infrastructure_unresolved=False)

    labels = tuple(int(item["label"]) for item in sorted(
        replicas, key=lambda entry: int(entry["replica_index"])))
    return V3CandidateLabelability(
        decision_event_id=decision_event_id,
        candidate_topology_id=int(candidate_topology_id),
        R_required=int(R_required),
        executed_required_replicas=len(replicas),
        generation_invalid_replica_indices=(),
        valid_replica_labels=labels,
        labelable=True, k=int(sum(labels)), infrastructure_unresolved=False)


# ---------------------------------------------------------------------------
# candidate supervision record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class V3CandidateSupervision:
    """The frozen F6 supervision payload. Never a scientific identity."""

    decision_event_id: str
    candidate_evaluation_id: str
    candidate_topology_id: int
    R: int                                                     # noqa: N815
    k: int
    replica_evaluation_ids: Tuple[str, ...]
    replica_target_v4_labels: Tuple[int, ...]
    replica_dispositions: Tuple[str, ...]
    invalidity_contract_sha256: str = INVALIDITY_CONTRACT_V3_SHA256

    def __post_init__(self) -> None:
        if int(self.candidate_topology_id) not in (COMPACT, LINE):
            raise V3ContractError("V3 supervision candidate is invalid")
        if int(self.R) < 1:
            raise V3ContractError("V3 supervision R must be at least one")
        if not 0 <= int(self.k) <= int(self.R):
            raise V3ContractError("V3 supervision requires 0 <= k <= R")
        if len(self.replica_target_v4_labels) != int(self.R):
            raise V3ContractError("V3 supervision needs exactly R replica labels")
        if len(self.replica_dispositions) != int(self.R):
            raise V3ContractError("V3 supervision needs exactly R dispositions")
        if len(self.replica_evaluation_ids) != int(self.R):
            raise V3ContractError("V3 supervision needs exactly R replica ids")
        if any(disposition not in LABELABLE_DISPOSITIONS
               for disposition in self.replica_dispositions):
            raise V3ContractError(
                "a supervision record may only be built from scientifically "
                "valid replicas; an invalid candidate has no (k, R)")
        if sum(int(label) for label in self.replica_target_v4_labels) != int(self.k):
            raise V3ContractError("k must equal the sum of the replica labels")
        require_invalidity_contract(self.invalidity_contract_sha256)

    @property
    def k_over_R_derived_descriptive_only(self) -> float:      # noqa: N802
        return float(self.k) / float(self.R)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": CANDIDATE_SUPERVISION_V3_SCHEMA_VERSION,
            "protocol_version": RECOVERABILITY_PROTOCOL_V3,
            "decision_event_id": self.decision_event_id,
            "candidate_evaluation_id": self.candidate_evaluation_id,
            "candidate_topology_id": int(self.candidate_topology_id),
            "R": int(self.R),
            "k": int(self.k),
            "replica_evaluation_ids": list(self.replica_evaluation_ids),
            "replica_target_v4_labels": [int(v) for v in self.replica_target_v4_labels],
            "replica_dispositions": list(self.replica_dispositions),
            "k_over_R_derived_descriptive_only": self.k_over_R_derived_descriptive_only,
            "recoverability_probabilistic_target_v3_sha256":
                PROBABILISTIC_TARGET_V3_SHA256,
            "recoverability_replica_protocol_v3_sha256": REPLICA_PROTOCOL_V3_SHA256,
            "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
                self.invalidity_contract_sha256,
            "is_scientific_identity": False,
        }


def candidate_evaluation_id_v3(
    *, candidate_event_id: str, candidate_topology_id: int,
) -> str:
    """Outcome-independent candidate-evaluation identity (frozen F5)."""
    return sha256_document({
        "candidate_event_id": candidate_event_id,
        "candidate_topology_id": int(candidate_topology_id),
        "recoverability_replica_protocol_v3_sha256": REPLICA_PROTOCOL_V3_SHA256,
    })


def replica_evaluation_id_v3(
    *, candidate_evaluation_id: str, replica_index: int,
    matched_disturbance_stream_identity: str,
) -> str:
    """Outcome-independent replica-evaluation identity (frozen F5).

    ``replica_index`` and the matched stream are permitted here because they
    describe the experiment performed, not its result.
    """
    return sha256_document({
        "candidate_evaluation_id": candidate_evaluation_id,
        "replica_index": int(replica_index),
        "matched_disturbance_stream_identity":
            str(matched_disturbance_stream_identity),
    })


def build_candidate_supervision(
    labelability: V3CandidateLabelability, *,
    candidate_evaluation_id: str,
    replica_evaluation_ids: Sequence[str],
    replica_dispositions: Sequence[str],
) -> Optional[V3CandidateSupervision]:
    """The supervision record, or ``None`` when no supervision exists."""
    if not labelability.labelable:
        return None
    return V3CandidateSupervision(
        decision_event_id=labelability.decision_event_id,
        candidate_evaluation_id=candidate_evaluation_id,
        candidate_topology_id=int(labelability.candidate_topology_id),
        R=int(labelability.R_required),
        k=int(labelability.k),
        replica_evaluation_ids=tuple(replica_evaluation_ids),
        replica_target_v4_labels=tuple(labelability.valid_replica_labels),
        replica_dispositions=tuple(replica_dispositions))


# ---------------------------------------------------------------------------
# pair transaction
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class V3PairTransaction:
    """One source event, both candidates, all-or-nothing row publication."""

    schema_version: str
    decision_event_id: str
    status: str
    scientifically_reconciled: bool
    training_rows_committable: bool
    expected_row_count: int
    actual_row_count: int
    labelability: Mapping[str, Any]
    supervision: Mapping[str, Any]
    rows: Tuple[Mapping[str, Any], ...]
    invalidity_contract_sha256: str = INVALIDITY_CONTRACT_V3_SHA256
    audit_dispositions: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "protocol_version": RECOVERABILITY_PROTOCOL_V3,
            "decision_event_id": self.decision_event_id,
            "status": self.status,
            "scientifically_reconciled": bool(self.scientifically_reconciled),
            "training_rows_committable": bool(self.training_rows_committable),
            "expected_row_count": int(self.expected_row_count),
            "actual_row_count": int(self.actual_row_count),
            "labelability": dict(self.labelability),
            "supervision": dict(self.supervision),
            "rows": [dict(row) for row in self.rows],
            "audit_dispositions": [dict(item) for item in self.audit_dispositions],
            "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
                self.invalidity_contract_sha256,
        }


#: The existing repository-consistent pair statuses. They are NOT re-invented
#: for V3: `test_v3_pair_statuses_match_the_frozen_reconciler` asserts each
#: string is byte-identical to what `reconcile_candidate_pair` emits for the
#: analogous V1/V2 case, so a semantic duplicate cannot appear.
PAIR_STATUS_LABELABLE = "SCIENTIFICALLY_RECONCILED_LABELABLE"
PAIR_STATUS_GENERATION_INVALID = "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID"
PAIR_STATUS_INFRASTRUCTURE = "PENDING_INFRASTRUCTURE_RESOLUTION"


def reconcile_candidate_pair_v3(
    compact: V3CandidateLabelability,
    line: V3CandidateLabelability,
    *,
    team_size: int,
    compact_supervision: Optional[V3CandidateSupervision] = None,
    line_supervision: Optional[V3CandidateSupervision] = None,
    compact_rows: Sequence[Mapping[str, Any]] = (),
    line_rows: Sequence[Mapping[str, Any]] = (),
) -> V3PairTransaction:
    """Pair atomicity: exactly ``2 * N`` rows, or none at all.

    The precedence is the frozen one -- infrastructure before scientific
    invalidity -- because an unresolved candidate has not yet produced the
    disposition that scientific invalidity would be read from. V3 does not
    delegate to :func:`reconcile_candidate_pair` because a labelable V3
    candidate has no binary aggregate label to hand it; it reuses that
    function's status strings instead, and a test pins the equality.
    """
    if compact.decision_event_id != line.decision_event_id:
        raise V3ContractError("candidate pair crosses decision events")
    if int(compact.candidate_topology_id) != COMPACT:
        raise V3ContractError("candidate pair must be ordered COMPACT then LINE")
    if int(line.candidate_topology_id) != LINE:
        raise V3ContractError("candidate pair must be ordered COMPACT then LINE")

    expected = 2 * int(team_size)
    states = (compact, line)
    both_labelable = compact.labelable and line.labelable

    if any(state.infrastructure_unresolved for state in states):
        status, reconciled, committable = PAIR_STATUS_INFRASTRUCTURE, False, False
        rows: Tuple[Mapping[str, Any], ...] = ()
    elif not both_labelable:
        status, reconciled, committable = (
            PAIR_STATUS_GENERATION_INVALID, True, False)
        rows = ()
    else:
        if len(compact_rows) != int(team_size) or len(line_rows) != int(team_size):
            raise V3ContractError(
                f"a labelable V3 pair requires exactly N rows per candidate, got "
                f"{len(compact_rows)} and {len(line_rows)}")
        status, reconciled, committable = PAIR_STATUS_LABELABLE, True, True
        rows = tuple(compact_rows) + tuple(line_rows)

    if both_labelable:
        if compact_supervision is None or line_supervision is None:
            raise V3ContractError(
                "a labelable V3 pair requires supervision for both candidates")
    elif compact_supervision is not None or line_supervision is not None:
        raise V3ContractError(
            "a non-labelable V3 pair must carry no supervision record")

    supervision: Dict[str, Any] = {}
    if both_labelable:
        supervision = {
            str(COMPACT): compact_supervision.as_dict(),
            str(LINE): line_supervision.as_dict(),
        }
    return V3PairTransaction(
        schema_version=CANDIDATE_PAIR_TRANSACTION_V3_SCHEMA_VERSION,
        decision_event_id=compact.decision_event_id,
        status=status,
        scientifically_reconciled=reconciled,
        training_rows_committable=committable,
        expected_row_count=expected,
        actual_row_count=len(rows),
        labelability={str(COMPACT): compact.as_dict(), str(LINE): line.as_dict()},
        supervision=supervision,
        rows=rows,
        audit_dispositions=(compact.as_dict(), line.as_dict()))


# ---------------------------------------------------------------------------
# S8 invalid-rollout accounting
# ---------------------------------------------------------------------------
@dataclass
class S8InvalidRateAccounting:
    """Exact S8 accounting at the replica-rollout level.

    Numerator: executed required Target-V4 replica rollouts disposed
    ``GENERATION_INVALID``. Denominator: executed required Target-V4 replica
    rollouts. Censored rollouts stay in the denominator -- a candidate whose
    rows were never published still consumed real rollouts -- and unresolved
    infrastructure failures stay out of it, because they produced no scientific
    disposition at all.
    """

    executed_required_rollouts: int = 0
    generation_invalid_rollouts: int = 0
    infrastructure_unresolved_rollouts: int = 0
    per_family_executed: Dict[str, int] = field(default_factory=dict)
    per_family_invalid: Dict[str, int] = field(default_factory=dict)

    def record_replica(self, *, family: str, disposition: str) -> None:
        if disposition == INFRASTRUCTURE_FAILURE:
            self.infrastructure_unresolved_rollouts += 1
            return
        if disposition not in LABELABLE_DISPOSITIONS | {GENERATION_INVALID}:
            raise V3ContractError(f"unknown replica disposition {disposition!r}")
        self.executed_required_rollouts += 1
        self.per_family_executed[family] = self.per_family_executed.get(family, 0) + 1
        self.per_family_invalid.setdefault(family, 0)
        if disposition == GENERATION_INVALID:
            self.generation_invalid_rollouts += 1
            self.per_family_invalid[family] += 1

    @property
    def overall_rate(self) -> float:
        if self.executed_required_rollouts == 0:
            return 0.0
        return self.generation_invalid_rollouts / self.executed_required_rollouts

    def family_rates(self) -> Mapping[str, float]:
        return {
            family: (self.per_family_invalid.get(family, 0) / executed
                     if executed else 0.0)
            for family, executed in sorted(self.per_family_executed.items())
        }

    def gate(self) -> Mapping[str, Any]:
        rates = self.family_rates()
        worst = max(rates.values()) if rates else 0.0
        return {
            "schema_version": S8_ACCOUNTING_V3_SCHEMA_VERSION,
            "gate": "S8",
            "numerator": self.generation_invalid_rollouts,
            "denominator": self.executed_required_rollouts,
            "unit": "executed required Target-V4 replica rollout",
            "overall_rate": self.overall_rate,
            "maximum_overall_rate": S8_MAXIMUM_OVERALL_INVALID_RATE,
            "family_rates": dict(rates),
            "maximum_family_rate_observed": worst,
            "maximum_family_rate": S8_MAXIMUM_FAMILY_INVALID_RATE,
            "infrastructure_unresolved_excluded_from_denominator":
                self.infrastructure_unresolved_rollouts,
            "censored_rollouts_remain_in_denominator": True,
            "result": (
                "PASS"
                if (self.overall_rate < S8_MAXIMUM_OVERALL_INVALID_RATE
                    and worst < S8_MAXIMUM_FAMILY_INVALID_RATE)
                else "FAIL"),
        }
