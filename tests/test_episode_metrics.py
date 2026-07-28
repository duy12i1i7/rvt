"""Finding 1 — is `CollisionFree` an episode-wide or a terminal-step quantity?

The manuscript defines the primary safety indicator as

    CollisionFree = 1[RRCol = 0 AND ROCol = 0]        (over the whole episode)

but `rvt_swarm.evaluate.run_policy_episode` returns `last_info`, i.e. the
metric dictionary produced by the *final* simulator step only.

Files involved
--------------
rvt_swarm/evaluate.py:32-66      episode loop; `last_info = info`; `return last_info`
rvt_swarm/environment.py:522-560 `compute_metrics()` is evaluated on the CURRENT
                                 positions and carries no episode history

These tests assert the *documented* (episode-wide) semantics, so they fail
against the unfixed code and pass once the accumulator is added.
"""

from __future__ import annotations

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.environment import SwarmFormationEnv


# Natural reproducers exist in abundance: scanning 640 baseline episodes found 363
# (56.7%) reported collision-free despite a mid-episode collision, and 286 (44.7%)
# reported as a conjunctive SUCCESS despite one. `adaptive_formation / open_field /
# N=4 / seed=45` was the canonical case (10 dirty steps of 97, clean terminal step,
# goal reached, formation in tolerance).
#
# Those reproducers are properties of the *dynamics*, so the geometry corrections
# legitimately dissolve some of them. The tests below therefore assert the
# accumulator SEMANTICS, which are dynamics-independent:
#   * a scripted episode pins the collision pattern exactly, and
#   * a sweep of real episodes asserts reported == per-step conjunction throughout.
# Both are red before the fix and green after it, and neither can pass vacuously.
SWEEP = [
    ("adaptive_formation", "open_field", 4, 45),
    ("adaptive_formation", "open_field", 4, 52),
    ("adaptive_formation", "cluttered", 6, 43),
    ("cbf_qp", "narrow_passage", 8, 42),
    ("cbf_qp", "open_field", 4, 45),
]


def _short_cfg() -> Config:
    """Keep the unit tests fast; none of these knobs affects the property tested."""
    cfg = Config()
    cfg.env.max_steps = 120
    return cfg


# --------------------------------------------------------------------------
# 1a. Controller-free demonstration: the metric has no memory.
# --------------------------------------------------------------------------
def test_compute_metrics_has_no_episode_memory() -> None:
    """Drive two robots into contact and then apart; the metric forgets the contact."""
    cfg = _short_cfg()
    env = SwarmFormationEnv(cfg)
    env.reset(2, "open_field", seed=0)
    env.state.obstacles = np.zeros((0, 2), dtype=np.float32)
    env.state.obstacle_velocities = np.zeros((0, 2), dtype=np.float32)
    env.state.velocities = np.zeros((2, 2), dtype=np.float32)

    # Step 1: overlapping -> collision.
    env.state.positions = np.array([[0.0, 0.0], [0.20, 0.0]], dtype=np.float32)
    during = env.compute_metrics()

    # Step 2: far apart -> clean.
    env.state.positions = np.array([[0.0, 0.0], [3.0, 0.0]], dtype=np.float32)
    after = env.compute_metrics()

    assert during["collision_free"] == 0.0, "contact must register as a collision"
    assert after["collision_free"] == 1.0, "separated robots must register as clean"

    # An episode consisting of these two states is NOT collision-free.
    episode_wide = min(during["collision_free"], after["collision_free"])
    assert episode_wide == 0.0
    # ...but the terminal snapshot says it is. This is the whole finding.
    assert after["collision_free"] != episode_wide


# --------------------------------------------------------------------------
# 1b. Integration: what run_policy_episode actually reports.
# --------------------------------------------------------------------------
class _RecordingEnv(SwarmFormationEnv):
    """Captures every per-step info dict so the episode can be reconstructed."""

    records: list[dict] = []

    def reset(self, *args, **kwargs):
        type(self).records = []
        return super().reset(*args, **kwargs)

    def step(self, actions, topology_action: int = 0):
        obs, reward, done, info = super().step(actions, topology_action)
        type(self).records.append(dict(info))
        return obs, reward, done, info


class _ScriptedCollisionEnv(SwarmFormationEnv):
    """Pins the safety pattern regardless of dynamics, config, or controller.

    Steps 2 and 3 report a collision; every other step is clean, the goal is
    reached, and the formation is in tolerance. So the terminal step is clean and
    terminal-success is 1, while the episode is neither collision-free nor a
    success. This isolates the accumulator from the physics.
    """

    DIRTY_STEPS = {2, 3}
    records: list[dict] = []

    def reset(self, *args, **kwargs):
        type(self).records = []
        self._scripted_step = 0
        return super().reset(*args, **kwargs)

    def step(self, actions, topology_action: int = 0):
        obs, reward, done, info = super().step(actions, topology_action)
        self._scripted_step += 1
        info = dict(info)
        info["goal_reached"] = 1.0
        info["form_ok"] = 1.0
        clean = self._scripted_step not in type(self).DIRTY_STEPS
        info["collision_free"] = 1.0 if clean else 0.0
        info["rr_collision"] = 0.0 if clean else 0.5
        info["success"] = info["collision_free"]
        type(self).records.append(dict(info))
        return obs, reward, done, info


@pytest.fixture()
def scripted_episode(monkeypatch):
    """Run the scripted episode and return (reported_metrics, per_step_records)."""
    import rvt_swarm.evaluate as ev

    monkeypatch.setattr(ev, "SwarmFormationEnv", _ScriptedCollisionEnv)
    cfg = _short_cfg()
    cfg.env.max_steps = 12  # keep it fast; the pattern is what matters
    reported = ev.run_policy_episode("adaptive_formation", cfg, 4, "open_field", seed=45)
    return reported, list(_ScriptedCollisionEnv.records)


def test_scripted_episode_is_a_valid_non_vacuous_probe(scripted_episode) -> None:
    """Guard: the script must actually produce a dirty-middle / clean-end episode."""
    _, records = scripted_episode
    assert len(records) >= 4
    assert any(r["collision_free"] < 0.5 for r in records), "no collision was scripted"
    assert records[-1]["collision_free"] == 1.0, "terminal step must be clean"
    assert records[-1]["success"] == 1.0, "terminal step must look like a success"


def test_reported_collision_free_is_episode_wide(scripted_episode) -> None:
    """The reported value must reflect the whole episode, not the last step."""
    reported, records = scripted_episode
    episode_wide = float(all(r["collision_free"] > 0.5 for r in records))

    assert episode_wide == 0.0  # by construction
    assert reported["collision_free"] == pytest.approx(episode_wide), (
        f"reported collision_free={reported['collision_free']} but the episode-wide "
        f"value is {episode_wide} "
        f"({sum(r['collision_free'] < 0.5 for r in records)}/{len(records)} steps had a collision)"
    )


def test_reported_success_uses_episode_wide_collision_free(scripted_episode) -> None:
    """Success is conjunctive, so it inherits the corrected safety term."""
    reported, records = scripted_episode
    assert records[-1]["success"] == 1.0  # terminal snapshot says success
    assert reported["success"] == 0.0, (
        "an episode containing a collision must not be reported as a success"
    )


def test_terminal_values_are_still_available_for_comparison(scripted_episode) -> None:
    """The fix must preserve the old quantities under explicit names, not delete them."""
    reported, records = scripted_episode
    assert "collision_free_terminal" in reported, (
        "the pre-fix terminal-step value should remain available for auditing"
    )
    assert reported["collision_free_terminal"] == pytest.approx(records[-1]["collision_free"])
    assert reported["success_terminal"] == pytest.approx(records[-1]["success"])


@pytest.mark.parametrize("method,scenario,n_agents,seed", SWEEP)
def test_reported_metrics_match_per_step_conjunction(
    monkeypatch, method: str, scenario: str, n_agents: int, seed: int
) -> None:
    """Consistency over real episodes, whether or not they happen to collide."""
    import rvt_swarm.evaluate as ev

    monkeypatch.setattr(ev, "SwarmFormationEnv", _RecordingEnv)
    reported = ev.run_policy_episode(method, _short_cfg(), n_agents, scenario, seed=seed)
    records = list(_RecordingEnv.records)

    episode_wide = float(all(r["collision_free"] > 0.5 for r in records))
    assert reported["collision_free"] == pytest.approx(episode_wide), (
        f"{method}/{scenario}/N={n_agents}/seed={seed}: reported "
        f"{reported['collision_free']} vs episode-wide {episode_wide} "
        f"({sum(r['collision_free'] < 0.5 for r in records)}/{len(records)} dirty steps)"
    )
    expected_success = float(
        reported["goal_reached"] > 0.5 and episode_wide > 0.5 and reported["form_ok"] > 0.5
    )
    assert reported["success"] == pytest.approx(expected_success)
