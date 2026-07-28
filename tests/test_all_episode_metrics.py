"""Task 1 — every episode metric has the semantics declared in the specification.

Reference: docs/EPISODE_METRIC_SPECIFICATION.md
Implementation: rvt_swarm/metrics.py

Most assertions run against `EpisodeAccumulator` directly with synthetic step
dicts, so each semantics class (A/B/C/D/E/F/G/H) is exercised in isolation and
cannot pass by accident of the dynamics.
"""

from __future__ import annotations

import math

import pytest

from rvt_swarm.config import Config
from rvt_swarm.metrics import EVALUATION_SCHEMA_VERSION, EpisodeAccumulator


def _info(**overrides) -> dict:
    """A clean, neutral step; override only what a test is about."""
    base = dict(
        goal_reached=0.0,
        collision_free=1.0,
        rr_collision=0.0,
        ro_collision=0.0,
        min_rr_clearance=1.0,
        min_ro_clearance=1.0,
        form_ok=1.0,
        form_rms=0.1,
        deadlock=0.0,
        irreversible_collapse=0.0,
        success=0.0,
        goal_distance=5.0,
        topology_switches=0.0,
    )
    base.update(overrides)
    return base


def _run(infos, shield_flags=None) -> dict:
    acc = EpisodeAccumulator(formation_tolerance=0.55, dt=0.15)
    shield_flags = shield_flags or [False] * len(infos)
    for info, flag in zip(infos, shield_flags):
        acc.update(info, shield_activated=flag)
    return acc.finalize(infos[-1])


# --------------------------------------------------------------------------
# B — episode-wide conjunction
# --------------------------------------------------------------------------
def test_collision_free_is_a_conjunction() -> None:
    out = _run([_info(), _info(collision_free=0.0, rr_collision=0.5), _info()])
    assert out["collision_free"] == 0.0
    assert out["collision_free_terminal"] == 1.0


def test_collision_free_true_only_when_every_step_is_clean() -> None:
    assert _run([_info(), _info(), _info()])["collision_free"] == 1.0


def test_success_is_conjunctive_over_the_corrected_terms() -> None:
    infos = [_info(), _info(collision_free=0.0), _info(goal_reached=1.0, form_ok=1.0)]
    out = _run(infos)
    assert out["goal_reached"] == 1.0
    assert out["collision_free"] == 0.0
    assert out["success"] == 0.0, "a colliding episode must never be a success"


# --------------------------------------------------------------------------
# C — event latches
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", ["goal_reached", "deadlock", "irreversible_collapse"])
def test_latched_metrics_survive_a_clean_terminal_step(key: str) -> None:
    """Occurred-at-any-step must not be erased by a clean final step."""
    out = _run([_info(), _info(**{key: 1.0}), _info()])
    assert out[key] == 1.0, f"{key} must latch"
    assert out[f"{key}_terminal"] == 0.0, f"{key}_terminal must retain the old semantics"


def test_latches_stay_false_when_the_event_never_occurs() -> None:
    out = _run([_info(), _info(), _info()])
    assert out["deadlock"] == 0.0
    assert out["irreversible_collapse"] == 0.0
    assert out["goal_reached"] == 0.0


# --------------------------------------------------------------------------
# D — counts
# --------------------------------------------------------------------------
def test_collision_step_counts() -> None:
    out = _run([
        _info(rr_collision=0.5, collision_free=0.0),
        _info(),
        _info(ro_collision=0.25, collision_free=0.0),
        _info(rr_collision=0.1, ro_collision=0.1, collision_free=0.0),
    ])
    assert out["robot_robot_collision_steps"] == 2.0
    assert out["robot_obstacle_collision_steps"] == 2.0


def test_safety_filter_activation_count_and_rate() -> None:
    out = _run([_info()] * 4, shield_flags=[False, True, True, False])
    assert out["safety_filter_activations"] == 2.0
    assert out["safety_filter_activation_rate"] == pytest.approx(0.5)


# --------------------------------------------------------------------------
# E — episode-wide extrema
# --------------------------------------------------------------------------
def test_minimum_clearances_are_episode_minima() -> None:
    out = _run([
        _info(min_rr_clearance=0.9, min_ro_clearance=1.2),
        _info(min_rr_clearance=0.41, min_ro_clearance=0.7),
        _info(min_rr_clearance=0.8, min_ro_clearance=1.1),
    ])
    assert out["min_rr_clearance"] == pytest.approx(0.41)
    assert out["min_ro_clearance"] == pytest.approx(0.7)


def test_formation_error_maximum_is_an_episode_maximum() -> None:
    out = _run([_info(form_rms=0.1), _info(form_rms=0.9), _info(form_rms=0.2)])
    assert out["form_rms_max"] == pytest.approx(0.9)
    assert out["form_rms"] == pytest.approx(0.2), "terminal value must be preserved"


# --------------------------------------------------------------------------
# F / G — time averages and percentage of episode time
# --------------------------------------------------------------------------
def test_formation_error_mean_is_a_time_average() -> None:
    out = _run([_info(form_rms=0.0), _info(form_rms=1.0), _info(form_rms=0.5)])
    assert out["form_rms_mean"] == pytest.approx(0.5)


def test_time_in_formation_tube_is_a_fraction_of_episode_time() -> None:
    out = _run([_info(form_ok=1.0), _info(form_ok=0.0), _info(form_ok=0.0), _info(form_ok=1.0)])
    assert out["time_in_formation_tube"] == pytest.approx(0.5)
    assert out["form_ok"] == 1.0, "terminal flag is deliberately preserved"


def test_stall_rate_is_a_time_average_of_no_progress_steps() -> None:
    # distances: 5 -> 4 (progress) -> 4 (stall) -> 3 (progress) -> 3.5 (stall)
    out = _run([
        _info(goal_distance=5.0),
        _info(goal_distance=4.0),
        _info(goal_distance=4.0),
        _info(goal_distance=3.0),
        _info(goal_distance=3.5),
    ])
    assert out["stall_rate"] == pytest.approx(2.0 / 5.0)


# --------------------------------------------------------------------------
# H — first-passage time
# --------------------------------------------------------------------------
def test_completion_time_is_first_passage_not_episode_length() -> None:
    out = _run([_info(), _info(), _info(goal_reached=1.0), _info(goal_reached=1.0)])
    assert out["first_goal_step"] == 3.0
    assert out["completion_time"] == pytest.approx(3 * 0.15)
    assert out["completion_time_censored"] == 0.0
    assert out["steps"] == 4.0, "episode length is still reported separately"


def test_completion_time_is_censored_when_the_goal_is_never_reached() -> None:
    out = _run([_info(), _info(), _info()])
    assert math.isnan(out["completion_time"])
    assert out["completion_time_censored"] == 1.0


# --------------------------------------------------------------------------
# Schema + integration
# --------------------------------------------------------------------------
def test_every_result_carries_the_schema_version() -> None:
    assert _run([_info()])["evaluation_schema_version"] == float(EVALUATION_SCHEMA_VERSION)


def test_integration_real_episode_exposes_the_full_metric_set() -> None:
    """The evaluator must actually emit every specified key."""
    from rvt_swarm.evaluate import run_policy_episode
    from rvt_swarm.splits import episode_seed

    seed = episode_seed("test", 0, 4, 0)
    out = run_policy_episode("adaptive_formation", Config(), 4, "open_field", seed=seed)

    required = [
        "goal_reached", "goal_reached_terminal",
        "collision_free", "collision_free_terminal",
        "rr_collision", "ro_collision",
        "robot_robot_collision_steps", "robot_obstacle_collision_steps",
        "min_rr_clearance", "min_ro_clearance",
        "form_ok", "time_in_formation_tube", "form_rms", "form_rms_mean", "form_rms_max",
        "deadlock", "deadlock_terminal", "stall_rate", "stall_rate_terminal",
        "irreversible_collapse", "irreversible_collapse_terminal",
        "success", "success_terminal",
        "completion_time", "completion_time_censored", "first_goal_step",
        "topology_switches",
        "safety_filter_activations", "safety_filter_activation_rate",
        "evaluation_schema_version",
    ]
    missing = [k for k in required if k not in out]
    assert not missing, f"evaluator does not emit: {missing}"


def test_clearances_are_finite_for_a_real_multi_robot_episode() -> None:
    from rvt_swarm.evaluate import run_policy_episode
    from rvt_swarm.splits import episode_seed

    out = run_policy_episode(
        "adaptive_formation", Config(), 8, "cluttered", seed=episode_seed("test", 1, 8, 0)
    )
    assert math.isfinite(out["min_rr_clearance"])
    assert math.isfinite(out["min_ro_clearance"])
    assert out["min_rr_clearance"] > 0.0
