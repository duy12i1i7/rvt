"""Official recoverability and Residual V2 producer entry points."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Optional, Sequence, Tuple

from ..decentralized.ego_graph_runtime_adapter import RobotLocalEgoGraphRuntimeAdapter
from ..decentralized.ego_graph_v2 import (
    EGO_GRAPH_SCHEMA_VERSION,
    dump_robot_local_ego_graph,
)
from ..fd24.configuration import FD24ModelConfig
from ..fd24.model import FD24_MODEL_INPUT_SCHEMA_VERSION, FD24_MODEL_SCHEMA_VERSION
from ..phase8.common import sha256_document
from ..phase8.targets import DENSE_ACTION_SAMPLE_SCHEMA_VERSION, DenseActionSample
from ..phase9c_rb import policies as source_policies
from ..phase9c_rb.binding import build_binding, load_execution_specification
from ..phase9c_rb.counterfactual import execute_candidate, snapshot
from ..phase9c_rb.generation_contract import (
    LABELED,
    NO_ELIGIBLE_ACTION,
    RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION,
    ResidualSupervisionRowV2,
    candidate_evaluation_id,
    residual_scientific_row_id,
)
from ..phase9c_rb.residual_expert_v2 import (
    canonical_result_digest,
    evaluate_residual_expert_v2,
)
from ..phase9c_rb.session import SimulatorEpisodeSession, build_event_plan
from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from ..topology_registry import COMPACT, LINE
from .compiler import OfficialDecisionEventTask, OfficialSourceTask
from .contracts import (
    GENERATION_INVALID,
    INFRASTRUCTURE_FAILURE,
    CandidateAggregateDisposition,
    Phase9G0RContractError,
    communication_configuration_sha256,
    lifecycle_configuration_sha256,
    official_rollout_configuration_payload,
    reconcile_candidate_pair,
    recoverability_ego_payload,
    recoverability_graph_fingerprint,
    recoverability_scientific_row_id,
    retained_dense_state_indices,
    validate_official_rollout_configuration_payload,
    validate_recoverability_ego_payload,
)
from .writer import CanonicalGenerationWriter


TARGET_V4_SHA256 = "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee"
EXECUTABLE_PROTOCOL_SHA256 = "8da0b94e5ae83cf35ea38c38504d11d6e6fdce6da09766bf8cb14c4cc252158a"
SOURCE_POLICY_SHA256 = "aaf4e35a539d1ae864805ee52cfbd8be7579e7a61103e3807fbbc6d1706168df"
TOPOLOGY_REGISTRY_SHA256 = "f8528d24561abea52e2cd50b236dc69cc6c25b402498fe13d0ace05e1317bfe5"
BASE_CONTROLLER_SHA256 = "1cfe364d706f06fe4602c5a3033e89051b3ca808443d4afd906c7e1319564a9f"
SAFETY_PROJECTION_SHA256 = "16e06727f9052198070c74814fd1822d0450c25a4d5d456f48fc33362e46c26e"
TRANSITION_PROTOCOL_SHA256 = "54f015e2c9a4da68d93c3e8e998f847b662fcfc8d7db4e75900b1e17ba6b1e01"
RESIDUAL_EXPERT_SPEC_SHA256 = "e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf"
RESIDUAL_SELECTOR_SHA256 = "535c4e639d598bb75bc4822cdbbc320c48c69a7f86f8d5b96dec2dd5ace9a123"


class OfficialProducerError(RuntimeError):
    """The qualified runtime cannot produce the requested scientific unit."""


def _load_contracts(root: Path) -> Tuple[Mapping[str, Any], ...]:
    result_root = root / "results/rvt_fd24"
    return tuple(
        json.loads((result_root / name).read_text(encoding="ascii"))
        for name in (
            "executable_scientific_protocol_v1.json",
            "target_v4_execution_contract_v1.json",
            "source_policy_contracts_v1.json",
        )
    )


def build_source_session(root: Path, task: OfficialSourceTask) -> SimulatorEpisodeSession:
    protocol, target, contracts = _load_contracts(root)
    runtime = RuntimeConfig.for_team_size(task.team_size)
    specification = load_execution_specification(
        root / "results/rvt_fd24", task.layout_source_split, task.layout_id
    )
    binding = build_binding(
        specification,
        team_size=task.team_size,
        source_policy=task.source_class,
        protocol=protocol,
        target_contract=target,
        source_policy_contracts=contracts,
        runtime_config=runtime,
    )
    if binding.layout_hash != task.layout_sha256 or binding.family != task.family:
        raise OfficialProducerError("source task differs from compiled runtime binding")
    event_plan = (
        build_event_plan(binding, contracts, runtime)
        if task.source_class == source_policies.S0
        else ()
    )
    policy = source_policies.build_source_policy(
        task.source_class,
        contracts=contracts,
        seed=int(task.seeds["data_sampling"]),
        horizon_seconds=binding.horizon_seconds,
        team_size=task.team_size,
        family_id=task.family,
        runtime_config=runtime,
        event_plan=event_plan,
    )
    return SimulatorEpisodeSession(
        binding,
        protocol=protocol,
        target_contract=target,
        seeds={
            "initial_condition": int(task.seeds["initial_condition"]),
            "communication": int(task.seeds["communication"]),
            "dynamic_obstacle": int(task.seeds["dynamic_obstacle"]),
        },
        source_policy=policy,
        runtime_config=runtime,
        episode_id=task.job_id,
    )


def _run_source_to_step(
    root: Path, task: OfficialSourceTask, control_step: int,
) -> SimulatorEpisodeSession:
    session = build_source_session(root, task)
    while session.termination is None and session.control_step < int(control_step):
        session.step()
    return session


def _rollout_kwargs(
    task: OfficialDecisionEventTask,
    session: SimulatorEpisodeSession,
    candidate: int,
    replica_job: Mapping[str, Any],
) -> Mapping[str, Any]:
    matched_seed = int(dict(replica_job["seeds"])["matched_disturbance_seed"])
    communication_hash = communication_configuration_sha256(
        session.runtime_config,
        session.binding.communication_contract,
        int(task.source.seeds["communication"]),
    )
    return {
        "study": task.source.study,
        "split": task.source.split,
        "family": task.source.family,
        "layout_sha256": task.source.layout_sha256,
        "team_size": task.source.team_size,
        "episode_id": task.source.job_id,
        "decision_event_id": task.event_id,
        "decision_timestep": task.resolved_control_step,
        "candidate_topology_id": candidate,
        "replica_index": int(replica_job["replica_index"]),
        "matched_disturbance_seed": matched_seed,
        "source_policy_contract_sha256": SOURCE_POLICY_SHA256,
        "topology_registry_contract_sha256": TOPOLOGY_REGISTRY_SHA256,
        "base_controller_contract_sha256": BASE_CONTROLLER_SHA256,
        "transition_execution_protocol_sha256": TRANSITION_PROTOCOL_SHA256,
        "safety_contract_sha256": SAFETY_PROJECTION_SHA256,
        "simulator_protocol_sha256": EXECUTABLE_PROTOCOL_SHA256,
        "target_v4_contract_sha256": TARGET_V4_SHA256,
        "runtime_configuration_sha256": canonical_runtime_hash(session.runtime_config),
        "control_period_seconds": session.runtime_config.physical.control_period_seconds,
        "lifecycle_config_sha256": lifecycle_configuration_sha256(session.runtime_config),
        "communication_config_sha256": communication_hash,
    }


def _candidate_disposition(
    event_id: str, candidate: int, replicas: Sequence[Mapping[str, Any]],
) -> CandidateAggregateDisposition:
    if any(item["disposition"] == GENERATION_INVALID for item in replicas):
        return CandidateAggregateDisposition(
            event_id, candidate, GENERATION_INVALID, None, len(replicas)
        )
    label = int(all(item["label"] == 1 for item in replicas))
    return CandidateAggregateDisposition(
        event_id,
        candidate,
        "RECOVERABLE_POSITIVE" if label else "VALID_TASK_NEGATIVE",
        label,
        len(replicas),
    )


def _execute_candidate_with_one_infrastructure_retry(
    source: Any,
    candidate: int,
    replica_job: Mapping[str, Any],
) -> tuple[Optional[Any], Tuple[Mapping[str, Any], ...]]:
    """Replay the byte-identical scientific call at most once after an exception."""
    audit = []
    for attempt_index in (0, 1):
        try:
            result = execute_candidate(
                source,
                candidate,
                replica_index=int(replica_job["replica_index"]),
                disturbance_seed=int(
                    dict(replica_job["seeds"])["matched_disturbance_seed"]
                ),
            )
        except Exception as exc:
            audit.append({
                "attempt_index": attempt_index,
                "status": "INFRASTRUCTURE_EXCEPTION",
                "exception_class": type(exc).__name__,
            })
            continue
        audit.append({"attempt_index": attempt_index, "status": "COMPLETED"})
        return result, tuple(audit)
    return None, tuple(audit)


def _joint_category(compact_label: int, line_label: int) -> str:
    return {
        (1, 0): "COMPACT_ONLY_SUCCESS",
        (0, 1): "LINE_ONLY_SUCCESS",
        (1, 1): "BOTH_SUCCESS",
        (0, 0): "BOTH_FAIL",
    }[(compact_label, line_label)]


def produce_recoverability_candidate(
    root: Path,
    task: OfficialDecisionEventTask,
    candidate: int,
) -> Mapping[str, Any]:
    """Execute one scheduler-atomic candidate aggregate with all replicas."""
    if candidate not in (COMPACT, LINE):
        raise OfficialProducerError("recoverability candidate must be COMPACT or LINE")
    started = perf_counter()
    session = _run_source_to_step(root, task.source, task.resolved_control_step)
    source_event_seconds = perf_counter() - started

    if session.termination is not None and session.control_step < task.resolved_control_step:
        disposition = CandidateAggregateDisposition(
            task.event_id, candidate, GENERATION_INVALID, None,
            task.replicas_per_candidate,
        )
        return {
            "schema_version": "rvt-official-recoverability-candidate-result/v1",
            "decision_event_id": task.event_id,
            "candidate_topology_id": candidate,
            "team_size": task.source.team_size,
            "source_terminated_before_event": True,
            "termination": asdict(session.termination),
            "source_snapshot_sha256": None,
            "graphs": [],
            "rollout_configuration_sha256_by_replica": [],
            "disposition": asdict(disposition),
            "candidate_audit": None,
            "operational_timing": {
                "source_event_seconds": source_event_seconds,
                "graph_serialization_seconds": 0.0,
                "replica_rollout_seconds": [],
                "candidate_total_seconds": perf_counter() - started,
            },
        }

    source = snapshot(session)
    graph_started = perf_counter()
    graphs = []
    for robot in session.robots:
        view = session._build_robot_view(robot)
        graph = RobotLocalEgoGraphRuntimeAdapter(
            session.runtime_config, robot.local_topology_metadata
        ).build(view, candidate, session.control_step)
        payload, separated_candidate = recoverability_ego_payload(graph)
        if separated_candidate != candidate:
            raise OfficialProducerError("ego graph candidate separation failed")
        validate_recoverability_ego_payload(payload)
        graphs.append({
            "robot_id": int(payload["metadata"]["observer_robot_id"]),
            "graph_payload": payload,
            "graph_fingerprint": recoverability_graph_fingerprint(payload),
        })
    graph_seconds = perf_counter() - graph_started

    replicas = []
    rollout_hashes = []
    replica_seconds = []
    candidate_audit: Mapping[str, Any]
    disposition: CandidateAggregateDisposition
    for replica_job in task.replica_jobs(candidate):
        kwargs = _rollout_kwargs(task, session, candidate, replica_job)
        rollout_payload = official_rollout_configuration_payload(**kwargs)
        validate_official_rollout_configuration_payload(
            rollout_payload,
            expected_lifecycle_config_sha256=kwargs["lifecycle_config_sha256"],
            expected_communication_config_sha256=kwargs[
                "communication_config_sha256"
            ],
        )
        rollout_hash = sha256_document(rollout_payload)
        rollout_hashes.append(rollout_hash)
        replica_started = perf_counter()
        result, attempt_audit = _execute_candidate_with_one_infrastructure_retry(
            source, candidate, replica_job
        )
        replica_seconds.append(perf_counter() - replica_started)
        if result is not None:
            replicas.append({
                **asdict(result),
                "rollout_configuration_sha256": rollout_hash,
                "matched_disturbance_seed": int(
                    dict(replica_job["seeds"])["matched_disturbance_seed"]
                ),
                "infrastructure_attempts": list(attempt_audit),
            })
        else:
            disposition = CandidateAggregateDisposition(
                task.event_id, candidate, INFRASTRUCTURE_FAILURE, None,
                task.replicas_per_candidate,
            )
            candidate_audit = {
                "candidate_topology_id": candidate,
                "infrastructure_failure": "RETRY_EXHAUSTED",
                "infrastructure_attempts": list(attempt_audit),
                "replicas": replicas,
            }
            break
    else:
        disposition = _candidate_disposition(task.event_id, candidate, replicas)
        candidate_audit = {
            "candidate_topology_id": candidate,
            "aggregate": asdict(disposition),
            "replicas": replicas,
        }

    return {
        "schema_version": "rvt-official-recoverability-candidate-result/v1",
        "decision_event_id": task.event_id,
        "candidate_topology_id": candidate,
        "team_size": task.source.team_size,
        "source_terminated_before_event": False,
        "termination": None,
        "source_snapshot_sha256": source.canonical_hash,
        "graphs": graphs,
        "rollout_configuration_sha256_by_replica": rollout_hashes,
        "disposition": asdict(disposition),
        "candidate_audit": candidate_audit,
        "operational_timing": {
            "source_event_seconds": source_event_seconds,
            "graph_serialization_seconds": graph_seconds,
            "replica_rollout_seconds": replica_seconds,
            "candidate_total_seconds": perf_counter() - started,
        },
    }


def reconcile_recoverability_candidate_results(
    root: Path,
    task: OfficialDecisionEventTask,
    compact_result: Mapping[str, Any],
    line_result: Mapping[str, Any],
    *,
    writer: Optional[CanonicalGenerationWriter] = None,
) -> Mapping[str, Any]:
    """Reconcile two scheduler units into the frozen event-level transaction."""
    reconcile_started = perf_counter()
    by_candidate = {
        int(compact_result["candidate_topology_id"]): compact_result,
        int(line_result["candidate_topology_id"]): line_result,
    }
    if set(by_candidate) != {COMPACT, LINE}:
        raise OfficialProducerError("candidate pair must contain COMPACT and LINE")
    for candidate, result in by_candidate.items():
        if result["decision_event_id"] != task.event_id:
            raise OfficialProducerError("candidate result crosses decision events")
        if int(result["team_size"]) != task.source.team_size:
            raise OfficialProducerError("candidate result team size changed")
        if int(result["candidate_topology_id"]) != candidate:
            raise OfficialProducerError("candidate result identity changed")
    terminated = {
        bool(result["source_terminated_before_event"])
        for result in by_candidate.values()
    }
    if len(terminated) != 1:
        raise OfficialProducerError("candidate source-event availability diverged")
    snapshots = {
        result["source_snapshot_sha256"] for result in by_candidate.values()
    }
    if len(snapshots) != 1:
        raise OfficialProducerError("candidate source snapshots diverged")
    for replica_index in range(task.replicas_per_candidate):
        compact_seed = int(
            dict(task.replica_jobs(COMPACT)[replica_index]["seeds"])[
                "matched_disturbance_seed"
            ]
        )
        line_seed = int(
            dict(task.replica_jobs(LINE)[replica_index]["seeds"])[
                "matched_disturbance_seed"
            ]
        )
        if compact_seed != line_seed:
            raise OfficialProducerError("matched candidate disturbance seeds diverge")

    row_binding = json.loads(
        (root / "results/rvt_fd24/phase9_recoverability_row_binding_v1.json")
        .read_text(encoding="ascii")
    )
    row_binding_sha = str(row_binding["phase9_recoverability_row_binding_sha256"])
    dispositions = {
        candidate: CandidateAggregateDisposition(**dict(result["disposition"]))
        for candidate, result in by_candidate.items()
    }
    row_started = perf_counter()
    rows: dict[int, list[Mapping[str, Any]]] = {COMPACT: [], LINE: []}
    if all(dispositions[c].disposition in {
        "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"
    } for c in (COMPACT, LINE)):
        joint = _joint_category(
            int(dispositions[COMPACT].aggregate_label),
            int(dispositions[LINE].aggregate_label),
        )
        for candidate in (COMPACT, LINE):
            result = by_candidate[candidate]
            for graph in result["graphs"]:
                robot_id = int(graph["robot_id"])
                graph_payload = graph["graph_payload"]
                graph_fingerprint = str(graph["graph_fingerprint"])
                key = {
                    "schema": "rvt-recoverability-row-identity/v1",
                    "study": task.source.study,
                    "split": task.source.split,
                    "family": task.source.family,
                    "layout_sha256": task.source.layout_sha256,
                    "team_size": task.source.team_size,
                    "episode_id": task.source.job_id,
                    "timestep": task.resolved_control_step,
                    "robot_id": robot_id,
                    "candidate_topology_id": candidate,
                    "graph_fingerprint": graph_fingerprint,
                    "target_v4_contract_sha256": TARGET_V4_SHA256,
                    "recoverability_row_binding_spec_sha256": row_binding_sha,
                }
                rows[candidate].append({
                    "schema_version": "rvt-recoverability-scientific-row/v1",
                    "scientific_row_id": recoverability_scientific_row_id(key),
                    "scientific_identity": key,
                    "graph_payload_schema_version": "rvt-recoverability-ego-payload-binding/v1",
                    "graph_payload": graph_payload,
                    "graph_fingerprint": graph_fingerprint,
                    "candidate_topology_id": candidate,
                    "target_v4_aggregate_label": dispositions[candidate].aggregate_label,
                    "target_v4_aggregate_disposition": dispositions[candidate].disposition,
                    "target_v4_contract_sha256": TARGET_V4_SHA256,
                    "replica_count": dispositions[candidate].replica_count,
                    "rollout_configuration_sha256_by_replica": result[
                        "rollout_configuration_sha256_by_replica"
                    ],
                    "joint_outcome_category": joint,
                })
    row_seconds = perf_counter() - row_started
    reconciliation = reconcile_candidate_pair(
        dispositions[COMPACT],
        dispositions[LINE],
        team_size=task.source.team_size,
        compact_rows=rows[COMPACT],
        line_rows=rows[LINE],
    )
    reconcile_seconds = perf_counter() - reconcile_started - row_seconds
    candidate_audits = [
        by_candidate[candidate]["candidate_audit"]
        for candidate in (COMPACT, LINE)
        if by_candidate[candidate]["candidate_audit"] is not None
    ]
    if next(iter(terminated)):
        audit = {
            "source_terminated_before_event": True,
            "termination": by_candidate[COMPACT]["termination"],
            "candidate_audits": candidate_audits,
        }
    else:
        audit = {
            "source_terminated_before_event": False,
            "source_snapshot_sha256": next(iter(snapshots)),
            "decision_event_id": task.event_id,
            "decision_timestep": task.resolved_control_step,
            "candidate_audits": candidate_audits,
            "row_binding_spec_sha256": row_binding_sha,
        }
    audit["operational_timing"] = {
        "candidate": {
            str(candidate): by_candidate[candidate]["operational_timing"]
            for candidate in (COMPACT, LINE)
        },
        "row_expansion_seconds": row_seconds,
        "candidate_pair_reconciliation_seconds": reconcile_seconds,
    }
    writer_started = perf_counter()
    write_result = None if writer is None else writer.write_recoverability_transaction(
        reconciliation, audit
    )
    audit["operational_timing"]["writer_seconds"] = perf_counter() - writer_started
    return {"reconciliation": asdict(reconciliation), "audit": audit, "write": write_result}


def produce_recoverability_event(
    root: Path,
    task: OfficialDecisionEventTask,
    *,
    writer: Optional[CanonicalGenerationWriter] = None,
) -> Mapping[str, Any]:
    """Execute both scheduler units and reconcile one frozen 2*N row set."""
    compact = produce_recoverability_candidate(root, task, COMPACT)
    line = produce_recoverability_candidate(root, task, LINE)
    return reconcile_recoverability_candidate_results(
        root, task, compact, line, writer=writer
    )


def residual_decision_eligible(
    session: SimulatorEpisodeSession, robot_id: int,
) -> tuple[bool, str]:
    """The existing active local-action pipeline is the only enable predicate."""
    if not session.initialization_valid:
        return False, "INITIALIZATION_INVALID"
    if session.termination is not None:
        return False, "TERMINAL"
    if not session.numerically_valid:
        return False, "RUNTIME_INVALID"
    try:
        robot = next(item for item in session.robots if item.robot_id == int(robot_id))
        _, controller_input, controller = session.local_decision_inputs(robot)
        output = controller.evaluate(controller_input)
        snapshot(session)
    except (StopIteration, TypeError, ValueError, RuntimeError, FloatingPointError):
        return False, "LOCAL_PIPELINE_UNAVAILABLE"
    if not bool(output.validity):
        return False, "BASE_ACTION_INVALID"
    if controller.safety_projection is None:
        return False, "SAFETY_CONTEXT_UNAVAILABLE"
    values = tuple(float(value) for value in output.base_action)
    if len(values) != 2 or not all(math.isfinite(value) for value in values):
        return False, "BASE_ACTION_INVALID"
    return True, "ELIGIBLE"


def plan_residual_retained_states(
    root: Path, task: OfficialSourceTask,
) -> Mapping[int, Tuple[int, ...]]:
    """Enumerate the source trajectory, then apply K=16 within each robot."""
    session = build_source_session(root, task)
    eligible: dict[int, list[int]] = {robot.robot_id: [] for robot in session.robots}
    while session.termination is None:
        for robot in session.robots:
            admitted, _ = residual_decision_eligible(session, robot.robot_id)
            if admitted:
                eligible[robot.robot_id].append(int(session.control_step))
        session.step()
    retained = {}
    for robot_id, timesteps in eligible.items():
        positions = retained_dense_state_indices(len(timesteps))
        retained[robot_id] = tuple(timesteps[index] for index in positions)
    return retained


def produce_residual_state(
    root: Path,
    task: OfficialSourceTask,
    *,
    robot_id: int,
    timestep: int,
    source_commit: str,
    scientific_addendum_sha256: str,
    writer: Optional[CanonicalGenerationWriter] = None,
) -> Mapping[str, Any]:
    started = perf_counter()
    session = _run_source_to_step(root, task, timestep)
    source_event_seconds = perf_counter() - started
    local_started = perf_counter()
    eligible, reason = residual_decision_eligible(session, robot_id)
    if not eligible or session.control_step != int(timestep):
        raise OfficialProducerError(f"retained residual state is unavailable: {reason}")
    robot = next(item for item in session.robots if item.robot_id == int(robot_id))
    view, controller_input, controller = session.local_decision_inputs(robot)
    output = controller.evaluate(controller_input)
    graph = RobotLocalEgoGraphRuntimeAdapter(
        session.runtime_config, robot.local_topology_metadata
    ).build(view, robot.committed_topology, session.control_step)
    graph_fingerprint = graph.fingerprint()
    local_input_graph_seconds = perf_counter() - local_started
    row_key = {
        "study": task.study,
        "split": task.split,
        "family": task.family,
        "layout_sha256": task.layout_sha256,
        "team_size": task.team_size,
        "episode_id": task.job_id,
        "timestep": int(timestep),
        "robot_id": int(robot_id),
        "topology_id": int(robot.committed_topology),
        "graph_fingerprint": graph_fingerprint,
        "residual_expert_spec_sha256": RESIDUAL_EXPERT_SPEC_SHA256,
    }
    row_id = residual_scientific_row_id(row_key)
    expert_started = perf_counter()
    result = evaluate_residual_expert_v2(session, robot_id)
    residual_expert_seconds = perf_counter() - expert_started
    sidecar_started = perf_counter()
    candidate_sidecars = []
    candidate_ids = []
    stream_hashes = []
    for candidate in result.candidates:
        stream_hash = sha256_document([
            list(value) for value in candidate.trace.matched_stream_identity
        ])
        evaluation_id = candidate_evaluation_id({
            "residual_scientific_row_id": row_id,
            "candidate_index": candidate.candidate_index,
            "replica_index": 0,
            "matched_stream_identity_sha256": stream_hash,
        })
        stream_hashes.append(stream_hash)
        candidate_ids.append(evaluation_id)
        candidate_sidecars.append({
            "candidate_evaluation_id": evaluation_id,
            "candidate_index": candidate.candidate_index,
            "candidate_sha256": candidate.canonical_hash,
            "delta_u_world": list(candidate.delta_u_world),
            "utilities": dict(candidate.utilities),
            "termination": candidate.trace.termination_cause,
            "control_intervals": candidate.trace.control_intervals,
            "matched_stream_identity_sha256": stream_hash,
        })
    sidecar_serialization_seconds = perf_counter() - sidecar_started

    row_payload: Optional[Mapping[str, Any]] = None
    disposition = LABELED if result.target is not None else NO_ELIGIBLE_ACTION
    if result.target is not None and result.selected_index is not None:
        projected = tuple(float(value) for value in output.projected_action)
        dense = DenseActionSample(
            schema_version=DENSE_ACTION_SAMPLE_SCHEMA_VERSION,
            ego_graph_schema_version=EGO_GRAPH_SCHEMA_VERSION,
            feature_sha256=graph_fingerprint,
            candidate_or_committed_topology=int(robot.committed_topology),
            base_action_world_acceleration=result.base_action_pre_safety,
            expert_action_world_acceleration=result.target.expert_action_world_acceleration,
            residual_target_world_acceleration=result.target.residual_target_world_acceleration,
            projected_base_action_world_acceleration=projected,
            safety_projection_metadata=(
                ("intervened", str(bool(output.projection_intervened))),
                ("infeasible", str(bool(output.projection_infeasible))),
                ("solver_failed", str(bool(output.projection_solver_failed))),
            ),
            robot_role_id=robot.role_id,
            team_size=task.team_size,
            scenario_family=task.family,
            layout_sha256=task.layout_sha256,
            split=task.split,
            episode_id=task.job_id,
            timestep=int(timestep),
            source_commit=source_commit,
            configuration_sha256=(
                ("runtime", canonical_runtime_hash(session.runtime_config)),
                ("scientific_addendum", scientific_addendum_sha256),
                ("residual_expert_v2", RESIDUAL_EXPERT_SPEC_SHA256),
            ),
        )
        selected = int(result.selected_index)
        row = ResidualSupervisionRowV2(
            schema_version=RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION,
            residual_scientific_row_id=row_id,
            dense_row=asdict(dense),
            mission_orientation_cos_sin=graph.mission_orientation_cos_sin,
            ego_graph_record_sha256=graph_fingerprint,
            ego_graph_schema_version=EGO_GRAPH_SCHEMA_VERSION,
            model_input_schema_version=FD24_MODEL_INPUT_SCHEMA_VERSION,
            model_schema_version=FD24_MODEL_SCHEMA_VERSION,
            residual_expert_spec_sha256=RESIDUAL_EXPERT_SPEC_SHA256,
            selector_sha256=RESIDUAL_SELECTOR_SHA256,
            decision_snapshot_sha256=result.snapshot_hash,
            matched_stream_identity_sha256=stream_hashes[selected],
            selected_candidate_index=selected,
            selected_candidate_evaluation_id=candidate_ids[selected],
            disposition=LABELED,
        )
        row_payload = {
            **dict(row.canonical_payload()),
            "canonical_supervision_row_sha256": row.canonical_sha256(),
            "ego_graph_payload": json.loads(dump_robot_local_ego_graph(graph)),
        }

    audit = {
        "scientific_row_id": row_id,
        "disposition": disposition,
        "eligible_reason": reason,
        "candidate_evaluations": len(result.candidates),
        "candidate_sidecars": candidate_sidecars,
        "result_digest": canonical_result_digest(result),
        "selector_error": result.selector_error,
        "selected_candidate_index": result.selected_index,
        "operational_timing": {
            "source_event_seconds": source_event_seconds,
            "local_input_graph_seconds": local_input_graph_seconds,
            "residual_expert_total_seconds": residual_expert_seconds,
            "candidate_continuation_seconds": [
                float(candidate.seconds) for candidate in result.candidates
            ],
            "utility_selector_target_seconds": max(
                0.0,
                float(result.seconds)
                - sum(float(candidate.seconds) for candidate in result.candidates),
            ),
            "sidecar_serialization_seconds": sidecar_serialization_seconds,
        },
    }
    writer_started = perf_counter()
    write_result = None if writer is None else writer.write_residual_attempt(
        scientific_row_id=row_id,
        disposition=disposition,
        row=row_payload,
        audit=audit,
    )
    audit["operational_timing"]["writer_seconds"] = perf_counter() - writer_started
    audit["operational_timing"]["unit_total_seconds"] = perf_counter() - started
    return {"row": row_payload, "audit": audit, "write": write_result}
