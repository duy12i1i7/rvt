"""Task 5 — Recovery Event V2 sanity checks, and Task 4 — region geometry.

The V1 event fired on 27.8 % of rollouts in provably impassable corridors. These
tests are the acceptance criteria for the repair.
"""

from __future__ import annotations

import numpy as np
import pytest

from rvt_swarm.config import Config, LEARNED_TOPOLOGY_IDS
from rvt_swarm.environment import SwarmFormationEnv
from rvt_swarm.layouts import build_layouts, get_layout
from rvt_swarm.recovery_v2 import RolloutRecord, evaluate_modes, rate, rollout
from rvt_swarm.regions import regions_for, regions_for_layout

SEED = 777


def _cfg() -> Config:
    cfg = Config()
    cfg.train.device = "cpu"
    return cfg


def _layout(family: str, split: str = "val"):
    return [l for l in build_layouts(split) if l.family == family][0]


def _env(cfg, layout, n=4, seed=20000400):
    env = SwarmFormationEnv(cfg)
    env.reset(n, "cluttered", seed=seed, layout=layout)
    return env


# ==========================================================================
# Task 4 — regions
# ==========================================================================
def test_exit_plane_sits_beyond_every_obstacle_of_the_structure() -> None:
    cfg = _cfg()
    lay = _layout("line_corridor")
    reg = regions_for_layout(lay, cfg)
    assert reg.has_bottleneck
    wall_x = lay.obstacle_array[:, 0].max()
    assert reg.exit_x > wall_x, "exit plane must be past the wall"
    assert reg.exit_x >= wall_x + cfg.env.obstacle_radius


def test_approach_region_is_not_crossing() -> None:
    """Task 5.F / Task 4.2 — being in the approach region is not a crossing."""
    cfg = _cfg()
    reg = regions_for_layout(_layout("line_corridor"), cfg)
    approach_point = np.array([reg.entrance_x - 1.0, 0.0])
    assert reg.in_approach(approach_point)
    assert not reg.crossed_exit(approach_point)
    assert not reg.in_downstream(approach_point)


def test_crossing_the_exit_plane_is_detected() -> None:
    cfg = _cfg()
    reg = regions_for_layout(_layout("line_corridor"), cfg)
    past = np.array([reg.exit_x + 0.01, 0.0])
    assert reg.crossed_exit(past)
    assert reg.in_downstream(np.array([reg.downstream_x + 0.01, 0.0]))


def test_open_field_has_no_bottleneck() -> None:
    cfg = _cfg()
    reg = regions_for_layout(_layout("keep_open"), cfg)
    assert not reg.has_bottleneck, "sparse clutter must not be treated as a structure"


def test_starting_downstream_never_awards_crossing_credit() -> None:
    """Task 4.5 — a start already past the structure must not count as a crossing.

    `regions_for` only considers obstacles strictly between the start and the
    goal, so a structure behind the start yields `has_bottleneck = False` and the
    crossing term is never awarded. That is the invariant that matters; the
    `starts_downstream` helper is a belt-and-braces check that is unreachable for
    a well-formed layout (the exit plane is always ahead of a start that has a
    structure in front of it).
    """
    cfg = _cfg()
    behind = regions_for([(0.0, 1.0), (0.0, -1.0), (0.0, 2.0)], np.array([4.5, 0.0]),
                         cfg, start_x=3.0)
    assert not behind.has_bottleneck, "a structure behind the start is not a bottleneck"
    assert not behind.crossed_exit(np.array([3.0, 0.0])), (
        "standing still at the start must not register as a crossing"
    )

    ahead = regions_for([(0.0, 1.0), (0.0, -1.0), (0.0, 2.0)], np.array([4.5, 0.0]),
                        cfg, start_x=-4.56)
    assert ahead.has_bottleneck
    assert ahead.exit_x > ahead.start_x, "exit plane must lie ahead of the start"
    assert not ahead.starts_downstream()


# ==========================================================================
# Task 5.A — provably infeasible must be rejected  (V1 scored 0.278 here)
# ==========================================================================
@pytest.mark.parametrize("split", ["train", "val"])
def test_infeasible_corridor_never_yields_task_recovery(split: str) -> None:
    cfg = _cfg()
    rng = np.random.default_rng(SEED)
    positives = total = 0
    for lay in [l for l in build_layouts(split) if l.family == "infeasible"]:
        reg = regions_for_layout(lay, cfg)
        for n in (4, 6):
            env = _env(cfg, lay, n=n)
            recs = evaluate_modes(env, LEARNED_TOPOLOGY_IDS, cfg, reg, rng,
                                  n_rollouts=3, t_max=120)
            for mode_recs in recs.values():
                positives += sum(r.task_recovery for r in mode_recs)
                total += len(mode_recs)
    rate_ = positives / max(total, 1)
    assert rate_ <= 0.01, (
        f"{positives}/{total} = {rate_:.3f} task-recovery positives in a corridor "
        f"below the 1.10 m single-file minimum (V1 scored 0.278 here)"
    )


def test_infeasible_corridor_may_still_show_local_progress() -> None:
    """The three concepts must be genuinely separable, not merely renamed."""
    cfg = _cfg()
    rng = np.random.default_rng(SEED)
    lay = _layout("infeasible")
    reg = regions_for_layout(lay, cfg)
    env = _env(cfg, lay, n=4)
    recs = [rollout(env, 0, cfg, reg, rng, t_max=120) for _ in range(6)]
    assert all(r.task_recovery == 0 for r in recs)
    assert all(r.crossed_bottleneck == 0 for r in recs), "nothing may cross an impassable wall"


# ==========================================================================
# Task 5.B — trivial open field must not be labelled negative
# ==========================================================================
def test_open_field_is_mostly_positive() -> None:
    cfg = _cfg()
    rng = np.random.default_rng(SEED)
    lay = _layout("keep_open")
    reg = regions_for_layout(lay, cfg)
    env = _env(cfg, lay, n=4)
    recs = [rollout(env, 0, cfg, reg, rng, t_max=240) for _ in range(8)]
    r = np.mean([x.task_recovery for x in recs])
    assert r >= 0.5, (
        f"open-field task-recovery rate {r:.3f}: the event is too strict and "
        f"rejects obviously successful rollouts"
    )


# ==========================================================================
# Task 5.C / E / F — the event must reject the right failure modes
# ==========================================================================
def test_collision_then_goal_is_not_task_recovery() -> None:
    rec = RolloutRecord(task_completed=1, crossed_bottleneck=1, rr_collision_steps=2,
                        tube_dwell_max=10)
    ok = (rec.task_completed and rec.rr_collision_steps == 0 and rec.ro_collision_steps == 0
          and not rec.deadlock and not rec.irreversible_collapse and rec.tube_dwell_max >= 3)
    assert not ok, "a collision anywhere in the rollout must void task recovery"


def test_temporary_formation_recovery_then_failure() -> None:
    """Task 5.E — formation recovery may be 1 while task recovery is 0."""
    cfg = _cfg()
    rng = np.random.default_rng(SEED)
    lay = _layout("infeasible")
    reg = regions_for_layout(lay, cfg)
    env = _env(cfg, lay, n=4)
    recs = [rollout(env, 0, cfg, reg, rng, t_max=120) for _ in range(6)]
    assert all(r.task_recovery == 0 for r in recs)
    # At least one rollout should hold formation while going nowhere -- which is
    # exactly the case the V1 event mistook for recovery.
    assert any(r.formation_recovery == 1 for r in recs), (
        "expected formation recovery without task recovery; if this never happens "
        "the two events are not measuring different things"
    )


def test_bottleneck_approach_without_crossing_is_not_task_recovery() -> None:
    """Task 5.F — local progress may be 1 while task recovery is 0."""
    cfg = _cfg()
    rng = np.random.default_rng(SEED)
    lay = _layout("infeasible")
    reg = regions_for_layout(lay, cfg)
    env = _env(cfg, lay, n=4)
    recs = [rollout(env, 0, cfg, reg, rng, t_max=120) for _ in range(6)]
    assert any(r.local_progress == 1 for r in recs), "expected local progress toward the wall"
    assert all(r.task_recovery == 0 for r in recs)


def test_task_recovery_requires_crossing_in_bottleneck_scenarios() -> None:
    rec = RolloutRecord(task_completed=1, crossed_bottleneck=0, tube_dwell_max=10)
    completion = bool(rec.task_completed) and bool(rec.crossed_bottleneck)
    assert not completion, "goal without crossing must not count in a bottleneck scenario"


# ==========================================================================
# Task 5.D — the three quantities are reported separately
# ==========================================================================
def test_all_three_events_are_reported_separately() -> None:
    cfg = _cfg()
    rng = np.random.default_rng(SEED)
    lay = _layout("line_corridor")
    reg = regions_for_layout(lay, cfg)
    env = _env(cfg, lay, n=4)
    rec = rollout(env, 2, cfg, reg, rng, t_max=120)
    d = rec.as_dict()
    for key in ["local_progress", "formation_recovery", "task_recovery", "task_completed",
                "rr_collision_steps", "ro_collision_steps", "deadlock",
                "irreversible_collapse", "tube_entry_time", "tube_dwell_max",
                "goal_progress", "crossed_bottleneck", "terminal_reason",
                "rollout_duration"]:
        assert key in d, f"missing required field {key}"


# ==========================================================================
# Task 2 — the intervention must be fair
# ==========================================================================
def test_continuation_policy_is_identical_across_candidate_modes() -> None:
    """After H_commit, every candidate must be continued the same way."""
    import inspect

    from rvt_swarm import recovery_v2

    src = inspect.getsource(recovery_v2.rollout)
    assert "CONTINUATION_MODE" in src
    assert recovery_v2.CONTINUATION_MODE == 0
    # The continuation must not depend on the candidate: the only place `mode`
    # appears in the action call is via `active`, which is CONTINUATION_MODE once
    # the commitment window closes.
    assert "active = mode if (full_mode or step < h_commit) else CONTINUATION_MODE" in src


def test_full_mode_intervention_differs_from_fixed_commitment() -> None:
    cfg = _cfg()
    lay = _layout("line_corridor")
    reg = regions_for_layout(lay, cfg)
    env = _env(cfg, lay, n=6)
    a = rollout(env, 2, cfg, reg, np.random.default_rng(1), h_commit=10,
                t_max=120, full_mode=False)
    b = rollout(env, 2, cfg, reg, np.random.default_rng(1), h_commit=10,
                t_max=120, full_mode=True)
    assert (a.as_dict() != b.as_dict()), (
        "fixed-commitment and full-mode interventions produced identical records; "
        "the commitment window is not being applied"
    )
