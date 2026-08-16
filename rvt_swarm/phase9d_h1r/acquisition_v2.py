"""Recoverability source-acquisition protocol V2 -- realized-trajectory rules.

The single semantic change against V1 is where a source event may live. V1
scheduled events at fixed fractions of the *nominal* family horizon and built
their identities before the episode ran; Phase 9D-R2 showed the trajectory
usually terminated first, so 5,557 of 6,000 TRAIN and 1,380 of 1,500
VALIDATION scheduled events had no source snapshot at all.

V2 inverts the order. The episode runs first, the realized source-state
universe is enumerated from already-authoritative runtime state, and only then
is a bounded number of events selected from states that demonstrably exist.

Nothing here touches Target V4, candidate semantics, matched randomness,
replica counts, pair reconciliation, safety or topology science. Selection is
candidate-blind by construction: no function in this module accepts a
candidate outcome, a label, a disposition or a model output, and
`recoverability_source_event_id_v2` rejects those keys explicitly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from ..phase8.common import sha256_document

SOURCE_ACQUISITION_SCHEMA_VERSION = "rvt-recoverability-source-acquisition/v2"
SOURCE_EVENT_IDENTITY_SCHEMA_VERSION = "rvt-recoverability-source-event-identity/v2"

#: Frozen minimum temporal spacing between retained decision events, from
#: `docs/RVT_DECISION_STATE_SAMPLING_PROTOCOL.md`: 1.5 s at the frozen
#: 0.15 s control period. The universe is defined on this grid so that every
#: subset of it satisfies the frozen spacing constraint by construction.
MINIMUM_SPACING_SECONDS = 1.5
CONTROL_PERIOD_SECONDS = 0.15
MINIMUM_SPACING_CONTROL_STEPS = 10

#: The maximum number of retained events per source episode under V2. This is a
#: *cap*, never a quota: an episode whose realized universe is smaller yields
#: fewer events and no state is ever fabricated. It is far below the frozen
#: `maximum_events_per_episode = 12`.
DEFAULT_K = 5

FIRST_K_ELIGIBLE = "FIRST_K_ELIGIBLE"
FIXED_SOURCE_TIME_STRIDE = "FIXED_SOURCE_TIME_STRIDE"
REALIZED_TRAJECTORY_UNIFORM_K = "REALIZED_TRAJECTORY_UNIFORM_K"
REALIZED_LEGACY_STAGE_ONLY = "REALIZED_LEGACY_STAGE_ONLY"

#: Absolute stride for the fixed-time alternative: 15 s, family-independent.
FIXED_STRIDE_CONTROL_STEPS = 100

#: The V1 slot positions, retained only as a comparison baseline.
LEGACY_HORIZON_FRACTIONS: Tuple[float, ...] = (0.10, 0.30, 0.50, 0.70, 0.90)

DESIGN_PILOT_STUDY = "study_a_design_pilot"

#: Terminal causes that leave the *current* control step realized: they are
#: detected after integration and after the clock advanced, so the post-step
#: state at that step exists and is a legitimate source snapshot. R2 verified
#: this ordering directly against `session.py` and refuted the hypothesis that
#: same-timestep terminal events cannot be captured.
TERMINAL_CAUSES_WITH_REALIZED_STEP: Tuple[str, ...] = (
    "COLLISION", "WORLD_BOUNDARY_EXIT", "PERSISTENT_DEADLOCK", "GOAL_COMPLETE",
    "HORIZON_COMPLETE",
)

#: Terminal causes that abort before the step is realized. `NUMERICAL_INVALID`
#: returns from `step()` before integration, so no new state exists;
#: `INITIALIZATION_INVALID` means the episode never produced any state at all.
TERMINAL_CAUSES_WITHOUT_REALIZED_STEP: Tuple[str, ...] = (
    "NUMERICAL_INVALID", "INITIALIZATION_INVALID",
)


class AcquisitionError(ValueError):
    """A V2 acquisition contract violation that must not be papered over."""


@dataclass(frozen=True)
class RealizedSourceState:
    """One realized, candidate-neutral source state on the frozen spacing grid.

    `source_state_fingerprint` is the canonical execution-state hash already
    used by the counterfactual snapshot machinery, so a V2 event points at
    exactly the state the existing `snapshot()` would restore.
    """

    universe_index: int
    control_step: int
    time_seconds: float
    source_state_fingerprint: str
    is_terminal_step: bool
    #: Optional source-only descriptors (for example longitudinal progress)
    #: recorded for audit and coverage reporting. They are never read by any
    #: selection rule; `select()` receives only the universe size and indices.
    descriptors: Mapping[str, Any] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "universe_index": int(self.universe_index),
            "control_step": int(self.control_step),
            "time_seconds": round(float(self.time_seconds), 9),
            "source_state_fingerprint": self.source_state_fingerprint,
            "is_terminal_step": bool(self.is_terminal_step),
            "descriptors": dict(self.descriptors or {}),
        }


@dataclass(frozen=True)
class SourceStateUniverse:
    """`U = [u_0 .. u_(M-1)]` for one realized source episode."""

    states: Tuple[RealizedSourceState, ...]
    terminal_cause: Optional[str]
    terminal_control_step: int
    episode_realized: bool

    @property
    def M(self) -> int:                                       # noqa: N802
        return len(self.states)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "M": self.M,
            "terminal_cause": self.terminal_cause,
            "terminal_control_step": int(self.terminal_control_step),
            "episode_realized": bool(self.episode_realized),
            "states": [state.as_dict() for state in self.states],
        }


def enumerate_realized_source_universe(
    session,
    *,
    spacing_control_steps: int = MINIMUM_SPACING_CONTROL_STEPS,
    include_initial_state: bool = True,
    fingerprint: Optional[Callable[[Any], str]] = None,
    descriptor: Optional[Callable[[Any], Mapping[str, Any]]] = None,
    maximum_control_steps: int = 200000,
) -> SourceStateUniverse:
    """Run one source episode and collect its realized eligible states.

    Eligibility is source-only and candidate-neutral. A control step enters the
    universe when, and only when:

    1. the episode initialized validly;
    2. the step was actually attained, meaning `step()` advanced the clock
       rather than aborting before integration;
    3. the step lies on the frozen minimum-spacing grid.

    No candidate rollout is executed, no Target V4 predicate is evaluated and
    no label exists at this point. The episode is consumed by this call.
    """
    if spacing_control_steps < 1:
        raise AcquisitionError("spacing must be at least one control step")
    if fingerprint is None:
        from ..phase9c_rb.counterfactual import canonical_execution_hash
        fingerprint = canonical_execution_hash

    initial_cause = None if session.termination is None else session.termination.cause
    if initial_cause == "INITIALIZATION_INVALID":
        # No realized source state ever existed. Under V2 this episode
        # contributes M = 0 and therefore zero recoverability source events.
        return SourceStateUniverse(states=(), terminal_cause=initial_cause,
                                   terminal_control_step=int(session.control_step),
                                   episode_realized=False)

    collected: list = []
    recorded_steps: set = set()

    def record(is_terminal: bool) -> None:
        step = int(session.control_step)
        if step in recorded_steps:
            return
        recorded_steps.add(step)
        collected.append(RealizedSourceState(
            universe_index=len(collected), control_step=step,
            time_seconds=float(session.time_seconds),
            source_state_fingerprint=fingerprint(session),
            is_terminal_step=is_terminal,
            descriptors=(dict(descriptor(session)) if descriptor is not None else {})))

    if include_initial_state and int(session.control_step) % spacing_control_steps == 0:
        record(session.termination is not None)

    guard = 0
    while session.termination is None:
        guard += 1
        if guard > maximum_control_steps:
            raise AcquisitionError("source episode exceeded the control-step guard")
        before = int(session.control_step)
        session.step()
        if int(session.control_step) == before:
            # Aborted before integration (NUMERICAL_INVALID): nothing new was
            # realized, so nothing may be recorded for this step.
            break
        if int(session.control_step) % spacing_control_steps == 0:
            record(session.termination is not None)

    terminal_cause = None if session.termination is None else session.termination.cause
    return SourceStateUniverse(
        states=tuple(collected), terminal_cause=terminal_cause,
        terminal_control_step=int(session.control_step),
        episode_realized=True)


# ---------------------------------------------------------------------------
# selection rules -- every one of them is a pure function of source-only data
# ---------------------------------------------------------------------------
def select_first_k_eligible(universe: SourceStateUniverse, k: int = DEFAULT_K):
    """The first `k` realized states. Maximally early-biased."""
    return tuple(range(min(int(k), universe.M)))


def select_fixed_source_time_stride(
    universe: SourceStateUniverse, k: int = DEFAULT_K,
    stride_control_steps: int = FIXED_STRIDE_CONTROL_STEPS,
):
    """Realized states nearest to a family-independent absolute time stride."""
    wanted = [index * int(stride_control_steps) for index in range(int(k))]
    by_step = {state.control_step: state.universe_index for state in universe.states}
    return tuple(sorted({by_step[step] for step in wanted if step in by_step}))


def select_realized_trajectory_uniform_k(
    universe: SourceStateUniverse, k: int = DEFAULT_K,
):
    """`idx_j = floor(j * (M - 1) / (K - 1))`, the proposed V2 rule.

    M = 0 emits nothing. `1 <= M <= K` retains every realized eligible state,
    so no nonexistent state is ever fabricated. `M > K` spreads exactly K
    indices across the realized trajectory with the first and last realized
    eligible states always included.
    """
    k = int(k)
    if k < 1:
        raise AcquisitionError("K must be at least 1")
    M = universe.M                                            # noqa: N806
    if M == 0:
        return ()
    if M <= k:
        return tuple(range(M))
    if k == 1:
        return (0,)
    return tuple(sorted({(j * (M - 1)) // (k - 1) for j in range(k)}))


def select_realized_legacy_stage_only(
    universe: SourceStateUniverse, k: int = DEFAULT_K,
    *, horizon_seconds: float,
    fractions: Sequence[float] = LEGACY_HORIZON_FRACTIONS,
):
    """The V1 nominal-horizon slots, kept only where they were realized.

    This is the comparison baseline, not a candidate rule: it reproduces
    exactly the acquisition behaviour Phase 9D-R2 found infeasible.
    """
    period = CONTROL_PERIOD_SECONDS
    wanted = []
    for fraction in fractions[:int(k)]:
        step = int(round(float(fraction) * float(horizon_seconds) / period))
        wanted.append(step - (step % MINIMUM_SPACING_CONTROL_STEPS))
    by_step = {state.control_step: state.universe_index for state in universe.states}
    return tuple(sorted({by_step[step] for step in wanted if step in by_step}))


_RULES: Mapping[str, Any] = {
    FIRST_K_ELIGIBLE: select_first_k_eligible,
    FIXED_SOURCE_TIME_STRIDE: select_fixed_source_time_stride,
    REALIZED_TRAJECTORY_UNIFORM_K: select_realized_trajectory_uniform_k,
    REALIZED_LEGACY_STAGE_ONLY: select_realized_legacy_stage_only,
}


def select(rule: str, universe: SourceStateUniverse, k: int = DEFAULT_K, **kwargs):
    """Dispatch by rule name. Returns universe indices in ascending order."""
    if rule not in _RULES:
        raise AcquisitionError(f"unknown source-acquisition rule {rule!r}")
    indices = _RULES[rule](universe, k, **kwargs)
    if len(set(indices)) != len(indices):
        raise AcquisitionError("selection produced duplicate universe indices")
    if list(indices) != sorted(indices):
        raise AcquisitionError("selection must be returned in ascending order")
    if any(index < 0 or index >= universe.M for index in indices):
        raise AcquisitionError("selection escaped the realized universe")
    if len(indices) > int(k):
        raise AcquisitionError("selection exceeded K")
    return tuple(indices)


# ---------------------------------------------------------------------------
# the protocol object and its hash
# ---------------------------------------------------------------------------
def acquisition_protocol_v2(
    *, rule: str = REALIZED_TRAJECTORY_UNIFORM_K, k: int = DEFAULT_K,
    spacing_control_steps: int = MINIMUM_SPACING_CONTROL_STEPS,
    include_initial_state: bool = True,
) -> Dict[str, Any]:
    """The candidate-blind acquisition contract, as canonical data."""
    if rule not in _RULES:
        raise AcquisitionError(f"unknown source-acquisition rule {rule!r}")
    return {
        "schema_version": SOURCE_ACQUISITION_SCHEMA_VERSION,
        "rule": rule,
        "K": int(k),
        "K_is_a_maximum_not_a_quota": True,
        "selection_formula": "idx_j = floor(j * (M - 1) / (K - 1)) for j in 0..K-1",
        "empty_universe_behaviour": "M = 0 emits zero recoverability source events",
        "small_universe_behaviour": "1 <= M <= K retains every realized eligible state",
        "fabrication_permitted": False,
        "minimum_spacing_seconds": MINIMUM_SPACING_SECONDS,
        "control_period_seconds": CONTROL_PERIOD_SECONDS,
        "spacing_control_steps": int(spacing_control_steps),
        "include_initial_state": bool(include_initial_state),
        "universe_definition": (
            "realized control steps on the frozen minimum-spacing grid, from a "
            "validly initialized episode, excluding any step aborted before "
            "integration"),
        "terminal_causes_with_realized_step": list(TERMINAL_CAUSES_WITH_REALIZED_STEP),
        "terminal_causes_without_realized_step":
            list(TERMINAL_CAUSES_WITHOUT_REALIZED_STEP),
        "not_a_realized_source_state_is_not_generation_invalid": True,
        "candidate_blind": True,
        "prohibited_selection_inputs": [
            "compact_outcome", "line_outcome", "target_v4_outcome",
            "recoverability_label", "candidate_validity", "pair_retention",
            "model_output", "class_distribution", "h1_performance",
        ],
        "permitted_selection_inputs": [
            "realized control step", "realized time", "source termination cause",
            "realized universe size M", "frozen control period",
            "frozen minimum spacing",
        ],
        "uses_future_source_trajectory_length": True,
        "uses_future_candidate_outcome": False,
        "authorizes_official_generation": False,
    }


def acquisition_protocol_v2_sha256(protocol: Optional[Mapping[str, Any]] = None) -> str:
    return sha256_document(dict(protocol or acquisition_protocol_v2()))


# ---------------------------------------------------------------------------
# V2 event identity
# ---------------------------------------------------------------------------
SOURCE_EVENT_KEY: Tuple[str, ...] = (
    "schema_version", "study", "split", "family", "layout_sha256", "team_size",
    "episode_id", "realized_source_timestep", "source_state_fingerprint",
    "source_acquisition_protocol_sha256",
)

#: Operational and outcome dimensions that must never enter a scientific
#: source-event identity. Passing one is an error, not a silently ignored key.
FORBIDDEN_IDENTITY_FIELDS: Tuple[str, ...] = (
    "worker", "worker_id", "chunk", "chunk_id", "retry", "attempt",
    "attempt_index", "wall_clock", "seconds", "timestamp",
    "candidate_topology", "candidate_result", "compact_outcome", "line_outcome",
    "aggregate_label", "label", "disposition", "target_v4_disposition",
    "model_prediction", "model_output", "pair_retained",
)


def recoverability_source_event_id_v2(key: Mapping[str, Any]) -> str:
    """Canonical identity of one realized V2 recoverability source event."""
    forbidden = [name for name in key if name in FORBIDDEN_IDENTITY_FIELDS]
    if forbidden:
        raise AcquisitionError(
            f"source-event identity must not carry {sorted(forbidden)}; execution "
            "metadata and candidate outcomes are not scientific identity")
    missing = [name for name in SOURCE_EVENT_KEY if name not in key]
    if missing:
        raise AcquisitionError(f"source-event key is missing {missing}")
    extra = [name for name in key if name not in SOURCE_EVENT_KEY]
    if extra:
        raise AcquisitionError(f"source-event key must not carry {extra}")
    if key["schema_version"] != SOURCE_EVENT_IDENTITY_SCHEMA_VERSION:
        raise AcquisitionError("unknown source-event identity schema")
    step = key["realized_source_timestep"]
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise AcquisitionError("realized source timestep must be a nonnegative integer")
    return sha256_document({name: key[name] for name in SOURCE_EVENT_KEY})


def build_source_event_key(
    *, study: str, split: str, family: str, layout_sha256: str, team_size: int,
    episode_id: str, state: RealizedSourceState, protocol_sha256: str,
) -> Dict[str, Any]:
    return {
        "schema_version": SOURCE_EVENT_IDENTITY_SCHEMA_VERSION,
        "study": study, "split": split, "family": family,
        "layout_sha256": layout_sha256, "team_size": int(team_size),
        "episode_id": episode_id,
        "realized_source_timestep": int(state.control_step),
        "source_state_fingerprint": state.source_state_fingerprint,
        "source_acquisition_protocol_sha256": protocol_sha256,
    }


def selected_events(
    universe: SourceStateUniverse, indices: Sequence[int], *, study: str, split: str,
    family: str, layout_sha256: str, team_size: int, episode_id: str,
    protocol_sha256: str,
):
    """Materialize the V2 source events for one episode, in ascending order."""
    events = []
    for index in indices:
        state = universe.states[index]
        key = build_source_event_key(
            study=study, split=split, family=family, layout_sha256=layout_sha256,
            team_size=team_size, episode_id=episode_id, state=state,
            protocol_sha256=protocol_sha256)
        events.append({"source_event_id_v2": recoverability_source_event_id_v2(key),
                       **key})
    return tuple(events)
