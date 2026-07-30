"""Task 11 — executable guards against centralized runtime access.

Every test here comes in two halves: the clean tree is clean, AND a real
offender is caught. The first version of this guard in the project asserted
`[] == []` and stayed green when an offender was injected, so non-vacuity is
demonstrated per category rather than assumed.

Injection is done by WRITING A TEMPORARY MODULE into the package, not by
assigning into a module namespace at runtime: `guards` filters on
`__module__`, so an in-memory injection is silently skipped. That mistake was
made once during this work and is recorded here so it is not repeated.
"""

from __future__ import annotations

import contextlib
import importlib
import pathlib

import pytest

from rvt_swarm.decentralized import guards
from rvt_swarm.decentralized.system_model import (
    PROHIBITED_OBS_KEYS, CentralizedAccessError,
)

PKG = pathlib.Path(guards.__file__).parent
TMP = PKG / "_tmp_violation.py"


@contextlib.contextmanager
def injected(source: str):
    """Write an offending module into the package, then remove it."""
    TMP.write_text("from __future__ import annotations\nimport numpy as np\n" + source)
    try:
        importlib.invalidate_caches()
        yield
    finally:
        TMP.unlink(missing_ok=True)
        importlib.invalidate_caches()
        import sys
        sys.modules.pop("rvt_swarm.decentralized._tmp_violation", None)


def _kinds(violations):
    return {v.kind for v in violations}


# ---------------------------------------------------------------------------
# The clean tree
# ---------------------------------------------------------------------------
def test_clean_package_has_no_violations() -> None:
    v = guards.audit()
    assert v == [], "\n".join(str(x) for x in v)


# ---------------------------------------------------------------------------
# Non-vacuity, one offender per prohibited category
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,source,kind", [
    ("full state array",
     "def build_team_features(p_all: np.ndarray, n: int):\n    return p_all.mean(0)\n",
     "bulk-annotation"),
    ("global graph builder",
     "def build_swarm_graph(all_positions):\n    return all_positions\n",
     "bulk-name"),
    ("global centroid utility",
     "def swarm_centroid(team_state):\n    return team_state\n",
     "bulk-name"),
    ("joint action generation",
     "def joint_actions(joint_state):\n    return joint_state\n",
     "bulk-name"),
    ("global min distance",
     "def global_min_distance(all_poses):\n    return min(all_poses)\n",
     "bulk-name"),
    ("torch tensor of everything",
     "import torch\ndef score_team(batch: torch.Tensor):\n    return batch\n",
     "bulk-annotation"),
])
def test_guard_catches_injected_offender(name, source, kind) -> None:
    before = guards.audit()
    with injected(source):
        after = guards.audit()
    assert len(after) > len(before), f"guard MISSED an injected offender: {name}"
    assert kind in _kinds(after), (name, _kinds(after))
    assert guards.audit() == [], "injection was not cleaned up"


def test_guard_catches_prohibited_obs_key_read() -> None:
    with injected('def read_state(view):\n    obs = {}\n    return obs["positions"]\n'):
        v = guards.audit()
    assert "prohibited-obs-key" in _kinds(v), v


def test_guard_catches_global_pooling_and_expert_action_calls() -> None:
    for call, in (("pooled_graph_features(h, b)",), ("expert_action(obs, cfg, 0)",)):
        with injected(f"def score_all(view):\n    return {call}\n"):
            v = guards.audit()
        assert "forbidden-call" in _kinds(v), (call, v)


def test_guard_catches_a_boundary_call_inside_a_control_loop() -> None:
    with injected("def control_step(view):\n    return simulate_broadcast_round(view)\n"):
        v = guards.audit()
    assert "boundary-in-loop" in _kinds(v), v


# ---------------------------------------------------------------------------
# strict_decentralized_runtime
# ---------------------------------------------------------------------------
def test_strict_mode_is_enabled_by_default() -> None:
    assert guards.strict_enabled() is True


def test_strict_mode_rejects_the_global_observation_dict() -> None:
    guards.set_strict(True)
    with pytest.raises(CentralizedAccessError):
        guards.assert_local_only({"positions": [[0, 0]], "goal": [1, 1]})
    with pytest.raises(CentralizedAccessError):
        guards.forbid_global("swarm_centroid")


def test_strict_mode_can_be_disabled_and_then_permits_access() -> None:
    try:
        guards.set_strict(False)
        guards.assert_local_only({"positions": [[0, 0]]})   # must not raise
        guards.forbid_global("swarm_centroid")              # must not raise
    finally:
        guards.set_strict(True)
    assert guards.strict_enabled() is True


def test_every_prohibited_obs_key_is_actually_rejected() -> None:
    guards.set_strict(True)
    for key in PROHIBITED_OBS_KEYS:
        with pytest.raises(CentralizedAccessError):
            guards.assert_local_only({key: object()})


def test_a_purely_local_payload_is_accepted() -> None:
    """Non-vacuity for the strict check itself: it must not reject everything."""
    guards.set_strict(True)
    guards.assert_local_only({"goal": (1.0, 0.0), "corridor_dx": 1.0})


# ---------------------------------------------------------------------------
# Final-test isolation
# ---------------------------------------------------------------------------
def test_no_final_test_layout_access_anywhere_in_the_decentralized_package() -> None:
    offenders = []
    for path in list(PKG.glob("*.py")) + list(
            (PKG.parent.parent / "tests").glob("test_*decentral*.py")) + list(
            (PKG.parent.parent / "tests").glob("test_ego_graph*.py")) + list(
            (PKG.parent.parent / "tests").glob("test_neighbour*.py")) + list(
            (PKG.parent.parent / "tests").glob("test_leaderless*.py")):
        src = path.read_text()
        if 'build_layouts("test")' in src or "build_layouts('test')" in src:
            offenders.append(str(path))
    assert offenders == [], offenders
