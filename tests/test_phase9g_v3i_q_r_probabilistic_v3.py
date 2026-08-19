"""Phase 9G-V3I-Q-R -- Probabilistic Recoverability V3 implementation tests.

The invalidity matrix (R13) is the heart of this file: a candidate whose
required replica set contains any scientifically GENERATION_INVALID rollout
yields no (k, R) at all, its pair publishes zero rows, and every required
replica still executes.
"""

from __future__ import annotations

import json
import math
import pathlib

import pytest
import torch
import torch.nn.functional as F

from rvt_swarm.fd24.loader_v3 import (
    V3LoaderError, batch_event_groups, deterministic_event_order,
    event_group_from_transaction, load_v3_event_groups, scientific_membership,
)
from rvt_swarm.fd24.loss_v3 import (
    V3LossContractError, candidate_loss, dataset_loss, event_loss,
    grouped_bernoulli_nll, reference_candidate_loss,
)
from rvt_swarm.fd24.metrics_v3 import (
    V3MetricContractError, brier_candidate, brier_event,
    brier_from_replica_outcomes, brier_robot, brier_split,
)
from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase9g0r.compiler_v3 import (
    FROZEN_V3_MANIFEST_ARTIFACT_HASHES, FROZEN_V3_MANIFEST_ROOTS, V3_TRAIN,
    V3_VALIDATION, V3CompilerError, assert_layout_registry_authoritative,
    assert_manifest_remains_dry, compile_v3_source_tasks,
    load_v3_layout_registry, load_v3_source_manifest, v3_manifest_dry_report,
    v3_split_of_layout,
)
from rvt_swarm.phase9g0r.contracts import (
    CandidateAggregateDisposition, reconcile_candidate_pair,
)
from rvt_swarm.phase9g0r.contracts_v3 import (
    INVALIDITY_CONTRACT_V3_SHA256, LAYOUT_SPLIT_REGISTRY_V2_SHA256,
    PAIR_STATUS_GENERATION_INVALID, PAIR_STATUS_INFRASTRUCTURE,
    PAIR_STATUS_LABELABLE, PROBABILISTIC_TARGET_V3_SHA256,
    PROHIBITED_ROW_IDENTITY_V3_FIELDS, RECOVERABILITY_ROW_IDENTITY_V3_FIELDS,
    REPLICA_PROTOCOL_V3_SHA256, ROW_BINDING_V3_SPEC_SHA256,
    SUPERSEDED_LAYOUT_SPLIT_REGISTRY_V1_SHA256, S8InvalidRateAccounting,
    V3ContractError, build_candidate_supervision, build_recoverability_row_key_v3,
    candidate_evaluation_id_v3, evaluate_candidate_labelability,
    reconcile_candidate_pair_v3, recoverability_scientific_row_id_v3,
    replica_evaluation_id_v3, require_invalidity_contract,
    verify_frozen_v3_contracts,
)
from rvt_swarm.phase9g0r.producer_v3 import planned_required_replica_executions
from rvt_swarm.phase9g0r.writer_v3 import (
    V3SupervisedDatasetWriter, V3WriterError, build_v3_dataset_manifest,
    seal_v3_dataset,
)
from rvt_swarm.topology_registry import COMPACT, LINE

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"

VALID_POSITIVE = "RECOVERABLE_POSITIVE"
VALID_NEGATIVE = "VALID_TASK_NEGATIVE"
INVALID = "GENERATION_INVALID"


def replica(index, disposition, label=None):
    return {"replica_index": index, "disposition": disposition, "label": label}


def valid_replicas(labels):
    return [replica(index, VALID_POSITIVE if value else VALID_NEGATIVE, value)
            for index, value in enumerate(labels)]


def labelability(labels_or_dispositions, *, candidate=COMPACT, event="event-1",
                 R=None, unresolved=False):
    replicas = labels_or_dispositions
    return evaluate_candidate_labelability(
        decision_event_id=event, candidate_topology_id=candidate,
        R_required=R if R is not None else len(replicas), replicas=replicas,
        infrastructure_unresolved=unresolved)


def supervision_for(state, *, candidate=COMPACT):
    evaluation_id = candidate_evaluation_id_v3(
        candidate_event_id=state.decision_event_id,
        candidate_topology_id=candidate)
    return build_candidate_supervision(
        state,
        candidate_evaluation_id=evaluation_id,
        replica_evaluation_ids=[
            replica_evaluation_id_v3(
                candidate_evaluation_id=evaluation_id, replica_index=index,
                matched_disturbance_stream_identity=str(1000 + index))
            for index in range(state.R_required)],
        replica_dispositions=[
            VALID_POSITIVE if value else VALID_NEGATIVE
            for value in state.valid_replica_labels])


def row_stub(candidate, robot_id, *, split="v3_train", event="event-1"):
    key = build_recoverability_row_key_v3(
        study="study_a_zero_shot", split=split, family="F9",
        layout_sha256="a" * 64, team_size=5, episode_id="episode-1",
        realized_source_timestep=17, robot_id=robot_id,
        candidate_topology_id=candidate, graph_fingerprint="b" * 64)
    return {
        "schema_version": "rvt-recoverability-v3-supervision-row/v1",
        "protocol_version": "RECOVERABILITY_V3",
        "scientific_row_id": recoverability_scientific_row_id_v3(key),
        "scientific_identity": key,
        "graph_payload_schema_version": "rvt-recoverability-ego-payload-binding/v1",
        "graph_payload": {"robot": robot_id},
    }


# =====================================================================
# R1 -- frozen contracts
# =====================================================================
def test_every_frozen_v3_contract_recomputes_from_its_artifact():
    resolved = verify_frozen_v3_contracts(ROOT)
    assert resolved["recoverability_probabilistic_target_v3_sha256"] == (
        PROBABILISTIC_TARGET_V3_SHA256)
    assert resolved["recoverability_replica_protocol_v3_sha256"] == (
        REPLICA_PROTOCOL_V3_SHA256)
    assert resolved["recoverability_row_binding_v3_spec_sha256"] == (
        ROW_BINDING_V3_SPEC_SHA256)
    assert resolved[
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    ] == INVALIDITY_CONTRACT_V3_SHA256


def test_invalidity_contract_fails_closed_when_missing_or_wrong():
    assert require_invalidity_contract(INVALIDITY_CONTRACT_V3_SHA256) == (
        INVALIDITY_CONTRACT_V3_SHA256)
    for bad in (None, "", "0" * 64, INVALIDITY_CONTRACT_V3_SHA256[:-1] + "0"):
        with pytest.raises(V3ContractError):
            require_invalidity_contract(bad)


# =====================================================================
# R13 -- the required invalidity test matrix
# =====================================================================
def test_matrix_1_all_valid_successes_give_k3_r3():
    state = labelability(valid_replicas([1, 1, 1]))
    assert state.labelable is True
    assert (state.k, state.R_required) == (3, 3)
    assert supervision_for(state).as_dict()["k"] == 3


def test_matrix_2_mixed_valid_outcomes_are_supervision():
    state = labelability(valid_replicas([1, 0, 1]))
    assert state.labelable is True
    assert (state.k, state.R_required) == (2, 3)
    record = supervision_for(state).as_dict()
    assert record["k"] == 2 and record["R"] == 3
    assert record["k_over_R_derived_descriptive_only"] == pytest.approx(2 / 3)


def test_matrix_3_all_valid_failures_give_k0_r3():
    state = labelability(valid_replicas([0, 0, 0]))
    assert state.labelable is True
    assert (state.k, state.R_required) == (0, 3)
    assert supervision_for(state).as_dict()["k"] == 0


def test_matrix_4_success_invalid_failure_yields_no_k_and_no_supervision():
    replicas = [replica(0, VALID_POSITIVE, 1), replica(1, INVALID),
                replica(2, VALID_NEGATIVE, 0)]
    state = labelability(replicas)
    assert state.labelable is False
    assert state.k is None
    assert state.R_required == 3
    assert state.executed_required_replicas == 3
    assert state.generation_invalid_replica_indices == (1,)
    assert supervision_for(state) is None


@pytest.mark.parametrize("invalid_index", [0, 1, 2])
def test_matrix_5_and_6_every_required_replica_still_executes(invalid_index):
    replicas = [
        replica(index, INVALID) if index == invalid_index
        else replica(index, VALID_POSITIVE, 1)
        for index in range(3)
    ]
    state = labelability(replicas)
    assert state.executed_required_replicas == 3
    assert state.R_required == 3
    assert state.labelable is False


def test_matrix_7_compact_labelable_line_invalid_publishes_zero_rows():
    compact = labelability(valid_replicas([1, 1, 1]), candidate=COMPACT)
    line = labelability(
        [replica(0, INVALID), replica(1, VALID_POSITIVE, 1),
         replica(2, VALID_NEGATIVE, 0)], candidate=LINE)
    transaction = reconcile_candidate_pair_v3(compact, line, team_size=5)
    assert transaction.actual_row_count == 0
    assert transaction.status == PAIR_STATUS_GENERATION_INVALID
    assert transaction.training_rows_committable is False
    assert transaction.supervision == {}


def test_matrix_8_compact_invalid_line_labelable_publishes_zero_rows():
    compact = labelability([replica(0, INVALID)], candidate=COMPACT, R=1)
    line = labelability(valid_replicas([1]), candidate=LINE)
    transaction = reconcile_candidate_pair_v3(compact, line, team_size=8)
    assert transaction.actual_row_count == 0
    assert transaction.status == PAIR_STATUS_GENERATION_INVALID


def test_matrix_9_both_invalid_publishes_zero_rows():
    compact = labelability([replica(0, INVALID)], candidate=COMPACT, R=1)
    line = labelability([replica(0, INVALID)], candidate=LINE, R=1)
    transaction = reconcile_candidate_pair_v3(compact, line, team_size=6)
    assert transaction.actual_row_count == 0
    assert transaction.status == PAIR_STATUS_GENERATION_INVALID


def test_matrix_10_infrastructure_failure_is_not_scientific_invalidity():
    compact = labelability(valid_replicas([1]), candidate=COMPACT)
    line = labelability([], candidate=LINE, R=1, unresolved=True)
    assert line.labelable is False
    assert line.k is None
    assert line.R_required == 1          # never reduced
    assert line.infrastructure_unresolved is True
    transaction = reconcile_candidate_pair_v3(compact, line, team_size=5)
    assert transaction.status == PAIR_STATUS_INFRASTRUCTURE
    assert transaction.scientifically_reconciled is False
    assert transaction.actual_row_count == 0


def test_matrix_10_infrastructure_replica_may_not_masquerade_as_science():
    with pytest.raises(V3ContractError):
        labelability([replica(0, "INFRASTRUCTURE_FAILURE")], R=1)


def test_matrix_11_scientific_invalidity_never_adds_a_replacement_replica():
    replicas = [replica(0, INVALID), replica(1, VALID_POSITIVE, 1),
                replica(2, VALID_NEGATIVE, 0)]
    state = labelability(replicas)
    assert state.executed_required_replicas == state.R_required == 3
    # a fourth replica would be outcome-dependent replication
    with pytest.raises(V3ContractError):
        labelability(replicas + [replica(3, VALID_POSITIVE, 1)], R=3)


def test_matrix_12_s8_numerator_and_denominator_are_exact():
    accounting = S8InvalidRateAccounting()
    for _ in range(97):
        accounting.record_replica(family="F9", disposition=VALID_POSITIVE)
    for _ in range(3):
        accounting.record_replica(family="F9", disposition=INVALID)
    for _ in range(100):
        accounting.record_replica(family="F1", disposition=VALID_NEGATIVE)
    accounting.record_replica(family="F1", disposition="INFRASTRUCTURE_FAILURE")
    gate = accounting.gate()
    assert gate["numerator"] == 3
    assert gate["denominator"] == 200          # infra excluded, invalid included
    assert gate["overall_rate"] == pytest.approx(3 / 200)
    assert gate["family_rates"]["F9"] == pytest.approx(3 / 100)
    assert gate["family_rates"]["F1"] == 0.0
    assert gate["infrastructure_unresolved_excluded_from_denominator"] == 1
    assert gate["censored_rollouts_remain_in_denominator"] is True
    assert gate["result"] == "PASS"


def test_matrix_12_s8_fails_when_the_frozen_bounds_are_exceeded():
    accounting = S8InvalidRateAccounting()
    for _ in range(90):
        accounting.record_replica(family="F8", disposition=VALID_POSITIVE)
    for _ in range(10):
        accounting.record_replica(family="F8", disposition=INVALID)
    gate = accounting.gate()
    assert gate["overall_rate"] == pytest.approx(0.10)
    assert gate["result"] == "FAIL"


def test_matrix_12_s8_thresholds_are_strict_inequalities():
    accounting = S8InvalidRateAccounting()
    for _ in range(98):
        accounting.record_replica(family="F1", disposition=VALID_POSITIVE)
    for _ in range(2):
        accounting.record_replica(family="F1", disposition=INVALID)
    gate = accounting.gate()
    assert gate["overall_rate"] == pytest.approx(0.02)
    assert gate["result"] == "FAIL"        # "below 0.02", not "at most"


def test_matrix_13_invalid_pair_keeps_its_audit_evidence():
    compact = labelability(
        [replica(0, VALID_POSITIVE, 1), replica(1, INVALID),
         replica(2, VALID_NEGATIVE, 0)], candidate=COMPACT)
    line = labelability(valid_replicas([1, 1, 1]), candidate=LINE)
    transaction = reconcile_candidate_pair_v3(compact, line, team_size=5)
    audit = transaction.as_dict()["labelability"]
    assert audit[str(COMPACT)]["generation_invalid_replica_indices"] == [1]
    assert audit[str(COMPACT)]["valid_replica_labels"] == [1, 0]
    assert audit[str(COMPACT)]["R"] == 3
    assert audit[str(COMPACT)]["k"] is None
    assert audit[str(LINE)]["k"] == 3
    assert transaction.as_dict()[
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    ] == INVALIDITY_CONTRACT_V3_SHA256


def test_matrix_14_no_supervised_placeholder_row_is_possible(tmp_path):
    writer = V3SupervisedDatasetWriter(tmp_path / "diag", mode="DIAGNOSTIC")
    compact = labelability([replica(0, INVALID)], candidate=COMPACT, R=1)
    line = labelability(valid_replicas([1]), candidate=LINE)
    transaction = reconcile_candidate_pair_v3(compact, line, team_size=5)
    with pytest.raises(V3WriterError):
        writer.write_v3_transaction(transaction, audit={})
    assert writer.rows_written == 0


# =====================================================================
# non-imputation and no-shrink-R
# =====================================================================
def test_a_supervision_record_cannot_be_built_from_an_invalid_candidate():
    from rvt_swarm.phase9g0r.contracts_v3 import V3CandidateSupervision
    with pytest.raises(V3ContractError):
        V3CandidateSupervision(
            decision_event_id="event-1", candidate_evaluation_id="c" * 64,
            candidate_topology_id=COMPACT, R=3, k=1,
            replica_evaluation_ids=("a" * 64, "b" * 64, "c" * 64),
            replica_target_v4_labels=(1, 0, 0),
            replica_dispositions=(VALID_POSITIVE, INVALID, VALID_NEGATIVE))


def test_R_is_never_shrunk_to_the_valid_replica_count():
    with pytest.raises(V3ContractError):
        evaluate_candidate_labelability(
            decision_event_id="event-1", candidate_topology_id=COMPACT,
            R_required=3, replicas=valid_replicas([1, 0]))


def test_an_invalid_replica_may_not_carry_a_bernoulli_label():
    with pytest.raises(V3ContractError):
        labelability([replica(0, INVALID, 0)], R=1)


def test_a_valid_replica_must_carry_a_binary_outcome():
    with pytest.raises(V3ContractError):
        labelability([replica(0, VALID_POSITIVE, None)], R=1)


def test_k_must_equal_the_sum_of_the_replica_labels():
    from rvt_swarm.phase9g0r.contracts_v3 import V3CandidateSupervision
    with pytest.raises(V3ContractError):
        V3CandidateSupervision(
            decision_event_id="event-1", candidate_evaluation_id="c" * 64,
            candidate_topology_id=COMPACT, R=3, k=3,
            replica_evaluation_ids=("a" * 64, "b" * 64, "c" * 64),
            replica_target_v4_labels=(1, 1, 0),
            replica_dispositions=(VALID_POSITIVE,) * 3)


# =====================================================================
# R9 -- no early abort
# =====================================================================
class _Task:
    def __init__(self, replicas):
        self.replicas_per_candidate = replicas


@pytest.mark.parametrize("R", [1, 3])
def test_planned_replica_count_is_outcome_independent(R):
    assert planned_required_replica_executions(_Task(R)) == 2 * R


@pytest.mark.parametrize("invalid_index", [0, 1, 2])
def test_total_required_executions_do_not_depend_on_when_invalidity_appears(
        invalid_index):
    replicas = [
        replica(index, INVALID) if index == invalid_index
        else replica(index, VALID_NEGATIVE, 0)
        for index in range(3)
    ]
    compact = labelability(replicas, candidate=COMPACT)
    line = labelability(replicas, candidate=LINE)
    executed = compact.executed_required_replicas + line.executed_required_replicas
    assert executed == planned_required_replica_executions(_Task(3))


# =====================================================================
# pair statuses reuse the existing repository strings
# =====================================================================
def test_v3_pair_statuses_match_the_frozen_reconciler():
    """No semantically duplicate status is invented for V3."""
    def frozen(compact_disposition, line_disposition, label=None):
        return reconcile_candidate_pair(
            CandidateAggregateDisposition("e", COMPACT, compact_disposition,
                                          label, 1),
            CandidateAggregateDisposition("e", LINE, compact_disposition
                                          if line_disposition is None
                                          else line_disposition, label, 1),
            team_size=0).status

    assert PAIR_STATUS_LABELABLE == frozen(VALID_NEGATIVE, VALID_NEGATIVE, 0)
    assert PAIR_STATUS_GENERATION_INVALID == frozen(INVALID, INVALID)
    assert PAIR_STATUS_INFRASTRUCTURE == frozen(
        "INFRASTRUCTURE_FAILURE", "INFRASTRUCTURE_FAILURE")


def test_infrastructure_takes_precedence_over_scientific_invalidity():
    compact = labelability([replica(0, INVALID)], candidate=COMPACT, R=1)
    line = labelability([], candidate=LINE, R=1, unresolved=True)
    transaction = reconcile_candidate_pair_v3(compact, line, team_size=5)
    assert transaction.status == PAIR_STATUS_INFRASTRUCTURE


# =====================================================================
# R12 -- pair atomicity
# =====================================================================
def test_a_labelable_pair_publishes_exactly_two_N_rows():
    compact = labelability(valid_replicas([1, 0, 1]), candidate=COMPACT)
    line = labelability(valid_replicas([0, 0, 0]), candidate=LINE)
    rows_c = [row_stub(COMPACT, index) for index in range(5)]
    rows_l = [row_stub(LINE, index) for index in range(5)]
    transaction = reconcile_candidate_pair_v3(
        compact, line, team_size=5,
        compact_supervision=supervision_for(compact, candidate=COMPACT),
        line_supervision=supervision_for(line, candidate=LINE),
        compact_rows=rows_c, line_rows=rows_l)
    assert transaction.actual_row_count == 10 == 2 * 5
    assert transaction.status == PAIR_STATUS_LABELABLE
    assert transaction.training_rows_committable is True


def test_row_count_is_never_two_N_times_R():
    compact = labelability(valid_replicas([1, 1, 1]), candidate=COMPACT)
    line = labelability(valid_replicas([1, 1, 1]), candidate=LINE)
    transaction = reconcile_candidate_pair_v3(
        compact, line, team_size=5,
        compact_supervision=supervision_for(compact, candidate=COMPACT),
        line_supervision=supervision_for(line, candidate=LINE),
        compact_rows=[row_stub(COMPACT, i) for i in range(5)],
        line_rows=[row_stub(LINE, i) for i in range(5)])
    assert transaction.actual_row_count == 10
    assert transaction.actual_row_count != 2 * 5 * 3


def test_a_partial_robot_set_is_refused():
    compact = labelability(valid_replicas([1]), candidate=COMPACT)
    line = labelability(valid_replicas([1]), candidate=LINE)
    with pytest.raises(V3ContractError):
        reconcile_candidate_pair_v3(
            compact, line, team_size=5,
            compact_supervision=supervision_for(compact, candidate=COMPACT),
            line_supervision=supervision_for(line, candidate=LINE),
            compact_rows=[row_stub(COMPACT, i) for i in range(4)],
            line_rows=[row_stub(LINE, i) for i in range(5)])


def test_a_non_labelable_pair_may_not_carry_supervision():
    compact = labelability([replica(0, INVALID)], candidate=COMPACT, R=1)
    line = labelability(valid_replicas([1]), candidate=LINE)
    with pytest.raises(V3ContractError):
        reconcile_candidate_pair_v3(
            compact, line, team_size=5,
            line_supervision=supervision_for(line, candidate=LINE))


# =====================================================================
# R14 / R15 / R16 -- row identity
# =====================================================================
def test_row_identity_has_exactly_the_sixteen_frozen_fields():
    assert len(RECOVERABILITY_ROW_IDENTITY_V3_FIELDS) == 16
    key = build_recoverability_row_key_v3(
        study="s", split="v3_train", family="F9", layout_sha256="a" * 64,
        team_size=5, episode_id="e", realized_source_timestep=3, robot_id=0,
        candidate_topology_id=COMPACT, graph_fingerprint="b" * 64)
    assert sorted(key) == sorted(RECOVERABILITY_ROW_IDENTITY_V3_FIELDS)


def test_the_frozen_artifact_agrees_on_the_identity_fields():
    frozen = json.loads(
        (RESULTS / "phase9d_v3f_row_binding_v1.json").read_text())
    assert list(frozen["row_identity_fields"]) == list(
        RECOVERABILITY_ROW_IDENTITY_V3_FIELDS)
    assert frozen["row_identity_field_count"] == 16


@pytest.mark.parametrize("field", ["k", "R", "label", "k_over_R", "worker",
                                   "retry", "path", "timestamp", "replica_index",
                                   "disposition"])
def test_outcome_and_operational_fields_are_refused_in_identity(field):
    key = dict(build_recoverability_row_key_v3(
        study="s", split="v3_train", family="F9", layout_sha256="a" * 64,
        team_size=5, episode_id="e", realized_source_timestep=3, robot_id=0,
        candidate_topology_id=COMPACT, graph_fingerprint="b" * 64))
    key[field] = 1
    with pytest.raises(V3ContractError):
        recoverability_scientific_row_id_v3(key)


def test_the_invalidity_contract_is_not_a_row_identity_field():
    assert ("recoverability_v3_required_replica_invalidity_contract_v1_sha256"
            not in RECOVERABILITY_ROW_IDENTITY_V3_FIELDS)
    assert ("recoverability_v3_required_replica_invalidity_contract_v1_sha256"
            in PROHIBITED_ROW_IDENTITY_V3_FIELDS)


def test_v1_v2_v3_identities_cannot_collide_for_the_same_source_state():
    from rvt_swarm.phase9g0r.contracts import (
        RECOVERABILITY_ROW_IDENTITY_FIELDS, recoverability_scientific_row_id,
    )
    from rvt_swarm.phase9g0r.contracts_v2 import (
        build_recoverability_row_key_v2, recoverability_scientific_row_id_v2,
    )
    common = dict(study="study_a_zero_shot", split="train", family="F9",
                  layout_sha256="a" * 64, team_size=5, episode_id="episode-1",
                  robot_id=2, candidate_topology_id=COMPACT,
                  graph_fingerprint="b" * 64)
    v2 = recoverability_scientific_row_id_v2(build_recoverability_row_key_v2(
        realized_source_timestep=17,
        source_acquisition_protocol_sha256="1" * 64, **common))
    v3 = recoverability_scientific_row_id_v3(build_recoverability_row_key_v3(
        realized_source_timestep=17,
        source_acquisition_protocol_sha256="1" * 64, **common))
    v1_key = {name: common.get(name, "x") for name in
              RECOVERABILITY_ROW_IDENTITY_FIELDS}
    v1_key.update({"schema": "rvt-recoverability-row-identity/v1",
                   "timestep": 17, "target_v4_contract_sha256": "c" * 64,
                   "recoverability_row_binding_spec_sha256": "d" * 64})
    v1 = recoverability_scientific_row_id(v1_key)
    assert len({v1, v2, v3}) == 3


def test_v2_identity_recomputation_is_unchanged_by_v3():
    from rvt_swarm.phase9g0r.contracts_v2 import (
        RECOVERABILITY_ROW_IDENTITY_V2_FIELDS,
        recoverability_row_binding_v2_spec_sha256,
    )
    assert len(RECOVERABILITY_ROW_IDENTITY_V2_FIELDS) == 14
    assert len(recoverability_row_binding_v2_spec_sha256()) == 64


# =====================================================================
# R3 / R5 / R29 -- registry, split authority, dry manifests
# =====================================================================
def test_superseded_registry_hard_fails():
    with pytest.raises(V3CompilerError) as excinfo:
        assert_layout_registry_authoritative(
            SUPERSEDED_LAYOUT_SPLIT_REGISTRY_V1_SHA256)
    assert "SUPERSEDED_PRE_GENERATION_CAPACITY_VERSION" in str(excinfo.value)


def test_an_unknown_registry_also_hard_fails():
    with pytest.raises(V3CompilerError):
        assert_layout_registry_authoritative("f" * 64)


def test_the_authoritative_registry_is_accepted():
    assert assert_layout_registry_authoritative(
        LAYOUT_SPLIT_REGISTRY_V2_SHA256) == LAYOUT_SPLIT_REGISTRY_V2_SHA256
    registry = load_v3_layout_registry(ROOT)
    assert registry["v3_layout_split_registry_v2_sha256"] == (
        LAYOUT_SPLIT_REGISTRY_V2_SHA256)


def test_split_comes_from_membership_not_from_the_layout_id_string():
    registry = load_v3_layout_registry(ROOT)
    # the worked hazard: a TRAIN layout whose id literally says "validation"
    assert v3_split_of_layout(registry, "validation-f1-01") == V3_TRAIN
    assert v3_split_of_layout(registry, "train-f1-02") == V3_TRAIN
    assert v3_split_of_layout(registry, "validation-f1-02") == V3_VALIDATION
    assert v3_split_of_layout(registry, "train-f1-03") is None      # reserve


def test_a_string_parser_would_have_got_the_hazard_wrong():
    registry = load_v3_layout_registry(ROOT)
    naive = "v3_validation" if "validation" in "validation-f1-01" else V3_TRAIN
    assert naive != v3_split_of_layout(registry, "validation-f1-01")


def test_a_layout_outside_the_registry_is_refused():
    registry = load_v3_layout_registry(ROOT)
    with pytest.raises(V3CompilerError):
        v3_split_of_layout(registry, "train-f1-00")


@pytest.mark.parametrize("v3_split,episodes,layouts,per_layout,offsets", [
    (V3_TRAIN, 1200, 20, 60, [0.22, 0.54]),
    (V3_VALIDATION, 300, 10, 30, [0.65]),
])
def test_dry_manifest_shape_is_the_frozen_shape(
        v3_split, episodes, layouts, per_layout, offsets):
    report = v3_manifest_dry_report(ROOT, v3_split=v3_split)
    assert report["source_episodes"] == episodes
    assert report["layout_count"] == layouts
    assert report["episodes_per_layout"] == [per_layout]
    assert report["layout_offsets"] == offsets
    assert report["dry_counters"] == {"executed": 0, "generated": 0, "rows": 0}
    assert report["reserve_offset_present"] is False
    assert report["forbidden_offsets_present"] == []


def test_manifest_roots_are_distinct_from_artifact_hashes():
    for split in (V3_TRAIN, V3_VALIDATION):
        assert FROZEN_V3_MANIFEST_ROOTS[split] != (
            FROZEN_V3_MANIFEST_ARTIFACT_HASHES[split])
        manifest = load_v3_source_manifest(ROOT, v3_split=split)
        report = v3_manifest_dry_report(ROOT, v3_split=split)
        assert report["manifest_root_sha256"] == FROZEN_V3_MANIFEST_ROOTS[split]
        assert report["manifest_artifact_sha256"] == (
            FROZEN_V3_MANIFEST_ARTIFACT_HASHES[split])
        assert manifest is not None


def test_manifests_remain_dry():
    for split in (V3_TRAIN, V3_VALIDATION):
        manifest = load_v3_source_manifest(ROOT, v3_split=split)
        assert assert_manifest_remains_dry(manifest) == {
            "executed": 0, "generated": 0, "rows": 0}


def test_compiled_source_tasks_carry_the_manifest_split_not_the_layout_name():
    tasks = compile_v3_source_tasks(ROOT, v3_split=V3_TRAIN)
    assert len(tasks) == 1200
    assert {task.split for task in tasks} == {V3_TRAIN}
    hazard = [task for task in tasks if task.layout_id.startswith("validation-")]
    assert hazard, "the TRAIN split must contain the validation-named layouts"
    assert {task.split for task in hazard} == {V3_TRAIN}
    assert {task.layout_source_split for task in hazard} == {"validation"}


def test_no_n24_and_no_sealed_study_in_either_split():
    for split in (V3_TRAIN, V3_VALIDATION):
        tasks = compile_v3_source_tasks(ROOT, v3_split=split)
        assert 24 not in {task.team_size for task in tasks}
        assert {task.study for task in tasks} == {"study_a_zero_shot"}


# =====================================================================
# R7 -- replica counts
# =====================================================================
def test_replica_counts_are_the_frozen_ones():
    from rvt_swarm.phase9c_rb.counterfactual import replica_count_for_family
    for family in ("F8", "F9"):
        assert replica_count_for_family(family) == 3
    for family in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F10"):
        assert replica_count_for_family(family) == 1


def test_manifest_replica_plan_matches_the_frozen_protocol():
    for split, r3 in ((V3_TRAIN, 240), (V3_VALIDATION, 60)):
        manifest = load_v3_source_manifest(ROOT, v3_split=split)
        assert manifest["replica_plan"]["episodes_with_R3"] == r3
        assert manifest["replica_plan"]["stochastic_families"] == ["F8", "F9"]


# =====================================================================
# R8 -- matched randomness
# =====================================================================
def test_v3_replica_jobs_derive_the_same_matched_seed_as_v2():
    from rvt_swarm.phase9b.identity import derive_generation_seed
    common = dict(study="study_a_zero_shot", split="v3_train",
                  scenario_family="F9", layout_sha256="a" * 64, team_size=5,
                  source_class="S1_ALWAYS_COMPACT", episode_index=0,
                  event_slot_index=2, replica_index=1)
    matched = derive_generation_seed(
        "counterfactual_rollout", candidate_topology=None, **common)
    compact = derive_generation_seed(
        "counterfactual_rollout", candidate_topology=int(COMPACT), **common)
    line = derive_generation_seed(
        "counterfactual_rollout", candidate_topology=int(LINE), **common)
    assert matched != compact and matched != line
    assert compact != line
    # the matched seed omits the candidate, so COMPACT and LINE share it
    assert matched == derive_generation_seed(
        "counterfactual_rollout", candidate_topology=None, **common)


# =====================================================================
# R20 / R21 / R22 -- loss
# =====================================================================
@pytest.mark.parametrize("k,R", [(0, 1), (1, 1), (0, 3), (1, 3), (2, 3), (3, 3)])
def test_loss_matches_the_frozen_formula(k, R):
    logits = torch.tensor([0.4], dtype=torch.float64)
    stable = candidate_loss(logits, k=k, R=R).item()
    reference = reference_candidate_loss(
        torch.sigmoid(logits).item(), k=k, R=R)
    assert stable == pytest.approx(reference, abs=1e-12)


@pytest.mark.parametrize("k", [0, 1])
def test_R1_reduces_exactly_to_bce_with_logits(k):
    logits = torch.tensor([0.4, -1.3], dtype=torch.float64)
    expected = F.binary_cross_entropy_with_logits(
        logits, torch.full_like(logits, float(k))).item()
    assert candidate_loss(logits, k=k, R=1).item() == expected


def test_loss_is_stable_at_extreme_logits():
    for value in (-80.0, 80.0):
        term = candidate_loss(torch.tensor([value], dtype=torch.float64),
                              k=1, R=3)
        assert torch.isfinite(term).all()


@pytest.mark.parametrize("N,R,k", [(5, 1, 1), (16, 1, 1), (5, 3, 3), (16, 3, 3)])
def test_event_weight_is_invariant_to_N_and_R(N, R, k):
    logits = torch.full((N,), 0.37, dtype=torch.float64)
    value = event_loss(compact_logits=logits, compact_k=k, compact_R=R,
                       line_logits=logits, line_k=k, line_R=R).item()
    baseline = event_loss(
        compact_logits=torch.full((5,), 0.37, dtype=torch.float64),
        compact_k=1, compact_R=1,
        line_logits=torch.full((5,), 0.37, dtype=torch.float64),
        line_k=1, line_R=1).item()
    assert value == pytest.approx(baseline, abs=1e-12)


def test_identical_k_over_R_gives_an_identical_event_loss():
    logits = torch.full((8,), -0.2, dtype=torch.float64)
    one = event_loss(compact_logits=logits, compact_k=1, compact_R=1,
                     line_logits=logits, line_k=1, line_R=1).item()
    three = event_loss(compact_logits=logits, compact_k=3, compact_R=3,
                       line_logits=logits, line_k=3, line_R=3).item()
    assert one == pytest.approx(three, abs=1e-12)


def test_per_replica_masking_is_impossible_to_express():
    with pytest.raises(V3LossContractError):
        grouped_bernoulli_nll(torch.tensor([0.1]), k=1, R=3,
                              replica_mask=[True, False, True])


def test_the_loss_refuses_an_impossible_observation():
    for k, R in ((4, 3), (-1, 3), (1, 0)):
        with pytest.raises(V3LossContractError):
            candidate_loss(torch.tensor([0.1]), k=k, R=R)


def test_dataset_loss_weights_every_event_equally():
    small = {"compact_logits": torch.full((5,), 0.1, dtype=torch.float64),
             "compact_k": 1, "compact_R": 1,
             "line_logits": torch.full((5,), 0.1, dtype=torch.float64),
             "line_k": 1, "line_R": 1}
    large = {"compact_logits": torch.full((16,), 0.9, dtype=torch.float64),
             "compact_k": 3, "compact_R": 3,
             "line_logits": torch.full((16,), 0.9, dtype=torch.float64),
             "line_k": 3, "line_R": 3}
    mean = dataset_loss([small, large]).item()
    expected = 0.5 * (event_loss(**small).item() + event_loss(**large).item())
    assert mean == pytest.approx(expected, abs=1e-12)


# =====================================================================
# R23 / R24 / R25 -- Brier
# =====================================================================
def test_mandatory_brier_anti_shortcut_fixture():
    value = brier_robot(torch.tensor([0.5], dtype=torch.float64), k=1, R=3).item()
    assert value == pytest.approx(0.25, abs=1e-12)
    shortcut = (0.5 - 1 / 3) ** 2
    assert shortcut == pytest.approx(0.027777777777, abs=1e-9)
    assert abs(value - shortcut) > 0.2


@pytest.mark.parametrize("k,R,outcomes", [
    (0, 1, [0]), (1, 1, [1]), (0, 3, [0, 0, 0]), (1, 3, [1, 0, 0]),
    (2, 3, [1, 1, 0]), (3, 3, [1, 1, 1]),
])
def test_closed_form_equals_the_literal_replica_definition(k, R, outcomes):
    for p in (0.1, 0.5, 0.73, 0.999):
        probability = torch.tensor([p], dtype=torch.float64)
        closed = brier_robot(probability, k=k, R=R).item()
        literal = brier_from_replica_outcomes(probability, outcomes).item()
        assert closed == pytest.approx(literal, abs=1e-12)


@pytest.mark.parametrize("k,R,expected", [
    (0, 1, 0.25), (1, 1, 0.25), (0, 3, 0.25), (1, 3, 0.25),
    (2, 3, 0.25), (3, 3, 0.25),
])
def test_all_required_k_R_fixtures_at_p_half(k, R, expected):
    value = brier_robot(torch.tensor([0.5], dtype=torch.float64), k=k, R=R).item()
    assert value == pytest.approx(expected, abs=1e-12)


def test_brier_distinguishes_mixed_from_unanimous_away_from_p_half():
    p = torch.tensor([0.9], dtype=torch.float64)
    unanimous = brier_robot(p, k=3, R=3).item()
    mixed = brier_robot(p, k=1, R=3).item()
    assert unanimous < mixed
    assert unanimous == pytest.approx(0.01, abs=1e-12)


def test_brier_refuses_an_invalid_replica_outcome():
    with pytest.raises(V3MetricContractError):
        brier_from_replica_outcomes(torch.tensor([0.5]), [1, None, 0])


def test_brier_event_weight_is_invariant_to_N_and_R():
    for N, R, k in ((5, 1, 1), (16, 1, 1), (5, 3, 3), (16, 3, 3)):
        probabilities = torch.full((N,), 0.7, dtype=torch.float64)
        value = brier_event(
            compact_probabilities=probabilities, compact_k=k, compact_R=R,
            line_probabilities=probabilities, line_k=k, line_R=R).item()
        assert value == pytest.approx(0.09, abs=1e-12)


def test_brier_split_is_an_event_mean_not_a_row_mean():
    small = {"compact_probabilities": torch.full((2,), 0.5, dtype=torch.float64),
             "compact_k": 1, "compact_R": 3,
             "line_probabilities": torch.full((2,), 0.5, dtype=torch.float64),
             "line_k": 1, "line_R": 3}
    large = {"compact_probabilities": torch.full((16,), 0.9, dtype=torch.float64),
             "compact_k": 3, "compact_R": 3,
             "line_probabilities": torch.full((16,), 0.9, dtype=torch.float64),
             "line_k": 3, "line_R": 3}
    value = brier_split([small, large]).item()
    assert value == pytest.approx(0.5 * (0.25 + 0.01), abs=1e-12)
    row_mean = (2 * 2 * 0.25 + 16 * 2 * 0.01) / (2 * 2 + 16 * 2)
    assert value != pytest.approx(row_mean, abs=1e-6)


# =====================================================================
# R19 / R26 / R27 -- loader
# =====================================================================
def build_transaction(*, event="event-1", team_size=3, compact_labels=(1, 0, 1),
                      line_labels=(0, 0, 0), split="v3_train"):
    compact = labelability(valid_replicas(list(compact_labels)),
                           candidate=COMPACT, event=event)
    line = labelability(valid_replicas(list(line_labels)),
                        candidate=LINE, event=event)
    rows_c = [row_stub(COMPACT, index, split=split, event=event)
              for index in range(team_size)]
    rows_l = [row_stub(LINE, index, split=split, event=event)
              for index in range(team_size)]
    for index, row in enumerate(rows_c + rows_l):
        row["scientific_identity"] = dict(row["scientific_identity"],
                                          episode_id=event)
        row["scientific_row_id"] = recoverability_scientific_row_id_v3(
            row["scientific_identity"])
    return reconcile_candidate_pair_v3(
        compact, line, team_size=team_size,
        compact_supervision=supervision_for(compact, candidate=COMPACT),
        line_supervision=supervision_for(line, candidate=LINE),
        compact_rows=rows_c, line_rows=rows_l).as_dict()


def test_loader_groups_by_event_then_candidate_then_robot():
    group = event_group_from_transaction(build_transaction(), split="v3_train")
    assert group.team_size == 3
    assert group.row_count == 6
    assert (group.compact.k, group.compact.R) == (2, 3)
    assert (group.line.k, group.line.R) == (0, 3)
    assert set(group.candidates()) == {COMPACT, LINE}


def test_loader_refuses_a_non_labelable_pair():
    compact = labelability([replica(0, INVALID)], candidate=COMPACT, R=1)
    line = labelability(valid_replicas([1]), candidate=LINE)
    transaction = reconcile_candidate_pair_v3(
        compact, line, team_size=5).as_dict()
    with pytest.raises(V3LoaderError):
        event_group_from_transaction(transaction, split="v3_train")


def test_loader_refuses_a_v2_schema_row():
    transaction = build_transaction()
    transaction["rows"][0]["schema_version"] = (
        "rvt-recoverability-v2-supervision-row/v1")
    with pytest.raises(V3LoaderError):
        event_group_from_transaction(transaction, split="v3_train")


def test_loader_enforces_the_split_boundary():
    transaction = build_transaction(split="v3_train")
    with pytest.raises(V3LoaderError):
        event_group_from_transaction(transaction, split="v3_validation")


def test_loader_refuses_a_transaction_without_the_invalidity_contract():
    transaction = build_transaction()
    transaction[
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    ] = "0" * 64
    with pytest.raises(V3LoaderError):
        event_group_from_transaction(transaction, split="v3_train")


def test_membership_is_identical_under_every_ordering():
    documents = [build_transaction(event=f"event-{index}")
                 for index in range(6)]
    sequential = load_v3_event_groups(documents, split="v3_train")
    reversed_groups = load_v3_event_groups(list(reversed(documents)),
                                           split="v3_train")
    shuffled = deterministic_event_order(sequential, seed=11)
    batched = [group for batch in batch_event_groups(shuffled, events_per_batch=4)
               for group in batch]
    base = scientific_membership(sequential)
    assert scientific_membership(reversed_groups) == base
    assert scientific_membership(shuffled) == base
    assert scientific_membership(batched) == base
    assert base["events"] == 6 and base["rows"] == 36


def test_the_frozen_shuffle_is_reproducible_and_actually_reorders():
    documents = [build_transaction(event=f"event-{index}") for index in range(8)]
    groups = load_v3_event_groups(documents, split="v3_train")
    first = deterministic_event_order(groups, seed=29)
    again = deterministic_event_order(groups, seed=29)
    other = deterministic_event_order(groups, seed=47)
    ids = [group.decision_event_id for group in first]
    assert ids == [group.decision_event_id for group in again]
    assert ids != [group.decision_event_id for group in groups]
    assert ids != [group.decision_event_id for group in other]


# =====================================================================
# R17 -- writer
# =====================================================================
def test_writer_publishes_only_labelable_pairs(tmp_path):
    writer = V3SupervisedDatasetWriter(tmp_path / "diag", mode="DIAGNOSTIC")
    compact = labelability(valid_replicas([1, 0, 1]), candidate=COMPACT)
    line = labelability(valid_replicas([1, 1, 1]), candidate=LINE)
    transaction = reconcile_candidate_pair_v3(
        compact, line, team_size=4,
        compact_supervision=supervision_for(compact, candidate=COMPACT),
        line_supervision=supervision_for(line, candidate=LINE),
        compact_rows=[row_stub(COMPACT, i) for i in range(4)],
        line_rows=[row_stub(LINE, i) for i in range(4)])
    result = writer.write_v3_transaction(transaction, audit={"note": "canary"})
    assert result["rows"] == 8
    assert writer.rows_written == 8
    assert "v3_recoverability" in result["path"]


def test_writer_is_idempotent_and_refuses_a_conflicting_payload(tmp_path):
    writer = V3SupervisedDatasetWriter(tmp_path / "diag", mode="DIAGNOSTIC")
    compact = labelability(valid_replicas([1]), candidate=COMPACT)
    line = labelability(valid_replicas([0]), candidate=LINE)
    transaction = reconcile_candidate_pair_v3(
        compact, line, team_size=2,
        compact_supervision=supervision_for(compact, candidate=COMPACT),
        line_supervision=supervision_for(line, candidate=LINE),
        compact_rows=[row_stub(COMPACT, i) for i in range(2)],
        line_rows=[row_stub(LINE, i) for i in range(2)])
    first = writer.write_v3_transaction(transaction, audit={})
    second = writer.write_v3_transaction(transaction, audit={})
    assert first["duplicate_replay"] is False
    assert second["duplicate_replay"] is True
    assert writer.transactions_written == 1


def test_writer_refuses_a_final_namespace(tmp_path):
    with pytest.raises(PermissionError):
        V3SupervisedDatasetWriter(tmp_path / "final", mode="DIAGNOSTIC")


def test_audit_record_never_carries_supervised_rows(tmp_path):
    writer = V3SupervisedDatasetWriter(tmp_path / "diag", mode="DIAGNOSTIC")
    result = writer.write_v3_audit_record(
        decision_event_id="event-9",
        record={"status": PAIR_STATUS_GENERATION_INVALID,
                "generation_invalid_replica_indices": [1]})
    document = json.loads(pathlib.Path(result["path"]).read_text())
    assert document["supervised_rows"] == 0
    assert "rows" not in document


# =====================================================================
# R15 -- provenance binding sites
# =====================================================================
def test_manifest_and_seal_bind_the_invalidity_contract():
    accounting = S8InvalidRateAccounting()
    accounting.record_replica(family="F9", disposition=VALID_POSITIVE)
    manifest = build_v3_dataset_manifest(
        v3_split=V3_TRAIN, dataset_id="qual", source_manifest_root_sha256="a" * 64,
        layout_registry_sha256=LAYOUT_SPLIT_REGISTRY_V2_SHA256,
        execution_spec_registry_sha256="e" * 64,
        accounting=accounting, source_episodes_executed=1,
        selected_source_events=1, pair_events_retained=1,
        pair_events_dropped_scientific_invalidity=0,
        candidate_supervision_records=2, candidate_supervision_blocked=0,
        rows_published=2, row_ids=["a" * 64, "b" * 64])
    assert manifest[
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    ] == INVALIDITY_CONTRACT_V3_SHA256
    assert verify_canonical_hash(manifest, "v3_dataset_manifest_sha256")
    seal = seal_v3_dataset(manifest)
    assert seal[
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    ] == INVALIDITY_CONTRACT_V3_SHA256
    assert verify_canonical_hash(seal, "v3_dataset_seal_sha256")
    assert seal["v3_dataset_manifest_sha256"] == (
        manifest["v3_dataset_manifest_sha256"])


def test_the_manifest_carries_the_c13_invalidity_accounting():
    accounting = S8InvalidRateAccounting()
    for _ in range(5):
        accounting.record_replica(family="F9", disposition=VALID_POSITIVE)
    accounting.record_replica(family="F9", disposition=INVALID)
    manifest = build_v3_dataset_manifest(
        v3_split=V3_TRAIN, dataset_id="qual", source_manifest_root_sha256="a" * 64,
        layout_registry_sha256=LAYOUT_SPLIT_REGISTRY_V2_SHA256,
        execution_spec_registry_sha256="e" * 64,
        accounting=accounting, source_episodes_executed=2,
        selected_source_events=2, pair_events_retained=1,
        pair_events_dropped_scientific_invalidity=1,
        candidate_supervision_records=2, candidate_supervision_blocked=1,
        rows_published=0, row_ids=[])
    counters = manifest["invalidity_accounting"]
    assert counters["required_replica_evaluations"] == 6
    assert counters["scientifically_valid_replicas"] == 5
    assert counters["generation_invalid_replicas"] == 1
    assert counters["pair_events_dropped_scientific_invalidity"] == 1
    assert counters["candidate_supervision_blocked"] == 1
    assert manifest["placeholder_rows"] == 0
    assert manifest["s8"]["denominator"] == 6


def test_the_frozen_provenance_binding_artifact_agrees():
    frozen = json.loads(
        (RESULTS / "phase9d_v3f_i_provenance_binding_v1.json").read_text())
    binds = {item["object"] for item in frozen["objects"]
             if item["binds_invalidity_contract"]}
    assert binds == {"candidate supervision provenance",
                     "pair transaction provenance", "V3 dataset manifest",
                     "V3 dataset seal"}
    assert frozen["row_binding_v3_determination"]["row_binding_v3_modified"] is False


# =====================================================================
# R18 -- graph input semantics
# =====================================================================
def test_frozen_robot_local_graph_dimensions_are_unchanged():
    from rvt_swarm.decentralized.ego_graph_v2 import (
        EDGE_FEATURE_DIM, NODE_FEATURE_DIM,
    )
    assert NODE_FEATURE_DIM == 35
    assert EDGE_FEATURE_DIM == 19


def test_the_recoverability_head_is_reused_not_replaced():
    """R28: the existing head already emits a candidate-conditioned logit."""
    from rvt_swarm.fd24.model import FD24RecoverabilityHead, RVTFD24LocalModel
    assert hasattr(RVTFD24LocalModel, "forward")
    assert hasattr(FD24RecoverabilityHead, "forward")
    source = pathlib.Path("rvt_swarm/fd24/model.py").read_text()
    assert "self.recoverability_head = FD24RecoverabilityHead(" in source
    assert "probability = torch.sigmoid(logits)" in source


def test_v3_adds_no_model_parameters():
    """The V3 loss and metric consume the existing logit; nothing is bolted on."""
    for module in ("rvt_swarm/fd24/loss_v3.py", "rvt_swarm/fd24/metrics_v3.py",
                   "rvt_swarm/fd24/loader_v3.py"):
        source = pathlib.Path(module).read_text()
        assert "nn.Module" not in source
        assert "nn.Parameter" not in source
        assert "nn.Linear" not in source


# =====================================================================
# R39 -- V1/V2 unchanged
# =====================================================================
def test_historical_gate_7_is_still_a_failure_for_v2():
    record = json.loads(
        (RESULTS / "phase9d_v2c_r_gate7_replica_instability_v1.json").read_text())
    assert record["result"] == "FAIL"
    assert 59 / 530 == pytest.approx(0.11132075471698114, abs=1e-15)
    assert 59 / 530 > 0.10


def test_v3_modules_do_not_import_into_the_v1_v2_paths():
    for name in ("producer.py", "producer_v2.py", "compiler.py",
                 "compiler_v2.py", "contracts.py", "contracts_v2.py",
                 "writer.py"):
        source = pathlib.Path("rvt_swarm/phase9g0r") / name
        assert "_v3" not in source.read_text(), (
            f"{name} must not depend on the additive V3 modules")
