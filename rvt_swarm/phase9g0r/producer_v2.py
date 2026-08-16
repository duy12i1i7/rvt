"""Recoverability V2 production behaviour, dispatched by protocol version.

Phase 9G-V2Q finding V2Q-F2: the V1 producer turns "the source terminated
before the planned event" into a `GENERATION_INVALID` candidate aggregate. That
branch is historically required for V1 replay, so it is left untouched here and
dispatched around instead (I12).

Under V2 that branch is unreachable *by construction*: every
`resolved_control_step` handed to the producer is a control step the source
trajectory demonstrably attained, because Stage A selected it from the realized
universe. This module asserts that invariant rather than assuming it, and
refuses to publish if it is ever violated.

The candidate science itself is untouched (I13). `produce_recoverability_candidate`
is the real production path and is reused verbatim: same snapshot, same graphs,
same matched randomness, same Target V4, same replica rules, same aggregation.
Only the row identity is V2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from ..topology_registry import COMPACT, LINE
from .compiler import OfficialDecisionEventTask
from .compiler_v2 import V2SourceAcquisition, compile_recoverability_v2_candidate_tasks
from .contracts import (
    CandidateAggregateDisposition, GENERATION_INVALID, Phase9G0RContractError,
    reconcile_candidate_pair,
)
from .contracts_v2 import (
    RECOVERABILITY_PROTOCOL_V1, RECOVERABILITY_PROTOCOL_V2, RECOVERABILITY_PROTOCOLS,
    build_recoverability_row_key_v2, recoverability_row_binding_v2_spec_sha256,
    recoverability_scientific_row_id_v2,
)
from .producer import (
    OfficialProducerError, produce_recoverability_candidate,
    produce_recoverability_event,
)

V2_EVENT_RESULT_SCHEMA_VERSION = "rvt-official-recoverability-v2-event-result/v1"
V2_ROW_SCHEMA_VERSION = "rvt-recoverability-scientific-row/v2"


class V2ProducerError(OfficialProducerError):
    """A V2 production invariant that must not be papered over."""


def _v2_rows(task: OfficialDecisionEventTask, candidate: int,
             result: Mapping[str, Any], protocol_sha256: str,
             binding_sha256: str) -> Sequence[Mapping[str, Any]]:
    rows = []
    for graph in result["graphs"]:
        key = build_recoverability_row_key_v2(
            study=task.source.study, split=task.source.split,
            family=task.source.family, layout_sha256=task.source.layout_sha256,
            team_size=task.source.team_size, episode_id=task.source.job_id,
            realized_source_timestep=task.resolved_control_step,
            robot_id=int(graph["robot_id"]), candidate_topology_id=int(candidate),
            graph_fingerprint=str(graph["graph_fingerprint"]),
            source_acquisition_protocol_sha256=protocol_sha256,
            row_binding_v2_spec_sha256=binding_sha256)
        rows.append({
            "schema_version": V2_ROW_SCHEMA_VERSION,
            "protocol_version": RECOVERABILITY_PROTOCOL_V2,
            "scientific_row_id": recoverability_scientific_row_id_v2(key),
            "scientific_identity": key,
            "graph_payload_schema_version":
                "rvt-recoverability-ego-payload-binding/v1",
            "graph_payload": graph["graph_payload"],
        })
    return tuple(rows)


def produce_recoverability_v2_event(
    root: Path,
    task: OfficialDecisionEventTask,
    *,
    source_acquisition_protocol_sha256: str,
    writer: Optional[Any] = None,
) -> Mapping[str, Any]:
    """Execute both candidates for one realized V2 source event and reconcile."""
    binding_sha256 = recoverability_row_binding_v2_spec_sha256()
    by_candidate = {}
    for candidate in (COMPACT, LINE):
        result = produce_recoverability_candidate(root, task, candidate)
        if bool(result["source_terminated_before_event"]):
            # Under V2 this is impossible: Stage A only selects realized states.
            # If it ever fires, the acquisition record and the producer have
            # diverged and nothing may be published.
            raise V2ProducerError(
                "V2 candidate task pointed at a source state the trajectory never "
                "reached; V2 must never convert this into GENERATION_INVALID")
        by_candidate[candidate] = result

    dispositions = {
        candidate: CandidateAggregateDisposition(**dict(result["disposition"]))
        for candidate, result in by_candidate.items()
    }
    labelable = all(item.disposition not in (GENERATION_INVALID,)
                    and item.aggregate_label is not None
                    for item in dispositions.values())
    compact_rows: Sequence[Mapping[str, Any]] = ()
    line_rows: Sequence[Mapping[str, Any]] = ()
    if labelable:
        compact_rows = _v2_rows(task, COMPACT, by_candidate[COMPACT],
                                source_acquisition_protocol_sha256, binding_sha256)
        line_rows = _v2_rows(task, LINE, by_candidate[LINE],
                             source_acquisition_protocol_sha256, binding_sha256)

    reconciliation = reconcile_candidate_pair(
        dispositions[COMPACT], dispositions[LINE],
        team_size=task.source.team_size,
        compact_rows=compact_rows, line_rows=line_rows)

    if reconciliation.training_rows_committable and writer is not None:
        writer.write_recoverability_transaction(task.event_id, reconciliation.rows)

    return {
        "schema_version": V2_EVENT_RESULT_SCHEMA_VERSION,
        "protocol_version": RECOVERABILITY_PROTOCOL_V2,
        "decision_event_id": task.event_id,
        "source_acquisition_protocol_sha256": source_acquisition_protocol_sha256,
        "recoverability_row_binding_v2_spec_sha256": binding_sha256,
        "realized_source_timestep": task.resolved_control_step,
        "team_size": task.source.team_size,
        "source_snapshot_sha256": by_candidate[COMPACT]["source_snapshot_sha256"],
        "dispositions": {str(int(candidate)): dict(result["disposition"])
                         for candidate, result in by_candidate.items()},
        "status": reconciliation.status,
        "scientifically_reconciled": reconciliation.scientifically_reconciled,
        "training_rows_committable": reconciliation.training_rows_committable,
        "expected_row_count": reconciliation.expected_row_count,
        "actual_row_count": reconciliation.actual_row_count,
        "rows": reconciliation.rows,
        "fake_generation_invalid_emitted": 0,
    }


def produce_recoverability_v2_episode(
    root: Path, acquisition: V2SourceAcquisition, *, writer: Optional[Any] = None,
) -> Mapping[str, Any]:
    """Stage B for one episode. `M = 0` yields zero tasks and zero results."""
    tasks = compile_recoverability_v2_candidate_tasks(acquisition)
    events = [
        produce_recoverability_v2_event(
            root, task,
            source_acquisition_protocol_sha256=acquisition.protocol_sha256,
            writer=writer)
        for task in tasks
    ]
    return {
        "protocol_version": RECOVERABILITY_PROTOCOL_V2,
        "episode_id": acquisition.source.job_id,
        "M": acquisition.M,
        "selected_source_events": acquisition.selected_event_count,
        "candidate_tasks": len(tasks),
        "events": events,
        "rows_published": sum(event["actual_row_count"] for event in events),
        "fake_generation_invalid_emitted": 0,
    }


# ---------------------------------------------------------------------------
# explicit version dispatch (I12) -- never an ad-hoc boolean
# ---------------------------------------------------------------------------
def produce_recoverability_event_by_protocol(
    root: Path, task: OfficialDecisionEventTask, *, protocol_version: str,
    source_acquisition_protocol_sha256: Optional[str] = None,
    writer: Optional[Any] = None,
) -> Mapping[str, Any]:
    """Route one decision event to its protocol's producer.

    V1 keeps its historical behaviour verbatim, including the
    source-terminated-before-event accounting that V2 forbids, so historical
    replay stays exact.
    """
    if protocol_version not in RECOVERABILITY_PROTOCOLS:
        raise V2ProducerError(
            f"unknown recoverability protocol version {protocol_version!r}")
    if protocol_version == RECOVERABILITY_PROTOCOL_V1:
        return produce_recoverability_event(root, task, writer=writer)
    if not source_acquisition_protocol_sha256:
        raise V2ProducerError(
            "V2 production requires the source-acquisition protocol hash")
    return produce_recoverability_v2_event(
        root, task,
        source_acquisition_protocol_sha256=source_acquisition_protocol_sha256,
        writer=writer)
