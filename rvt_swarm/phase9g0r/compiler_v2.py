"""Recoverability V2 task compilation -- realized states, never scheduled slots.

Phase 9G-V2Q finding V2Q-F1: the V1 compiler reads a precomputed
`resolved_control_step` out of the frozen V1 job manifest, so every event exists
before the episode runs and most of them are never reached. V2 inverts that.

Two stages (I6):

* **Stage A** runs the source episode, enumerates the realized eligible
  universe `U`, applies the frozen `REALIZED_TRAJECTORY_UNIFORM_K` rule with
  K=5, and produces an immutable acquisition record. No candidate has executed
  at this point and nothing here can read a candidate outcome.
* **Stage B** turns each already-selected realized state into a candidate task.

Stage B cannot modify Stage A: the acquisition record is frozen and every Stage
B task carries the Stage A source-state fingerprint it was built from.

Matched randomness is unchanged. Seeds still come from the frozen
`derive_generation_seed` PRF, with the selection ordinal playing the role V1
gave to the slot index, and the matched disturbance seed still omits candidate
topology so COMPACT and LINE receive the same realization.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from ..phase8.common import sha256_document
from ..phase9b.identity import derive_generation_seed
from ..phase9c_rb.counterfactual import canonical_execution_hash, replica_count_for_family
from ..phase9d_h1r.acquisition_v2 import (
    DEFAULT_K, MINIMUM_SPACING_CONTROL_STEPS, REALIZED_TRAJECTORY_UNIFORM_K,
    SOURCE_EVENT_IDENTITY_SCHEMA_VERSION, build_source_event_key,
    enumerate_realized_source_universe, frozen_acquisition_protocol_v2,
    frozen_acquisition_protocol_v2_sha256, recoverability_source_event_id_v2,
    select,
)
from ..phase9d_h1r.exclusion import design_pilot_identity
from ..topology_registry import COMPACT, LINE
from .compiler import (
    OfficialDecisionEventTask, OfficialSourceTask, OfficialTaskCompilerError,
    compile_source_tasks,
)
from .contracts_v2 import RECOVERABILITY_PROTOCOL_V2

V2_SOURCE_MANIFEST_SCHEMA_VERSION = "rvt-recoverability-v2-source-manifest/v1"
V2_ACQUISITION_SCHEMA_VERSION = "rvt-recoverability-v2-source-acquisition-record/v1"

#: The scientific unit of a V2 manifest is the fixed source episode. Realized
#: event counts emerge from the trajectories; they are never budgeted (I15).
FROZEN_V2_SOURCE_EPISODE_BUDGET: Mapping[str, int] = {"train": 1200, "validation": 300}
#: K = 5 maxima, recorded for reconciliation only -- never as a target.
FROZEN_V2_MAXIMUM_SELECTED_EVENTS: Mapping[str, int] = {"train": 6000, "validation": 1500}

SEALED_STUDIES = ("study_a_n24_evaluation", "study_b_with_n24", "final_test")
SEALED_SPLITS = ("n24_evaluation", "final_test", "test")

_EXCLUSION_ARTIFACTS = (
    "results/rvt_fd24/phase9d_h1r_design_pilot_exclusion_set_v1.json",
    "results/rvt_fd24/phase9g_v2q_qualification_canary_exclusion_set_v1.json",
)


class V2CompilerError(OfficialTaskCompilerError):
    """A V2 compilation that must fail closed."""


@dataclass(frozen=True)
class V2SelectedSourceState:
    """One realized state that survived the frozen K=5 selection."""

    selection_ordinal: int
    universe_index: int
    realized_control_step: int
    realized_time_seconds: float
    source_state_fingerprint: str
    source_event_id: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "selection_ordinal": int(self.selection_ordinal),
            "universe_index": int(self.universe_index),
            "realized_control_step": int(self.realized_control_step),
            "realized_time_seconds": round(float(self.realized_time_seconds), 9),
            "source_state_fingerprint": self.source_state_fingerprint,
            "source_event_id": self.source_event_id,
        }


@dataclass(frozen=True)
class V2SourceAcquisition:
    """Immutable Stage A output for one source episode."""

    source: OfficialSourceTask
    protocol_sha256: str
    M: int                                                    # noqa: N815
    terminal_cause: Optional[str]
    terminal_control_step: int
    universe_fingerprints: Tuple[str, ...]
    selected: Tuple[V2SelectedSourceState, ...]

    @property
    def selected_event_count(self) -> int:
        return len(self.selected)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": V2_ACQUISITION_SCHEMA_VERSION,
            "protocol_version": RECOVERABILITY_PROTOCOL_V2,
            "source_acquisition_protocol_sha256": self.protocol_sha256,
            "episode_id": self.source.job_id,
            "study": self.source.study, "split": self.source.split,
            "family": self.source.family, "team_size": self.source.team_size,
            "layout_sha256": self.source.layout_sha256,
            "source_class": self.source.source_class,
            "M": self.M,
            "terminal_cause": self.terminal_cause,
            "terminal_control_step": self.terminal_control_step,
            "selected_event_count": self.selected_event_count,
            "selected": [state.as_dict() for state in self.selected],
        }

    def acquisition_sha256(self) -> str:
        return sha256_document(self.as_dict())


# ---------------------------------------------------------------------------
# Stage A -- source execution and candidate-blind selection
# ---------------------------------------------------------------------------
def execute_v2_source_acquisition(
    root: Path, source: OfficialSourceTask, *,
    session_factory=None, protocol_sha256: Optional[str] = None,
) -> V2SourceAcquisition:
    """Run one source episode and freeze its selected realized states.

    No candidate rollout is executed here and no candidate outcome exists yet,
    so selection is candidate-blind by construction rather than by convention.
    """
    protocol_sha256 = protocol_sha256 or frozen_acquisition_protocol_v2_sha256(
        frozen_acquisition_protocol_v2())
    if session_factory is None:
        from .producer import build_source_session
        session = build_source_session(root, source)
    else:
        session = session_factory(root, source)

    universe = enumerate_realized_source_universe(
        session, spacing_control_steps=MINIMUM_SPACING_CONTROL_STEPS,
        include_initial_state=True, fingerprint=canonical_execution_hash)
    indices = select(REALIZED_TRAJECTORY_UNIFORM_K, universe, DEFAULT_K)

    selected = []
    for ordinal, index in enumerate(indices):
        state = universe.states[index]
        key = build_source_event_key(
            study=source.study, split=source.split, family=source.family,
            layout_sha256=source.layout_sha256, team_size=source.team_size,
            episode_id=source.job_id, state=state, protocol_sha256=protocol_sha256)
        selected.append(V2SelectedSourceState(
            selection_ordinal=ordinal, universe_index=index,
            realized_control_step=state.control_step,
            realized_time_seconds=state.time_seconds,
            source_state_fingerprint=state.source_state_fingerprint,
            source_event_id=recoverability_source_event_id_v2(key)))

    if len(selected) > DEFAULT_K:
        raise V2CompilerError("V2 acquisition exceeded K")
    if universe.M == 0 and selected:
        raise V2CompilerError("M = 0 must yield zero source events")
    return V2SourceAcquisition(
        source=source, protocol_sha256=protocol_sha256, M=universe.M,
        terminal_cause=universe.terminal_cause,
        terminal_control_step=universe.terminal_control_step,
        universe_fingerprints=tuple(state.source_state_fingerprint
                                    for state in universe.states),
        selected=tuple(selected))


# ---------------------------------------------------------------------------
# Stage B -- candidate tasks from already-selected realized states
# ---------------------------------------------------------------------------
def _replica_jobs(acquisition: V2SourceAcquisition,
                  state: V2SelectedSourceState, replicas: int):
    """Frozen matched randomness: identical `derive_generation_seed` PRF, and
    the matched disturbance seed still omits candidate topology so COMPACT and
    LINE receive the same disturbance realization."""
    source = acquisition.source
    jobs = []
    for replica_index in range(replicas):
        common = {
            "study": source.study, "split": source.split,
            "scenario_family": source.family,
            "layout_sha256": source.layout_sha256,
            "team_size": source.team_size,
            "source_class": source.source_class,
            "episode_index": source.episode_index,
            "event_slot_index": state.selection_ordinal,
            "replica_index": replica_index,
        }
        matched = derive_generation_seed(
            "counterfactual_rollout", candidate_topology=None, **common)
        for candidate in (COMPACT, LINE):
            jobs.append({
                "candidate_topology": int(candidate),
                "replica_index": replica_index,
                "seeds": {
                    "candidate_replica_job_seed": derive_generation_seed(
                        "counterfactual_rollout",
                        candidate_topology=int(candidate), **common),
                    "matched_disturbance_seed": matched,
                },
                "protocol_version": RECOVERABILITY_PROTOCOL_V2,
                "source_state_fingerprint": state.source_state_fingerprint,
            })
    return tuple(jobs)


def compile_recoverability_v2_candidate_tasks(
    acquisition: V2SourceAcquisition,
) -> Tuple[OfficialDecisionEventTask, ...]:
    """One decision-event task per already-selected realized source state.

    `resolved_control_step` is the realized control step, so the V1
    source-terminated-before-event branch is unreachable by construction.
    """
    replicas = replica_count_for_family(acquisition.source.family)
    tasks = []
    for state in acquisition.selected:
        if state.realized_control_step > acquisition.terminal_control_step:
            raise V2CompilerError(
                "a V2 candidate task escaped the realized source trajectory")
        tasks.append(OfficialDecisionEventTask(
            event_id=state.source_event_id,
            source=acquisition.source,
            event_slot_index=state.selection_ordinal,
            resolved_control_step=state.realized_control_step,
            resolved_timestamp_seconds=state.realized_time_seconds,
            replicas_per_candidate=replicas,
            candidate_replica_jobs=_replica_jobs(acquisition, state, replicas)))
    if len({task.event_id for task in tasks}) != len(tasks):
        raise V2CompilerError("duplicate V2 decision-event identity")
    return tuple(tasks)


# ---------------------------------------------------------------------------
# the fixed-budget V2 source manifest
# ---------------------------------------------------------------------------
def load_v2_excluded_identities(root: Path) -> set:
    import json
    burned = set()
    for relative in _EXCLUSION_ARTIFACTS:
        path = root / relative
        if not path.exists():
            continue
        document = json.loads(path.read_text(encoding="ascii"))
        burned |= {str(entry["design_pilot_identity_sha256"])
                   for entry in document.get("excluded_identities", [])}
    return burned


def _source_identity(task: OfficialSourceTask) -> Mapping[str, Any]:
    import json
    return {
        "study": task.study, "split": task.split, "family": task.family,
        "team_size": task.team_size, "layout_id": task.layout_id,
        "source_policy": task.source_class, "episode_id": task.job_id,
        "seed_identity": json.dumps(task.seeds, sort_keys=True),
    }


def compile_recoverability_v2_source_episodes(
    root: Path, *, study: str, split: str,
    excluded: Optional[Iterable[str]] = None,
) -> Tuple[OfficialSourceTask, ...]:
    """The fixed V2 source-episode universe, or a hard failure (I17)."""
    if split not in FROZEN_V2_SOURCE_EPISODE_BUDGET:
        raise V2CompilerError(
            f"split {split!r} has no frozen V2 source-episode budget")
    if study in SEALED_STUDIES:
        raise V2CompilerError(f"sealed study {study!r} may not be compiled")
    tasks = compile_source_tasks(root, study=study, split=split)
    budget = FROZEN_V2_SOURCE_EPISODE_BUDGET[split]
    if len(tasks) != budget:
        raise V2CompilerError(
            f"{split} declares {len(tasks)} source episodes against the frozen "
            f"budget of {budget}; budgets are fixed and never adaptively refilled")

    burned = set(excluded) if excluded is not None else load_v2_excluded_identities(root)
    seen = set()
    for task in tasks:
        if task.study in SEALED_STUDIES or task.split in SEALED_SPLITS:
            raise V2CompilerError("sealed domain entered V2 compilation")
        if int(task.team_size) == 24:
            raise V2CompilerError("N=24 is sealed and may not enter a V2 manifest")
        identity = design_pilot_identity(**_source_identity(task))
        if identity in burned:
            raise V2CompilerError(
                f"source identity {identity[:16]}... was consumed by a V2 design "
                "pilot or qualification canary and is permanently excluded")
        if identity in seen:
            raise V2CompilerError("duplicate V2 source-episode identity")
        seen.add(identity)
    return tasks


def compile_recoverability_v2_source_manifest(
    root: Path, *, study: str, split: str,
    excluded: Optional[Iterable[str]] = None,
) -> Mapping[str, Any]:
    """Compile the future official V2 manifest. Never executes anything."""
    tasks = compile_recoverability_v2_source_episodes(
        root, study=study, split=split, excluded=excluded)
    protocol_sha = frozen_acquisition_protocol_v2_sha256(
        frozen_acquisition_protocol_v2())
    from .contracts_v2 import (
        TARGET_V4_SHA256, recoverability_row_binding_v2_spec_sha256,
    )
    manifest = {
        "schema_version": V2_SOURCE_MANIFEST_SCHEMA_VERSION,
        "protocol_version": RECOVERABILITY_PROTOCOL_V2,
        "study": study, "split": split,
        "scientific_unit": "SOURCE_EPISODE",
        "source_episodes": len(tasks),
        "frozen_source_episode_budget": FROZEN_V2_SOURCE_EPISODE_BUDGET[split],
        "maximum_selected_source_events":
            FROZEN_V2_MAXIMUM_SELECTED_EVENTS[split],
        "maximum_is_a_cap_not_a_target": True,
        "realized_event_count_is_emergent": True,
        "adaptive_refill_permitted": False,
        "outcome_dependent_stopping_permitted": False,
        "source_acquisition_protocol_sha256": protocol_sha,
        "acquisition_rule": REALIZED_TRAJECTORY_UNIFORM_K,
        "K": DEFAULT_K,
        "target_v4_contract_sha256": TARGET_V4_SHA256,
        "recoverability_row_binding_v2_spec_sha256":
            recoverability_row_binding_v2_spec_sha256(),
        "source_event_identity_schema": SOURCE_EVENT_IDENTITY_SCHEMA_VERSION,
        "families": sorted({task.family for task in tasks},
                           key=lambda name: int(name[1:])),
        "team_sizes": sorted({task.team_size for task in tasks}),
        "source_policies": sorted({task.source_class for task in tasks}),
        "n24_episodes": 0, "study_b_episodes": 0, "final_test_episodes": 0,
        "episode_identity_sha256": sorted(
            design_pilot_identity(**_source_identity(task)) for task in tasks),
        "authorizes_official_generation": False,
    }
    manifest["v2_source_manifest_sha256"] = sha256_document(manifest)
    return manifest
