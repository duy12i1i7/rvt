"""Deterministic compiler for authorized official Phase-9 scientific tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Tuple

from ..phase8.common import sha256_document
from ..topology_registry import COMPACT, LINE


JOB_MANIFEST_RELATIVE_PATH = Path("results/rvt_fd24/datasets/phase9_job_manifest.json")
JOB_MANIFEST_SHA256 = "801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3"
AUTHORIZED_DATASETS = frozenset({
    "study_a_train",
    "study_a_validation",
    "study_b_train",
    "study_b_validation",
})
SEALED_DATASETS = frozenset({"study_a_n24_evaluation"})
AUTHORIZED_STUDY_SPLITS = frozenset({
    ("study_a_zero_shot", "train"),
    ("study_a_zero_shot", "validation"),
    ("study_b_with_n24", "train"),
    ("study_b_with_n24", "validation"),
})
AUTHORIZED_FAMILIES = frozenset(f"F{index}" for index in range(1, 11))


class OfficialTaskCompilerError(ValueError):
    """A task selection is unknown, sealed, or not canonically bound."""


@dataclass(frozen=True)
class OfficialSourceTask:
    job_id: str
    dataset_id: str
    study: str
    split: str
    layout_source_split: str
    family: str
    layout_id: str
    layout_sha256: str
    team_size: int
    source_class: str
    episode_index: int
    horizon_seconds: float
    seeds: Mapping[str, int]


@dataclass(frozen=True)
class OfficialDecisionEventTask:
    event_id: str
    source: OfficialSourceTask
    event_slot_index: int
    resolved_control_step: int
    resolved_timestamp_seconds: float
    replicas_per_candidate: int
    candidate_replica_jobs: Tuple[Mapping[str, Any], ...]

    @property
    def scientific_task_id(self) -> str:
        return self.event_id

    def replica_jobs(self, candidate_topology_id: int) -> Tuple[Mapping[str, Any], ...]:
        if candidate_topology_id not in (COMPACT, LINE):
            raise OfficialTaskCompilerError("candidate must be COMPACT or LINE")
        result = tuple(
            item for item in self.candidate_replica_jobs
            if int(item["candidate_topology"]) == int(candidate_topology_id)
        )
        if len(result) != self.replicas_per_candidate:
            raise OfficialTaskCompilerError("candidate replica set is incomplete")
        return tuple(sorted(result, key=lambda item: int(item["replica_index"])))


@dataclass(frozen=True)
class OfficialResidualEpisodeTask:
    source: OfficialSourceTask

    @property
    def scientific_task_id(self) -> str:
        return f"{self.source.job_id}/residual-dense-universe"


def load_authoritative_job_manifest(root: Path) -> Mapping[str, Any]:
    path = root.resolve() / JOB_MANIFEST_RELATIVE_PATH
    document = json.loads(path.read_text(encoding="ascii"))
    expected = str(document.get("job_manifest_sha256", ""))
    body = dict(document)
    body.pop("job_manifest_sha256", None)
    if expected != JOB_MANIFEST_SHA256 or sha256_document(body) != expected:
        raise OfficialTaskCompilerError("authoritative job manifest hash mismatch")
    if document.get("final_test_jobs_present") is not False:
        raise OfficialTaskCompilerError("job manifest exposes final-test tasks")
    return document


def _authorize(study: str, split: str) -> None:
    if split == "final_test" or "final_test" in split:
        raise PermissionError("final-test task compilation is sealed")
    if split == "n24_evaluation" and study == "study_a_zero_shot":
        raise PermissionError("Study A N24 task compilation is sealed")
    if (study, split) not in AUTHORIZED_STUDY_SPLITS:
        raise OfficialTaskCompilerError(
            f"unsupported official study/split namespace: {study}/{split}"
        )


def _source_task(job: Mapping[str, Any]) -> OfficialSourceTask:
    if bool(job.get("sealed")) or str(job["dataset_id"]) in SEALED_DATASETS:
        raise PermissionError("sealed source job cannot become an executable task")
    if str(job["dataset_id"]) not in AUTHORIZED_DATASETS:
        raise OfficialTaskCompilerError("source job dataset is not authorized")
    if str(job["family_id"]) not in AUTHORIZED_FAMILIES:
        raise OfficialTaskCompilerError("unsupported official scenario family")
    return OfficialSourceTask(
        job_id=str(job["job_id"]),
        dataset_id=str(job["dataset_id"]),
        study=str(job["study"]),
        split=str(job["split"]),
        layout_source_split=str(job["layout_source_split"]),
        family=str(job["family_id"]),
        layout_id=str(job["layout_id"]),
        layout_sha256=str(job["layout_sha256"]),
        team_size=int(job["team_size"]),
        source_class=str(job["source_class"]),
        episode_index=int(job["episode_index"]),
        horizon_seconds=float(job["episode_horizon_seconds"]),
        seeds={str(name): int(value) for name, value in dict(job["seeds"]).items()},
    )


def compile_source_tasks(
    root: Path, *, study: str, split: str,
) -> Tuple[OfficialSourceTask, ...]:
    _authorize(study, split)
    manifest = load_authoritative_job_manifest(root)
    result = tuple(
        _source_task(job)
        for job in manifest["source_episode_jobs"]
        if str(job["study"]) == study
        and str(job["split"]) == split
        and not bool(job.get("sealed"))
    )
    if not result:
        raise OfficialTaskCompilerError("authorized source task selection is empty")
    if len({task.job_id for task in result}) != len(result):
        raise OfficialTaskCompilerError("duplicate source scientific task identity")
    return result


def compile_recoverability_tasks(
    root: Path, *, study: str, split: str,
) -> Tuple[OfficialDecisionEventTask, ...]:
    _authorize(study, split)
    manifest = load_authoritative_job_manifest(root)
    sources = {
        task.job_id: task
        for task in compile_source_tasks(root, study=study, split=split)
    }
    replica_by_event: dict[str, list[Mapping[str, Any]]] = {}
    for job in manifest["candidate_replica_jobs"]:
        if bool(job.get("sealed")):
            continue
        event_id = str(job["decision_event_job_id"])
        replica_by_event.setdefault(event_id, []).append(job)
    tasks = []
    for event in manifest["decision_event_jobs"]:
        source_id = str(event["source_episode_job_id"])
        if source_id not in sources:
            continue
        if bool(event.get("sealed")):
            raise PermissionError("sealed event entered authorized task compilation")
        replicas = int(event["replicas_per_candidate"])
        jobs = tuple(replica_by_event.get(str(event["job_id"]), ()))
        if len(jobs) != 2 * replicas:
            raise OfficialTaskCompilerError("event candidate-replica universe is incomplete")
        tasks.append(OfficialDecisionEventTask(
            event_id=str(event["job_id"]),
            source=sources[source_id],
            event_slot_index=int(event["event_slot_index"]),
            resolved_control_step=int(event["resolved_control_step"]),
            resolved_timestamp_seconds=float(event["resolved_timestamp_seconds"]),
            replicas_per_candidate=replicas,
            candidate_replica_jobs=tuple(sorted(
                jobs,
                key=lambda item: (
                    0 if int(item["candidate_topology"]) == COMPACT else 1,
                    int(item["replica_index"]),
                ),
            )),
        ))
    result = tuple(tasks)
    if len({task.event_id for task in result}) != len(result):
        raise OfficialTaskCompilerError("duplicate decision-event scientific task")
    return result


def compile_residual_tasks(
    root: Path, *, study: str, split: str,
) -> Tuple[OfficialResidualEpisodeTask, ...]:
    return tuple(
        OfficialResidualEpisodeTask(source)
        for source in compile_source_tasks(root, study=study, split=split)
    )


def compile_task_summary(root: Path) -> Mapping[str, Any]:
    manifest = load_authoritative_job_manifest(root)
    source_jobs = [
        job for job in manifest["source_episode_jobs"]
        if not bool(job.get("sealed"))
    ]
    events = [
        job for job in manifest["decision_event_jobs"]
        if not bool(job.get("sealed"))
    ]
    replicas = [
        job for job in manifest["candidate_replica_jobs"]
        if not bool(job.get("sealed"))
    ]
    return {
        "source_episodes": len(source_jobs),
        "decision_events": len(events),
        "candidate_aggregates": 2 * len(events),
        "candidate_replica_executions": len(replicas),
        "recoverability_robot_local_row_capacity": sum(
            2 * int(job["team_size"]) for job in events
        ),
        "residual_robot_episodes": sum(int(job["team_size"]) for job in source_jobs),
        "residual_retained_attempted_state_strict_upper_bound": (
            16 * sum(int(job["team_size"]) for job in source_jobs)
        ),
        "residual_candidate_evaluation_strict_upper_bound": (
            16 * 9 * sum(int(job["team_size"]) for job in source_jobs)
        ),
        "study_a_n24_tasks": 0,
        "final_test_tasks": 0,
    }
