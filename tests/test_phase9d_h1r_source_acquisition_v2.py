"""Phase 9D-H1R -- Recoverability source-acquisition protocol V2.

These tests pin the acquisition semantics that Phase 9D-R2 showed V1 lacked: a
source event may exist only where a source state was actually realized, the
selection is candidate-blind and deterministic, and no operational or outcome
dimension may enter the scientific identity.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9d_h1r.acquisition_v2 import (
    DEFAULT_K,
    FIRST_K_ELIGIBLE,
    FIXED_SOURCE_TIME_STRIDE,
    FORBIDDEN_IDENTITY_FIELDS,
    MINIMUM_SPACING_CONTROL_STEPS,
    REALIZED_LEGACY_STAGE_ONLY,
    REALIZED_TRAJECTORY_UNIFORM_K,
    SOURCE_EVENT_IDENTITY_SCHEMA_VERSION,
    TERMINAL_CAUSES_WITH_REALIZED_STEP,
    TERMINAL_CAUSES_WITHOUT_REALIZED_STEP,
    AcquisitionError,
    RealizedSourceState,
    SourceStateUniverse,
    acquisition_protocol_v2,
    acquisition_protocol_v2_sha256,
    build_source_event_key,
    enumerate_realized_source_universe,
    recoverability_source_event_id_v2,
    select,
    select_realized_trajectory_uniform_k,
    selected_events,
)
from rvt_swarm.phase9d_h1r.exclusion import (
    DesignPilotReuseError,
    assert_not_design_pilot_identity,
    build_exclusion_document,
    design_pilot_identity,
)

ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL_V2 = acquisition_protocol_v2()
PROTOCOL_V2_SHA = acquisition_protocol_v2_sha256(PROTOCOL_V2)


def universe(m: int) -> SourceStateUniverse:
    """A synthetic realized universe of size `m` on the frozen spacing grid."""
    states = tuple(
        RealizedSourceState(
            universe_index=index,
            control_step=index * MINIMUM_SPACING_CONTROL_STEPS,
            time_seconds=index * MINIMUM_SPACING_CONTROL_STEPS * 0.15,
            source_state_fingerprint=hashlib.sha256(
                b"state-%d" % index).hexdigest(),
            is_terminal_step=(index == m - 1),
            descriptors={})
        for index in range(m))
    return SourceStateUniverse(states=states, terminal_cause="GOAL_COMPLETE",
                               terminal_control_step=max(m - 1, 0)
                               * MINIMUM_SPACING_CONTROL_STEPS,
                               episode_realized=True)


# ---------------------------------------------------------------------------
# M semantics -- the core of the V1 repair
# ---------------------------------------------------------------------------
def test_m_zero_emits_no_source_events_and_fabricates_nothing() -> None:
    empty = SourceStateUniverse(states=(), terminal_cause="INITIALIZATION_INVALID",
                                terminal_control_step=0, episode_realized=False)
    assert empty.M == 0
    for rule in (FIRST_K_ELIGIBLE, FIXED_SOURCE_TIME_STRIDE,
                 REALIZED_TRAJECTORY_UNIFORM_K):
        assert select(rule, empty, DEFAULT_K) == ()
    assert select(REALIZED_LEGACY_STAGE_ONLY, empty, DEFAULT_K,
                  horizon_seconds=90.0) == ()


def test_m_one_retains_the_single_realized_state() -> None:
    assert select(REALIZED_TRAJECTORY_UNIFORM_K, universe(1), DEFAULT_K) == (0,)


@pytest.mark.parametrize("m", [2, 3, 4])
def test_m_below_k_retains_every_realized_state(m: int) -> None:
    selected = select(REALIZED_TRAJECTORY_UNIFORM_K, universe(m), DEFAULT_K)
    assert selected == tuple(range(m))
    assert len(selected) == m < DEFAULT_K


def test_m_equal_k_retains_every_realized_state() -> None:
    assert select(REALIZED_TRAJECTORY_UNIFORM_K, universe(DEFAULT_K),
                  DEFAULT_K) == (0, 1, 2, 3, 4)


def test_m_above_k_selects_exactly_k_uniform_indices() -> None:
    assert select(REALIZED_TRAJECTORY_UNIFORM_K, universe(13), DEFAULT_K) == (
        0, 3, 6, 9, 12)
    assert select(REALIZED_TRAJECTORY_UNIFORM_K, universe(101), DEFAULT_K) == (
        0, 25, 50, 75, 100)


def test_selection_never_exceeds_k_across_a_wide_sweep() -> None:
    for m in range(0, 400):
        assert len(select(REALIZED_TRAJECTORY_UNIFORM_K, universe(m),
                          DEFAULT_K)) <= DEFAULT_K


def test_first_and_last_realized_states_are_always_included_when_m_positive() -> None:
    for m in range(1, 200):
        selected = select(REALIZED_TRAJECTORY_UNIFORM_K, universe(m), DEFAULT_K)
        assert selected[0] == 0
        assert selected[-1] == m - 1


def test_floor_index_formula_is_exact() -> None:
    for m in range(DEFAULT_K + 1, 300):
        expected = sorted({(j * (m - 1)) // (DEFAULT_K - 1)
                           for j in range(DEFAULT_K)})
        assert list(select(REALIZED_TRAJECTORY_UNIFORM_K, universe(m),
                           DEFAULT_K)) == expected


def test_no_duplicate_or_unsorted_selected_indices() -> None:
    for m in range(0, 300):
        selected = select(REALIZED_TRAJECTORY_UNIFORM_K, universe(m), DEFAULT_K)
        assert len(set(selected)) == len(selected)
        assert list(selected) == sorted(selected)


def test_selection_escaping_the_universe_is_rejected() -> None:
    with pytest.raises(AcquisitionError):
        select("NOT_A_RULE", universe(10), DEFAULT_K)


def test_selected_states_respect_the_frozen_minimum_spacing() -> None:
    for m in range(2, 200):
        selected = select(REALIZED_TRAJECTORY_UNIFORM_K, universe(m), DEFAULT_K)
        steps = [universe(m).states[i].control_step for i in selected]
        gaps = [b - a for a, b in zip(steps, steps[1:])]
        assert all(gap >= MINIMUM_SPACING_CONTROL_STEPS for gap in gaps)


# ---------------------------------------------------------------------------
# candidate blindness
# ---------------------------------------------------------------------------
def test_selection_signature_cannot_receive_a_candidate_outcome() -> None:
    with pytest.raises(TypeError):
        select_realized_trajectory_uniform_k(  # type: ignore[call-arg]
            universe(10), DEFAULT_K, aggregate_label=1)


def test_selection_depends_only_on_universe_size() -> None:
    """Two universes with identical M but different state content select the
    same indices -- selection cannot be reading state content, let alone an
    outcome that does not exist yet."""
    left = universe(37)
    right = SourceStateUniverse(
        states=tuple(
            RealizedSourceState(universe_index=s.universe_index,
                                control_step=s.control_step,
                                time_seconds=s.time_seconds,
                                source_state_fingerprint="f" * 64,
                                is_terminal_step=s.is_terminal_step,
                                descriptors={"longitudinal_progress_meters": 1.0})
            for s in left.states),
        terminal_cause="COLLISION",
        terminal_control_step=left.terminal_control_step, episode_realized=True)
    assert select(REALIZED_TRAJECTORY_UNIFORM_K, left, DEFAULT_K) == select(
        REALIZED_TRAJECTORY_UNIFORM_K, right, DEFAULT_K)


def test_protocol_declares_candidate_blindness_and_prohibited_inputs() -> None:
    assert PROTOCOL_V2["candidate_blind"] is True
    assert PROTOCOL_V2["uses_future_candidate_outcome"] is False
    assert PROTOCOL_V2["uses_future_source_trajectory_length"] is True
    for field in ("compact_outcome", "line_outcome", "target_v4_outcome",
                  "recoverability_label", "candidate_validity", "pair_retention",
                  "model_output", "class_distribution", "h1_performance"):
        assert field in PROTOCOL_V2["prohibited_selection_inputs"]


def test_acquisition_hash_excludes_every_candidate_outcome_field() -> None:
    payload = json.dumps(PROTOCOL_V2, sort_keys=True)
    for field in ("aggregate_label", "target_v4_disposition", "model_prediction",
                  "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"):
        assert field not in payload.replace("prohibited_selection_inputs", "")
    assert PROTOCOL_V2_SHA == sha256_document(PROTOCOL_V2)


def test_protocol_does_not_authorize_generation() -> None:
    assert PROTOCOL_V2["authorizes_official_generation"] is False


# ---------------------------------------------------------------------------
# V2 event identity
# ---------------------------------------------------------------------------
def _key(**overrides):
    key = {
        "schema_version": SOURCE_EVENT_IDENTITY_SCHEMA_VERSION,
        "study": "study_a_zero_shot", "split": "validation", "family": "F3",
        "layout_sha256": "a" * 64, "team_size": 8,
        "episode_id": "episode-0", "realized_source_timestep": 120,
        "source_state_fingerprint": "b" * 64,
        "source_acquisition_protocol_sha256": PROTOCOL_V2_SHA,
    }
    key.update(overrides)
    return key


def test_event_identity_is_deterministic() -> None:
    assert recoverability_source_event_id_v2(_key()) == \
        recoverability_source_event_id_v2(_key())


def test_event_identity_separates_v2_from_v1() -> None:
    assert SOURCE_EVENT_IDENTITY_SCHEMA_VERSION.endswith("/v2")
    with pytest.raises(AcquisitionError):
        recoverability_source_event_id_v2(
            _key(schema_version="rvt-recoverability-source-event-identity/v1"))


def test_event_identity_changes_with_the_realized_state() -> None:
    base = recoverability_source_event_id_v2(_key())
    assert recoverability_source_event_id_v2(
        _key(realized_source_timestep=130)) != base
    assert recoverability_source_event_id_v2(
        _key(source_state_fingerprint="c" * 64)) != base
    assert recoverability_source_event_id_v2(
        _key(source_acquisition_protocol_sha256="d" * 64)) != base


@pytest.mark.parametrize("field", sorted(set(FORBIDDEN_IDENTITY_FIELDS)))
def test_event_identity_rejects_operational_and_outcome_fields(field: str) -> None:
    with pytest.raises(AcquisitionError):
        recoverability_source_event_id_v2(_key(**{field: "x"}))


def test_event_identity_rejects_missing_and_extra_fields() -> None:
    incomplete = _key()
    incomplete.pop("family")
    with pytest.raises(AcquisitionError):
        recoverability_source_event_id_v2(incomplete)
    with pytest.raises(AcquisitionError):
        recoverability_source_event_id_v2(_key(unexpected_field="x"))


def test_event_identity_rejects_a_negative_or_boolean_timestep() -> None:
    with pytest.raises(AcquisitionError):
        recoverability_source_event_id_v2(_key(realized_source_timestep=-1))
    with pytest.raises(AcquisitionError):
        recoverability_source_event_id_v2(_key(realized_source_timestep=True))


# ---------------------------------------------------------------------------
# worker / chunk / iteration-order invariance
# ---------------------------------------------------------------------------
def test_selected_events_are_invariant_to_iteration_and_chunk_order() -> None:
    source = universe(41)
    indices = select(REALIZED_TRAJECTORY_UNIFORM_K, source, DEFAULT_K)
    forward = selected_events(
        source, indices, study="study_a_zero_shot", split="train", family="F6",
        layout_sha256="a" * 64, team_size=12, episode_id="episode-3",
        protocol_sha256=PROTOCOL_V2_SHA)
    reversed_input = selected_events(
        source, tuple(sorted(indices, reverse=True)), study="study_a_zero_shot",
        split="train", family="F6", layout_sha256="a" * 64, team_size=12,
        episode_id="episode-3", protocol_sha256=PROTOCOL_V2_SHA)
    assert sorted(e["source_event_id_v2"] for e in forward) == \
        sorted(e["source_event_id_v2"] for e in reversed_input)


def test_event_identity_has_no_worker_or_chunk_dimension() -> None:
    from rvt_swarm.phase9d_h1r.acquisition_v2 import SOURCE_EVENT_KEY
    for banned in ("worker", "chunk", "attempt", "retry", "wall_clock"):
        assert not any(banned in name for name in SOURCE_EVENT_KEY)


# ---------------------------------------------------------------------------
# terminal-step semantics -- the R2 ordering finding, pinned
# ---------------------------------------------------------------------------
def test_same_step_terminal_causes_keep_their_realized_state() -> None:
    for cause in ("COLLISION", "WORLD_BOUNDARY_EXIT", "PERSISTENT_DEADLOCK",
                  "GOAL_COMPLETE", "HORIZON_COMPLETE"):
        assert cause in TERMINAL_CAUSES_WITH_REALIZED_STEP
    for cause in ("NUMERICAL_INVALID", "INITIALIZATION_INVALID"):
        assert cause in TERMINAL_CAUSES_WITHOUT_REALIZED_STEP
    assert not set(TERMINAL_CAUSES_WITH_REALIZED_STEP) & set(
        TERMINAL_CAUSES_WITHOUT_REALIZED_STEP)


def test_universe_marks_its_terminal_state() -> None:
    source = universe(7)
    assert source.states[-1].is_terminal_step is True
    assert all(not state.is_terminal_step for state in source.states[:-1])


class _FakeTermination:
    def __init__(self, cause):
        self.cause = cause


class _FakeSession:
    """Minimal stand-in exercising the enumerator's realization boundary."""

    def __init__(self, steps, terminal_cause, abort_before_integration=False):
        self.control_step = 0
        self.time_seconds = 0.0
        self._limit = steps
        self._cause = terminal_cause
        self._abort = abort_before_integration
        self.termination = None

    def step(self):
        if self.termination is not None:
            return
        if self._abort and self.control_step >= self._limit:
            self.termination = _FakeTermination("NUMERICAL_INVALID")
            return                      # clock does not advance
        self.control_step += 1
        self.time_seconds = self.control_step * 0.15
        if self.control_step >= self._limit:
            self.termination = _FakeTermination(self._cause)


def test_enumerator_records_the_step_of_a_same_step_terminal() -> None:
    session = _FakeSession(30, "COLLISION")
    result = enumerate_realized_source_universe(
        session, fingerprint=lambda s: "f%d" % s.control_step)
    assert [state.control_step for state in result.states] == [0, 10, 20, 30]
    assert result.terminal_cause == "COLLISION"
    assert result.states[-1].is_terminal_step is True


def test_enumerator_does_not_record_a_step_aborted_before_integration() -> None:
    session = _FakeSession(20, "NUMERICAL_INVALID", abort_before_integration=True)
    result = enumerate_realized_source_universe(
        session, fingerprint=lambda s: "f%d" % s.control_step)
    assert [state.control_step for state in result.states] == [0, 10, 20]
    assert result.terminal_cause == "NUMERICAL_INVALID"


def test_initialization_invalid_yields_an_empty_universe() -> None:
    session = _FakeSession(0, "INITIALIZATION_INVALID")
    session.termination = _FakeTermination("INITIALIZATION_INVALID")
    result = enumerate_realized_source_universe(
        session, fingerprint=lambda s: "f")
    assert result.M == 0
    assert result.episode_realized is False
    assert select(REALIZED_TRAJECTORY_UNIFORM_K, result, DEFAULT_K) == ()


def test_enumerator_only_records_grid_steps() -> None:
    session = _FakeSession(27, "GOAL_COMPLETE")
    result = enumerate_realized_source_universe(
        session, fingerprint=lambda s: "f%d" % s.control_step)
    assert [state.control_step for state in result.states] == [0, 10, 20]


# ---------------------------------------------------------------------------
# design-pilot exclusion
# ---------------------------------------------------------------------------
PILOT_FIELDS = {
    "study": "study_a_design_pilot", "split": "design_pilot", "family": "F4",
    "team_size": 16, "layout_id": "train-f4-00",
    "source_policy": "S1_ALWAYS_COMPACT", "episode_id": "design-pilot/episode-0",
    "seed_identity": "e" * 64,
}


def test_design_pilot_identity_is_deterministic_and_complete() -> None:
    assert design_pilot_identity(**PILOT_FIELDS) == design_pilot_identity(
        **PILOT_FIELDS)
    partial = dict(PILOT_FIELDS)
    partial.pop("seed_identity")
    with pytest.raises(ValueError):
        design_pilot_identity(**partial)


def test_design_pilot_identity_rejects_unknown_dimensions() -> None:
    with pytest.raises(ValueError):
        design_pilot_identity(**dict(PILOT_FIELDS, aggregate_label=1))


def test_a_burned_pilot_identity_cannot_be_reused_officially() -> None:
    burned = {design_pilot_identity(**PILOT_FIELDS)}
    with pytest.raises(DesignPilotReuseError):
        assert_not_design_pilot_identity(PILOT_FIELDS, excluded=burned)
    official = dict(PILOT_FIELDS, study="study_a_zero_shot", split="train",
                    episode_id="episode-0", seed_identity="f" * 64)
    assert assert_not_design_pilot_identity(official, excluded=burned)


def test_exclusion_document_is_canonical_and_duplicate_free() -> None:
    document = build_exclusion_document([PILOT_FIELDS, dict(
        PILOT_FIELDS, episode_id="design-pilot/episode-1")])
    assert document["excluded_identity_count"] == 2
    assert document["permanent"] is True
    assert document["study_a_n24_identities"] == 0
    assert document["study_b_identities"] == 0
    assert document["final_test_identities"] == 0
    with pytest.raises(ValueError):
        build_exclusion_document([PILOT_FIELDS, PILOT_FIELDS])


def test_committed_exclusion_set_covers_every_pilot_episode() -> None:
    path = ROOT / "phase9d_h1r_design_pilot_exclusion_set_v1.json"
    document = json.loads(path.read_text(encoding="ascii"))
    identities = [entry["design_pilot_identity_sha256"]
                  for entry in document["excluded_identities"]]
    assert len(identities) == len(set(identities)) == \
        document["excluded_identity_count"]
    for entry in document["excluded_identities"]:
        assert entry["study"] == "study_a_design_pilot"
        assert entry["split"] == "design_pilot"
        assert entry["team_size"] in (5, 6, 8, 12, 16)
    assert document["study_a_n24_identities"] == 0
    assert document["study_b_identities"] == 0
    assert document["final_test_identities"] == 0
