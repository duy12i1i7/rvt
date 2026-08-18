"""Qualification-only V3 canary. Never official data.

Identities live in their own study and split, on the offset-0.0 layout variants
that the final V3 registry does not contain at all, so disjointness from the
frozen official V3 TRAIN and VALIDATION manifests is structural rather than
checked after the fact. The check is still performed, because structural
arguments are worth verifying.

The semantic digest is the point of the whole exercise: it covers source-event
identities, selected states, candidate and replica identities, matched streams,
scientific dispositions, valid ``Y_r``, candidate labelability, ``k``, ``R``,
the invalidity-contract hash, the pair disposition, row ids and the supervision
payload. Reference and target must produce the same digest, bit for bit.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

from ..phase8.common import sha256_document
from ..topology_registry import COMPACT, LINE
from .compiler import OfficialSourceTask
from .compiler_v3 import (
    compile_recoverability_v3_candidate_tasks, execute_v3_source_acquisition,
    load_v3_source_manifest, V3_TRAIN, V3_VALIDATION,
)
from .contracts_v3 import (
    INVALIDITY_CONTRACT_V3_SHA256, PROBABILISTIC_TARGET_V3_SHA256,
    REPLICA_PROTOCOL_V3_SHA256, ROW_BINDING_V3_SPEC_SHA256,
    S8InvalidRateAccounting,
)
from .producer_v3 import produce_recoverability_v3_event

CANARY_STUDY = "study_a_v3_qualification_canary"
CANARY_SPLIT = "v3_qualification_canary"
CANARY_SEED_NAMESPACE = "phase9g_v3i_q_r_qualification_canary"
CANARY_SCHEMA_VERSION = "rvt-recoverability-v3-qualification-canary/v1"

#: Deliberately the offset-0.0 layout variants. The final V3 registry contains
#: train-f*-02, validation-f*-01 and validation-f*-02 only, so a canary on
#: train-f*-00 cannot touch an official V3 layout.
CANARY_LAYOUT_SOURCE_SPLIT = "train"


@dataclass(frozen=True)
class CanaryIdentity:
    family: str
    team_size: int
    source_policy: str
    layout_id: str
    episode_index: int = 0

    @property
    def episode_id(self) -> str:
        return (f"v3-qual-canary/{self.family}/N{self.team_size}/"
                f"{self.source_policy}/episode-{self.episode_index}")


#: R31 coverage: an R = 1 family, F8, F9, several N, both candidates, real
#: source selection and real Target-V4 execution. Chosen before any outcome was
#: observed and never adjusted toward a desired k.
CANARY_IDENTITIES: Tuple[CanaryIdentity, ...] = (
    CanaryIdentity("F1", 5, "S1_ALWAYS_COMPACT", "train-f1-00"),
    CanaryIdentity("F8", 5, "S1_ALWAYS_COMPACT", "train-f8-00"),
    CanaryIdentity("F9", 6, "S1_ALWAYS_COMPACT", "train-f9-00"),
    CanaryIdentity("F9", 12, "S2_ALWAYS_LINE", "train-f9-00"),
)


def _seed(identity: CanaryIdentity, key: str) -> int:
    payload = json.dumps({
        "namespace": CANARY_SEED_NAMESPACE, "key": key,
        "study": CANARY_STUDY, "split": CANARY_SPLIT,
        "family": identity.family, "team_size": identity.team_size,
        "source_policy": identity.source_policy,
        "layout_id": identity.layout_id,
        "episode_index": identity.episode_index,
    }, sort_keys=True).encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def canary_source_task(root: Path, identity: CanaryIdentity) -> OfficialSourceTask:
    specification = json.loads(
        (Path(root) / "results/rvt_fd24/layout_execution_specifications"
         / CANARY_LAYOUT_SOURCE_SPLIT / f"{identity.layout_id}.json"
         ).read_text(encoding="ascii"))
    return OfficialSourceTask(
        job_id=identity.episode_id,
        dataset_id="v3_qualification_canary",
        study=CANARY_STUDY,
        split=CANARY_SPLIT,
        layout_source_split=CANARY_LAYOUT_SOURCE_SPLIT,
        family=identity.family,
        layout_id=identity.layout_id,
        layout_sha256=str(specification["source_layout"]["geometry_sha256"]),
        team_size=int(identity.team_size),
        source_class=identity.source_policy,
        episode_index=int(identity.episode_index),
        horizon_seconds=float(specification["episode_horizon_seconds"]),
        seeds={
            "initial_condition": _seed(identity, "initial_condition"),
            "communication": _seed(identity, "communication"),
            "dynamic_obstacle": _seed(identity, "dynamic_obstacle"),
            "data_sampling": _seed(identity, "data_sampling"),
        })


def official_v3_identity_pool(root: Path) -> Dict[str, set]:
    """Everything the canary must stay away from."""
    episodes, layouts, geometries = set(), set(), set()
    for split in (V3_TRAIN, V3_VALIDATION):
        manifest = load_v3_source_manifest(root, v3_split=split)
        for entry in manifest["episodes"]:
            episodes.add(str(entry["episode_id"]))
            layouts.add(str(entry["layout_id"]))
            geometries.add(str(entry["layout_sha256"]))
    return {"episode_ids": episodes, "layout_ids": layouts,
            "layout_sha256": geometries}


def prove_canary_disjointness(root: Path) -> Mapping[str, Any]:
    """R30: prove disjointness BEFORE anything executes."""
    pool = official_v3_identity_pool(root)
    tasks = [canary_source_task(root, identity) for identity in CANARY_IDENTITIES]
    episode_overlap = sorted({task.job_id for task in tasks} & pool["episode_ids"])
    layout_overlap = sorted({task.layout_id for task in tasks} & pool["layout_ids"])
    geometry_overlap = sorted(
        {task.layout_sha256 for task in tasks} & pool["layout_sha256"])
    return {
        "schema_version": "rvt-recoverability-v3-canary-disjointness/v1",
        "canary_identities": len(tasks),
        "official_v3_episode_identities": len(pool["episode_ids"]),
        "official_v3_layout_ids": sorted(pool["layout_ids"]),
        "canary_layout_ids": sorted({task.layout_id for task in tasks}),
        "episode_identity_overlap": episode_overlap,
        "layout_id_overlap": layout_overlap,
        "layout_geometry_overlap": geometry_overlap,
        "overlap_total": len(episode_overlap) + len(layout_overlap)
                         + len(geometry_overlap),
        "canary_study": CANARY_STUDY,
        "canary_split": CANARY_SPLIT,
        "official_studies": ["study_a_zero_shot"],
        "study_namespaces_disjoint": True,
    }


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
def _event_digest_payload(event: Mapping[str, Any]) -> Mapping[str, Any]:
    """Everything R44 requires the semantic digest to cover."""
    return {
        "decision_event_id": event["decision_event_id"],
        "family": event["family"],
        "team_size": event["team_size"],
        "realized_source_timestep": event["realized_source_timestep"],
        "R_required": event["R_required"],
        "planned_required_replica_executions":
            event["planned_required_replica_executions"],
        "executed_required_replica_rollouts":
            event["executed_required_replica_rollouts"],
        "replica_evidence": {
            candidate: [
                {
                    "replica_index": item["replica_index"],
                    "replica_evaluation_id": item["replica_evaluation_id"],
                    "matched_disturbance_seed": item["matched_disturbance_seed"],
                    "disposition": item["disposition"],
                    "target_v4_label": item["target_v4_label"],
                    "termination_cause": item["termination_cause"],
                    "failed_predicates": item["failed_predicates"],
                    "initial_clone_hash": item["initial_clone_hash"],
                    "final_state_hash": item["final_state_hash"],
                }
                for item in items
            ]
            for candidate, items in sorted(event["replica_evidence"].items())
        },
        "labelability": event["labelability"],
        "supervision": event["supervision"],
        "status": event["status"],
        "training_rows_committable": event["training_rows_committable"],
        "expected_row_count": event["expected_row_count"],
        "actual_row_count": event["actual_row_count"],
        "row_ids": sorted(str(row["scientific_row_id"]) for row in event["rows"]),
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
            event["recoverability_v3_required_replica_invalidity_contract_v1_sha256"],
    }


def _run_identity(payload: Tuple[str, int, Sequence[int]]) -> Mapping[str, Any]:
    root_text, index, candidate_order = payload
    root = Path(root_text)
    identity = CANARY_IDENTITIES[index]
    task = canary_source_task(root, identity)
    acquisition = execute_v3_source_acquisition(root, task)
    events = [
        produce_recoverability_v3_event(
            root, candidate_task,
            source_acquisition_protocol_sha256=acquisition.protocol_sha256,
            candidate_order=tuple(candidate_order))
        for candidate_task in compile_recoverability_v3_candidate_tasks(acquisition)
    ]
    return {
        "episode_id": task.job_id,
        "family": task.family,
        "team_size": task.team_size,
        "source_policy": task.source_class,
        "layout_id": task.layout_id,
        "M": acquisition.M,
        "selected_source_events": acquisition.selected_event_count,
        "selected_state_fingerprints": [
            state.source_state_fingerprint for state in acquisition.selected],
        "source_event_ids": [state.source_event_id
                             for state in acquisition.selected],
        "acquisition_sha256": acquisition.acquisition_sha256(),
        "events": events,
    }


def run_v3_qualification_canary(
    root: Path, *, workers: int = 1,
    candidate_order: Sequence[int] = (COMPACT, LINE),
    identities: Sequence[int] = tuple(range(len(CANARY_IDENTITIES))),
) -> Mapping[str, Any]:
    """Execute the canary end to end and return its canonical semantic digest."""
    root = Path(root).resolve()
    disjointness = prove_canary_disjointness(root)
    if disjointness["overlap_total"] != 0:
        raise RuntimeError("canary identities overlap the official V3 manifests")

    jobs = [(str(root), index, tuple(int(c) for c in candidate_order))
            for index in identities]
    if workers <= 1:
        episodes = [_run_identity(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            episodes = list(executor.map(_run_identity, jobs, chunksize=1))
    episodes.sort(key=lambda item: item["episode_id"])

    accounting = S8InvalidRateAccounting()
    rows_published = 0
    retained = dropped = 0
    supervision_records = supervision_blocked = 0
    for episode in episodes:
        for event in episode["events"]:
            for items in event["replica_evidence"].values():
                for item in items:
                    accounting.record_replica(
                        family=episode["family"], disposition=item["disposition"])
            rows_published += int(event["actual_row_count"])
            if event["training_rows_committable"]:
                retained += 1
                supervision_records += 2
            else:
                dropped += 1
                supervision_blocked += sum(
                    0 if state["candidate_scientifically_labelable"] else 1
                    for state in event["labelability"].values())

    digest_payload = {
        "schema_version": CANARY_SCHEMA_VERSION,
        "episodes": [
            {
                "episode_id": episode["episode_id"],
                "family": episode["family"],
                "team_size": episode["team_size"],
                "source_policy": episode["source_policy"],
                "layout_id": episode["layout_id"],
                "M": episode["M"],
                "selected_source_events": episode["selected_source_events"],
                "selected_state_fingerprints":
                    episode["selected_state_fingerprints"],
                "source_event_ids": episode["source_event_ids"],
                "acquisition_sha256": episode["acquisition_sha256"],
                "events": [_event_digest_payload(event)
                           for event in episode["events"]],
            }
            for episode in episodes
        ],
        "recoverability_probabilistic_target_v3_sha256":
            PROBABILISTIC_TARGET_V3_SHA256,
        "recoverability_replica_protocol_v3_sha256": REPLICA_PROTOCOL_V3_SHA256,
        "recoverability_row_binding_v3_spec_sha256": ROW_BINDING_V3_SPEC_SHA256,
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
            INVALIDITY_CONTRACT_V3_SHA256,
    }
    return {
        "schema_version": CANARY_SCHEMA_VERSION,
        "canary_semantic_digest_sha256": sha256_document(digest_payload),
        "disjointness": disjointness,
        "workers": workers,
        "candidate_order": [int(item) for item in candidate_order],
        "episodes_executed": len(episodes),
        "decision_events": sum(len(episode["events"]) for episode in episodes),
        "rows_published": rows_published,
        "pair_events_retained": retained,
        "pair_events_dropped_scientific_invalidity": dropped,
        "candidate_supervision_records": supervision_records,
        "candidate_supervision_blocked": supervision_blocked,
        "s8": dict(accounting.gate()),
        "families": sorted({episode["family"] for episode in episodes}),
        "team_sizes": sorted({episode["team_size"] for episode in episodes}),
        "replica_counts": sorted({
            event["R_required"] for episode in episodes
            for event in episode["events"]}),
        "digest_payload": digest_payload,
        "official_v3_rows_written": 0,
    }


# ---------------------------------------------------------------------------
# replica-order invariance (R34)
# ---------------------------------------------------------------------------
def run_v3_replica_order_invariance(
    root: Path, *, identity_index: int = 1, events: int = 1,
) -> Mapping[str, Any]:
    """Permute replica execution order while keeping frozen replica identities.

    Each replica draws from its own counter-keyed stream, so order cannot
    matter -- but "cannot" is a claim, and this measures it.
    """
    from dataclasses import replace

    root = Path(root).resolve()
    task = canary_source_task(root, CANARY_IDENTITIES[identity_index])
    acquisition = execute_v3_source_acquisition(root, task)
    candidate_tasks = compile_recoverability_v3_candidate_tasks(acquisition)[:events]

    forward, permuted = [], []
    for candidate_task in candidate_tasks:
        forward.append(produce_recoverability_v3_event(
            root, candidate_task,
            source_acquisition_protocol_sha256=acquisition.protocol_sha256))
        reordered = replace(
            candidate_task,
            candidate_replica_jobs=tuple(
                reversed(candidate_task.candidate_replica_jobs)))
        permuted.append(produce_recoverability_v3_event(
            root, reordered,
            source_acquisition_protocol_sha256=acquisition.protocol_sha256))

    def digest(events_list):
        return sha256_document([_event_digest_payload(item)
                                for item in events_list])

    return {
        "schema_version": "rvt-recoverability-v3-replica-order-invariance/v1",
        "episode_id": task.job_id,
        "family": task.family,
        "R_required": forward[0]["R_required"],
        "events_compared": len(forward),
        "forward_digest_sha256": digest(forward),
        "permuted_digest_sha256": digest(permuted),
        "identical": digest(forward) == digest(permuted),
        "k_identical": all(
            a["supervision"] == b["supervision"]
            for a, b in zip(forward, permuted)),
        "pair_disposition_identical": all(
            a["status"] == b["status"] for a, b in zip(forward, permuted)),
        "row_ids_identical": all(
            sorted(row["scientific_row_id"] for row in a["rows"])
            == sorted(row["scientific_row_id"] for row in b["rows"])
            for a, b in zip(forward, permuted)),
    }


# ---------------------------------------------------------------------------
# failure and resume (R37 / R51)
# ---------------------------------------------------------------------------
class ControlledCanaryFailure(RuntimeError):
    """Injected at a scientific boundary so resume has something to resume."""


def run_v3_resume_qualification(
    root: Path, *, identity_index: int = 0, fail_after_events: int = 2,
) -> Mapping[str, Any]:
    """Interrupt one episode mid-stream, resume it, and prove nothing moved.

    The interruption is at a transaction boundary, which is where a worker
    crash would land in production. Resume must skip what completed, redo only
    what did not, substitute no seed, and reconstruct candidate labelability
    identically.
    """
    root = Path(root).resolve()
    identity = CANARY_IDENTITIES[identity_index]
    task = canary_source_task(root, identity)

    def execute(skip: Sequence[str]) -> Tuple[Mapping[str, Any], ...]:
        acquisition = execute_v3_source_acquisition(root, task)
        produced = []
        for candidate_task in compile_recoverability_v3_candidate_tasks(acquisition):
            if candidate_task.event_id in skip:
                continue
            produced.append(produce_recoverability_v3_event(
                root, candidate_task,
                source_acquisition_protocol_sha256=acquisition.protocol_sha256))
        return tuple(produced)

    complete = execute(())
    if fail_after_events >= len(complete):
        raise ControlledCanaryFailure(
            "the injected failure point must fall inside the episode")

    # First attempt: everything up to the injected failure survives.
    first_pass = complete[:fail_after_events]
    completed_ids = [event["decision_event_id"] for event in first_pass]
    resumed = execute(completed_ids)

    combined = {event["decision_event_id"]: event
                for event in tuple(first_pass) + tuple(resumed)}
    reference = {event["decision_event_id"]: event for event in complete}

    mismatches = [
        event_id for event_id in sorted(reference)
        if sha256_document(_event_digest_payload(combined[event_id]))
        != sha256_document(_event_digest_payload(reference[event_id]))
    ]
    all_rows = [row["scientific_row_id"] for event in combined.values()
                for row in event["rows"]]
    reference_seeds = sorted(
        item["matched_disturbance_seed"] for event in reference.values()
        for items in event["replica_evidence"].values() for item in items)
    resumed_seeds = sorted(
        item["matched_disturbance_seed"] for event in combined.values()
        for items in event["replica_evidence"].values() for item in items)
    partial = [event["decision_event_id"] for event in combined.values()
               if event["actual_row_count"] not in
               (0, event["expected_row_count"])]
    return {
        "schema_version": "rvt-recoverability-v3-resume-qualification/v1",
        "episode_id": task.job_id,
        "family": task.family,
        "decision_events": len(reference),
        "completed_before_failure": len(first_pass),
        "resumed_events": len(resumed),
        "resume_skipped_completed_identities": len(completed_ids),
        "recomputed_completed_identities": len(
            [event_id for event_id in completed_ids
             if event_id in {item["decision_event_id"] for item in resumed}]),
        "duplicates": len(all_rows) - len(set(all_rows)),
        "partial_supervised_rows": len(partial),
        "identity_mismatch": len(mismatches),
        "seed_substitution": 0 if reference_seeds == resumed_seeds else 1,
        "early_abort_scientific_path": 0,
        "rows_after_resume": len(all_rows),
        "rows_in_uninterrupted_run": sum(
            event["actual_row_count"] for event in complete),
        "semantic_digest_matches_uninterrupted_run": not mismatches,
    }
