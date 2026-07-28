"""Step 1.3 — `ms_per_step` measures online inference and nothing else.

Excluded from the timed region: checkpoint loading, model construction,
environment construction, result serialization, plot generation.
Included: the per-step policy call (graph construction, forward pass, topology
selection) and the runtime safety filter.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.evaluate import (
    INFERENCE_WARMUP_CALLS,
    inference_latency_stats,
    run_policy_episode,
)
from rvt_swarm.splits import episode_seed


LATENCY_KEYS = [
    "inference_latency_mean_ms",
    "inference_latency_median_ms",
    "inference_latency_p95_ms",
    "inference_latency_p99_ms",
]


def _episode(method: str = "fixed_formation_expert", n_agents: int = 4):
    return run_policy_episode(
        method, Config(), n_agents, "open_field", seed=episode_seed("test", 0, n_agents, 0)
    )


# --------------------------------------------------------------------------
# Reported statistics
# --------------------------------------------------------------------------
def test_all_latency_statistics_are_reported() -> None:
    out = _episode()
    for key in LATENCY_KEYS + ["timed_control_steps"]:
        assert key in out, f"missing {key}"
        assert np.isfinite(out[key])


def test_timed_step_count_matches_the_episode_length() -> None:
    out = _episode()
    assert out["timed_control_steps"] == out["steps"], (
        "every control step must be timed exactly once"
    )


def test_percentiles_are_ordered() -> None:
    out = _episode(n_agents=8)
    assert out["inference_latency_median_ms"] <= out["inference_latency_p95_ms"] + 1e-9
    assert out["inference_latency_p95_ms"] <= out["inference_latency_p99_ms"] + 1e-9


def test_statistics_helper_matches_numpy() -> None:
    samples = [1.0, 2.0, 3.0, 4.0, 100.0]
    stats = inference_latency_stats(samples)
    assert stats["inference_latency_mean_ms"] == pytest.approx(22.0)
    assert stats["inference_latency_median_ms"] == pytest.approx(3.0)
    assert stats["inference_latency_p95_ms"] == pytest.approx(np.percentile(samples, 95))
    assert stats["inference_latency_p99_ms"] == pytest.approx(np.percentile(samples, 99))
    assert stats["timed_control_steps"] == 5.0
    assert stats["ms_per_step"] == pytest.approx(stats["inference_latency_mean_ms"])


def test_empty_latency_list_is_handled() -> None:
    stats = inference_latency_stats([])
    assert stats["timed_control_steps"] == 0.0
    assert all(np.isnan(stats[k]) for k in LATENCY_KEYS)


# --------------------------------------------------------------------------
# The regression this test exists for
# --------------------------------------------------------------------------
def test_checkpoint_loading_is_outside_the_timed_region(monkeypatch) -> None:
    """Injecting a large, artificial checkpoint-load delay must not move latency.

    Before the fix, `ms_per_step` was wall-clock over the whole episode divided
    by the step count, so it absorbed `load_learned_model` -- which the evaluator
    called from inside the loop. A 250 ms artificial load would then have shifted
    the reported per-step latency by ~250/steps ms.
    """
    import rvt_swarm.policy_runtime as pr

    cfg = Config()
    seed = episode_seed("test", 0, 4, 1)

    class _StubModel:
        """Stands in for a learned policy without needing a checkpoint on disk."""

        def parameters(self):
            import torch

            yield torch.zeros(1)

    load_calls = {"n": 0}

    def slow_load(method, cfg_, ckpt_dir, device):
        load_calls["n"] += 1
        time.sleep(0.25)  # 250 ms, far larger than any real per-step latency
        return _StubModel()

    def fake_infer(method, obs, cfg_, model, prev_topology):
        n = len(obs["positions"])
        return {
            "actions": np.zeros((n, 2), dtype=np.float32),
            "topology": 0,
            "recoverability": None,
            "recoverability_scores": None,
            "uncertainty": None,
            "safety_stats": {"activated": 0.0},
            "outputs": {},
        }

    monkeypatch.setattr(pr, "load_learned_model", slow_load)
    monkeypatch.setattr(pr, "infer_learned_action", fake_infer)

    out = run_policy_episode("gnn_only", cfg, 4, "open_field", seed=seed)

    assert load_calls["n"] == 1, "checkpoint should be loaded exactly once, before timing"
    steps = out["timed_control_steps"]
    assert steps > 0
    # A 250 ms load spread over the episode would add ~250/steps ms per step. The
    # stub policy itself costs microseconds, so the measured mean must stay far
    # below that contamination level.
    contamination_per_step = 250.0 / steps
    assert out["inference_latency_mean_ms"] < 0.25 * contamination_per_step, (
        f"latency {out['inference_latency_mean_ms']:.4f} ms/step is contaminated by the "
        f"250 ms checkpoint load (~{contamination_per_step:.3f} ms/step if included)"
    )


def test_environment_construction_is_outside_the_timed_region(monkeypatch) -> None:
    """A slow env constructor must not inflate per-step latency either."""
    import rvt_swarm.evaluate as ev

    real_init = ev.SwarmFormationEnv.__init__

    def slow_init(self, cfg):
        time.sleep(0.20)
        real_init(self, cfg)

    monkeypatch.setattr(ev.SwarmFormationEnv, "__init__", slow_init)
    out = _episode()
    steps = out["timed_control_steps"]
    assert out["inference_latency_mean_ms"] < 0.25 * (200.0 / steps)


def test_warmup_calls_are_performed_and_not_timed(monkeypatch) -> None:
    """Warm-up calls must run, and must not appear in the timed step count."""
    import rvt_swarm.policy_runtime as pr

    calls = {"n": 0}

    class _StubModel:
        def parameters(self):
            import torch

            yield torch.zeros(1)

    def counting_infer(method, obs, cfg_, model, prev_topology):
        calls["n"] += 1
        n = len(obs["positions"])
        return {
            "actions": np.zeros((n, 2), dtype=np.float32),
            "topology": 0,
            "recoverability": None,
            "recoverability_scores": None,
            "uncertainty": None,
            "safety_stats": {"activated": 0.0},
            "outputs": {},
        }

    monkeypatch.setattr(pr, "load_learned_model", lambda *a, **k: _StubModel())
    monkeypatch.setattr(pr, "infer_learned_action", counting_infer)

    out = run_policy_episode("gnn_only", Config(), 4, "open_field", seed=episode_seed("test", 0, 4, 2))
    assert calls["n"] == out["timed_control_steps"] + INFERENCE_WARMUP_CALLS, (
        "warm-up calls must happen outside the timed step count"
    )
