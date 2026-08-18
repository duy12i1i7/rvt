"""Recoverability V3 production -- probabilistic (k, R) supervision.

The candidate rollout itself is *not* reimplemented. V3 calls the frozen
:func:`produce_recoverability_candidate`, which already executes every replica
before aggregating and only short-circuits on infrastructure retry exhaustion.
That is exactly owner-ratified clause C7: scientific invalidity never stops a
candidate. Reusing the qualified producer is what makes the no-early-abort
guarantee structural rather than a promise.

What V3 adds on top:

* per-replica evidence is kept, not discarded -- V2 threw it away and the
  gate-7 forensics had to replay the entire dataset to get it back;
* candidate labelability is decided by the frozen invalidity contract;
* the pair publishes ``2 * N`` rows or none;
* S8 counts every executed required rollout, including those whose rows were
  censored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..phase9c_rb.counterfactual import replica_count_for_family
from ..topology_registry import COMPACT, LINE
from .compiler import OfficialDecisionEventTask
from .compiler_v2 import V2SourceAcquisition
from .compiler_v3 import compile_recoverability_v3_candidate_tasks
from .contracts import GENERATION_INVALID, INFRASTRUCTURE_FAILURE
from .contracts_v3 import (
    INVALIDITY_CONTRACT_V3_SHA256, PROBABILISTIC_TARGET_V3_SHA256,
    RECOVERABILITY_PROTOCOL_V3, REPLICA_PROTOCOL_V3_SHA256,
    ROW_BINDING_V3_SPEC_SHA256, SOURCE_ACQUISITION_PROTOCOL_SHA256,
    S8InvalidRateAccounting, V3CandidateLabelability, V3ContractError,
    V3PairTransaction, build_candidate_supervision, build_recoverability_row_key_v3,
    candidate_evaluation_id_v3, evaluate_candidate_labelability,
    reconcile_candidate_pair_v3, recoverability_scientific_row_id_v3,
    replica_evaluation_id_v3, require_invalidity_contract,
)
from .producer import produce_recoverability_candidate

V3_EVENT_RESULT_SCHEMA_VERSION = "rvt-official-recoverability-v3-event-result/v1"
V3_ROW_SCHEMA_VERSION = "rvt-recoverability-v3-supervision-row/v1"


class V3ProducerError(V3ContractError):
    """A V3 production invariant that must not be papered over."""


def planned_required_replica_executions(task: OfficialDecisionEventTask) -> int:
    """The compute path a source event commits to before any outcome exists.

    Outcome-independent by construction: it depends only on the frozen replica
    count and the two candidates, never on what any replica returned.
    """
    return 2 * int(task.replicas_per_candidate)


def _replica_evidence(
    result: Mapping[str, Any], *, candidate_evaluation_id: str,
) -> Tuple[Mapping[str, Any], ...]:
    """Per-replica scientific evidence, ordered by replica index."""
    audit = result.get("candidate_audit") or {}
    evidence = []
    for replica in audit.get("replicas", ()):  # already in execution order
        replica_index = int(replica["replica_index"])
        disposition = str(replica["disposition"])
        evidence.append({
            "replica_index": replica_index,
            "replica_evaluation_id": replica_evaluation_id_v3(
                candidate_evaluation_id=candidate_evaluation_id,
                replica_index=replica_index,
                matched_disturbance_stream_identity=str(
                    replica["matched_disturbance_seed"])),
            "matched_disturbance_seed": int(replica["matched_disturbance_seed"]),
            "disposition": disposition,
            # A scientifically invalid replica has no Bernoulli outcome. The
            # key is present and null; it is never filled in with 0 or 1.
            "target_v4_label": (None if disposition == GENERATION_INVALID
                                else int(replica["label"])),
            "termination_cause": replica["termination_cause"],
            "failed_predicates": list(replica["failed_predicates"]),
            "safety_infeasible_robots": int(replica["safety_infeasible_robots"]),
            "safety_solver_failure_robots": int(
                replica["safety_solver_failure_robots"]),
            "created_lifecycle": bool(replica["created_lifecycle"]),
            "control_steps": int(replica["control_steps"]),
            "initial_clone_hash": replica["initial_clone_hash"],
            "final_state_hash": replica["final_state_hash"],
            "rollout_configuration_sha256": replica["rollout_configuration_sha256"],
        })
    return tuple(sorted(evidence, key=lambda item: item["replica_index"]))


def _labelability(
    task: OfficialDecisionEventTask, candidate: int,
    result: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]],
) -> V3CandidateLabelability:
    unresolved = (
        str(dict(result["disposition"])["disposition"]) == INFRASTRUCTURE_FAILURE)
    replicas = [
        {"replica_index": item["replica_index"],
         "disposition": item["disposition"],
         "label": item["target_v4_label"]}
        for item in evidence
    ]
    return evaluate_candidate_labelability(
        decision_event_id=task.event_id,
        candidate_topology_id=int(candidate),
        R_required=int(task.replicas_per_candidate),
        replicas=replicas,
        infrastructure_unresolved=unresolved)


def _v3_rows(
    task: OfficialDecisionEventTask, candidate: int, result: Mapping[str, Any],
) -> Tuple[Mapping[str, Any], ...]:
    """One row per robot. Identity carries no outcome, ever."""
    rows = []
    for graph in result["graphs"]:
        key = build_recoverability_row_key_v3(
            study=task.source.study, split=task.source.split,
            family=task.source.family, layout_sha256=task.source.layout_sha256,
            team_size=task.source.team_size, episode_id=task.source.job_id,
            realized_source_timestep=task.resolved_control_step,
            robot_id=int(graph["robot_id"]),
            candidate_topology_id=int(candidate),
            graph_fingerprint=str(graph["graph_fingerprint"]),
            source_acquisition_protocol_sha256=SOURCE_ACQUISITION_PROTOCOL_SHA256)
        rows.append({
            "schema_version": V3_ROW_SCHEMA_VERSION,
            "protocol_version": RECOVERABILITY_PROTOCOL_V3,
            "scientific_row_id": recoverability_scientific_row_id_v3(key),
            "scientific_identity": key,
            "graph_payload_schema_version":
                "rvt-recoverability-ego-payload-binding/v1",
            "graph_payload": graph["graph_payload"],
        })
    return tuple(rows)


def produce_recoverability_v3_event(
    root: Path,
    task: OfficialDecisionEventTask,
    *,
    source_acquisition_protocol_sha256: str = SOURCE_ACQUISITION_PROTOCOL_SHA256,
    invalidity_contract_sha256: str = INVALIDITY_CONTRACT_V3_SHA256,
    writer: Optional[Any] = None,
    accounting: Optional[S8InvalidRateAccounting] = None,
    candidate_order: Sequence[int] = (COMPACT, LINE),
) -> Mapping[str, Any]:
    """Execute both candidates for one V3 source event and reconcile the pair.

    ``candidate_order`` exists so qualification can prove order invariance. It
    changes execution order only; the reconciliation is always COMPACT-then-LINE.
    """
    require_invalidity_contract(invalidity_contract_sha256)
    if sorted(int(item) for item in candidate_order) != sorted((COMPACT, LINE)):
        raise V3ProducerError("a V3 event must evaluate exactly COMPACT and LINE")
    expected_replicas = replica_count_for_family(task.source.family)
    if int(task.replicas_per_candidate) != expected_replicas:
        raise V3ProducerError(
            f"{task.source.family} declares R = {task.replicas_per_candidate} "
            f"against the frozen protocol's {expected_replicas}")

    planned = planned_required_replica_executions(task)
    by_candidate: Dict[int, Mapping[str, Any]] = {}
    evidence_by_candidate: Dict[int, Tuple[Mapping[str, Any], ...]] = {}
    evaluation_ids: Dict[int, str] = {}

    for candidate in candidate_order:
        candidate = int(candidate)
        result = produce_recoverability_candidate(root, task, candidate)
        if bool(result["source_terminated_before_event"]):
            # Stage A only selects realized states, so this is a divergence
            # between the acquisition record and the producer, never a
            # scientific GENERATION_INVALID.
            raise V3ProducerError(
                "a V3 candidate task pointed at a source state the trajectory "
                "never reached; V3 must never convert this into "
                "GENERATION_INVALID")
        evaluation_id = candidate_evaluation_id_v3(
            candidate_event_id=task.event_id, candidate_topology_id=candidate)
        evaluation_ids[candidate] = evaluation_id
        evidence = _replica_evidence(
            result, candidate_evaluation_id=evaluation_id)
        by_candidate[candidate] = result
        evidence_by_candidate[candidate] = evidence

    executed = sum(len(items) for items in evidence_by_candidate.values())
    states = {
        candidate: _labelability(
            task, candidate, by_candidate[candidate],
            evidence_by_candidate[candidate])
        for candidate in (COMPACT, LINE)
    }
    unresolved = any(state.infrastructure_unresolved for state in states.values())
    if not unresolved and executed != planned:
        raise V3ProducerError(
            f"C7 violation: {executed} required replica rollouts executed "
            f"against the {planned} the event committed to before any outcome "
            "existed")

    if accounting is not None:
        for candidate in (COMPACT, LINE):
            for item in evidence_by_candidate[candidate]:
                accounting.record_replica(
                    family=task.source.family, disposition=item["disposition"])

    supervision = {
        candidate: build_candidate_supervision(
            states[candidate],
            candidate_evaluation_id=evaluation_ids[candidate],
            replica_evaluation_ids=[
                item["replica_evaluation_id"]
                for item in evidence_by_candidate[candidate]],
            replica_dispositions=[
                item["disposition"]
                for item in evidence_by_candidate[candidate]])
        for candidate in (COMPACT, LINE)
    }
    both_labelable = all(state.labelable for state in states.values())
    rows = {
        candidate: (_v3_rows(task, candidate, by_candidate[candidate])
                    if both_labelable else ())
        for candidate in (COMPACT, LINE)
    }

    transaction = reconcile_candidate_pair_v3(
        states[COMPACT], states[LINE], team_size=int(task.source.team_size),
        compact_supervision=supervision[COMPACT],
        line_supervision=supervision[LINE],
        compact_rows=rows[COMPACT], line_rows=rows[LINE])

    if writer is not None and transaction.training_rows_committable:
        writer.write_v3_transaction(transaction, audit={
            "decision_event_id": task.event_id,
            "replica_evidence": {
                str(candidate): [dict(item) for item in items]
                for candidate, items in sorted(evidence_by_candidate.items())},
        })

    return {
        "schema_version": V3_EVENT_RESULT_SCHEMA_VERSION,
        "protocol_version": RECOVERABILITY_PROTOCOL_V3,
        "decision_event_id": task.event_id,
        "family": task.source.family,
        "team_size": int(task.source.team_size),
        "realized_source_timestep": int(task.resolved_control_step),
        "source_acquisition_protocol_sha256": source_acquisition_protocol_sha256,
        "recoverability_probabilistic_target_v3_sha256":
            PROBABILISTIC_TARGET_V3_SHA256,
        "recoverability_replica_protocol_v3_sha256": REPLICA_PROTOCOL_V3_SHA256,
        "recoverability_row_binding_v3_spec_sha256": ROW_BINDING_V3_SPEC_SHA256,
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
            invalidity_contract_sha256,
        "R_required": int(task.replicas_per_candidate),
        "planned_required_replica_executions": planned,
        "executed_required_replica_rollouts": executed,
        "early_abort_on_scientific_invalidity": False,
        "candidate_execution_order": [int(item) for item in candidate_order],
        "replica_evidence": {
            str(candidate): [dict(item) for item in items]
            for candidate, items in sorted(evidence_by_candidate.items())},
        "labelability": dict(transaction.labelability),
        "supervision": dict(transaction.supervision),
        "status": transaction.status,
        "scientifically_reconciled": transaction.scientifically_reconciled,
        "training_rows_committable": transaction.training_rows_committable,
        "expected_row_count": transaction.expected_row_count,
        "actual_row_count": transaction.actual_row_count,
        "rows": list(transaction.rows),
        "replacement_replicas_sampled": 0,
        "imputed_bernoulli_outcomes": 0,
        "fake_generation_invalid_emitted": 0,
    }


def produce_recoverability_v3_episode(
    root: Path, acquisition: V2SourceAcquisition, *,
    writer: Optional[Any] = None,
    accounting: Optional[S8InvalidRateAccounting] = None,
) -> Mapping[str, Any]:
    """Stage B for one V3 episode. ``M = 0`` yields zero tasks and zero rows."""
    tasks = compile_recoverability_v3_candidate_tasks(acquisition)
    events = [
        produce_recoverability_v3_event(
            root, task,
            source_acquisition_protocol_sha256=acquisition.protocol_sha256,
            writer=writer, accounting=accounting)
        for task in tasks
    ]
    return {
        "protocol_version": RECOVERABILITY_PROTOCOL_V3,
        "episode_id": acquisition.source.job_id,
        "family": acquisition.source.family,
        "M": acquisition.M,
        "selected_source_events": acquisition.selected_event_count,
        "candidate_tasks": len(tasks),
        "events": events,
        "rows_published": sum(event["actual_row_count"] for event in events),
        "pair_events_retained": sum(
            1 for event in events if event["training_rows_committable"]),
        "pair_events_dropped_scientific_invalidity": sum(
            1 for event in events
            if event["status"] == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID"),
        "executed_required_replica_rollouts": sum(
            event["executed_required_replica_rollouts"] for event in events),
        "replacement_replicas_sampled": 0,
        "fake_generation_invalid_emitted": 0,
    }
