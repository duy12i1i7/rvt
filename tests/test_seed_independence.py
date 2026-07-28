"""Task 3 — seed roles are independent.

Episode identity is compared by SHA-256 signature over initial states, goals,
obstacles, and obstacle velocities (`splits.episode_signature`), so "the same
episodes" is proven rather than assumed.
"""

from __future__ import annotations

from dataclasses import replace

from rvt_swarm.config import Config, SeedConfig
from rvt_swarm.environment import SwarmFormationEnv
from rvt_swarm.evaluate import _setting_episode_seeds
from rvt_swarm.splits import (
    TEST,
    VALIDATION,
    episode_signature,
    split_episode_signatures,
)


def _cfg(**seed_overrides) -> Config:
    cfg = Config()
    cfg.seeds = replace(SeedConfig(), **seed_overrides)
    return cfg


def _test_signatures(cfg: Config, episodes: int = 2) -> dict:
    """Signatures of a small slice of the final test split."""
    sigs = {}
    for scenario_idx, scenario in enumerate(cfg.env.scenarios):
        for n_agents in (4, 8):
            for seed in _setting_episode_seeds(cfg, scenario_idx, n_agents, episodes, split=TEST):
                obs = SwarmFormationEnv(cfg).reset(n_agents, scenario, seed=seed)
                sigs[f"{scenario}/{n_agents}/{seed}"] = episode_signature(obs)
    return sigs


# --------------------------------------------------------------------------
# Independence
# --------------------------------------------------------------------------
def test_changing_model_seed_does_not_change_final_test_episodes() -> None:
    a = _test_signatures(_cfg(model_seed=0))
    b = _test_signatures(_cfg(model_seed=7))
    assert a == b, "final test episodes must not depend on model initialisation"


def test_changing_training_data_seed_does_not_change_final_test_episodes() -> None:
    a = _test_signatures(_cfg(training_data_seed=0))
    b = _test_signatures(_cfg(training_data_seed=99))
    assert a == b


def test_changing_validation_seed_does_not_change_final_test_episodes() -> None:
    a = _test_signatures(_cfg(validation_seed=0))
    b = _test_signatures(_cfg(validation_seed=3))
    assert a == b


def test_changing_final_test_seed_does_change_final_test_episodes() -> None:
    a = _test_signatures(_cfg(final_test_seed=0))
    b = _test_signatures(_cfg(final_test_seed=1))
    assert set(a) != set(b) or any(a[k] != b.get(k) for k in a), (
        "final_test_seed must actually re-draw the test set"
    )


def test_changing_final_test_seed_does_not_change_model_initialisation() -> None:
    """Model init depends on model_seed alone."""
    import torch

    from rvt_swarm.models import build_model
    from rvt_swarm.utils import set_seed

    def first_weights(cfg: Config):
        set_seed(cfg.seed_config().model_seed)
        model = build_model("gnn_only", cfg.train.hidden_dim, cfg.train.message_passes)
        return torch.cat([p.detach().flatten()[:8] for p in model.parameters()][:4])

    a = first_weights(_cfg(model_seed=5, final_test_seed=0))
    b = first_weights(_cfg(model_seed=5, final_test_seed=42))
    assert torch.allclose(a, b), "model init must not depend on final_test_seed"

    c = first_weights(_cfg(model_seed=6, final_test_seed=0))
    assert not torch.allclose(a, c), "model_seed must actually change initialisation"


# --------------------------------------------------------------------------
# Matching across methods and training seeds
# --------------------------------------------------------------------------
def test_all_methods_receive_identical_test_episodes() -> None:
    """Episodes are a property of the split and seed, never of the method.

    Episode construction takes no method argument, so this is verified by
    confirming that the same (scenario, N, seed) triple yields the same signature
    on repeated construction, which is what every method's evaluation loop does.
    """
    cfg = _cfg()
    first = _test_signatures(cfg)
    second = _test_signatures(cfg)
    assert first == second and len(first) > 0


def test_all_training_seeds_share_one_final_test_set() -> None:
    """The multi-seed protocol varies model_seed only."""
    signatures = [_test_signatures(_cfg(model_seed=s)) for s in range(5)]
    reference = signatures[0]
    for idx, sig in enumerate(signatures[1:], start=1):
        assert sig == reference, f"training seed {idx} saw a different test set"


def test_validation_and_test_signatures_never_collide() -> None:
    cfg = _cfg()
    val = set(split_episode_signatures(cfg, VALIDATION, episodes_per_setting=1).values())
    test = set(split_episode_signatures(cfg, TEST, episodes_per_setting=1).values())
    assert val and test
    assert not (val & test), "a validation episode is byte-identical to a test episode"


def test_signature_is_sensitive_to_every_initial_condition() -> None:
    """Guard: a signature that ignored a field would make the tests above vacuous."""
    cfg = _cfg()
    env = SwarmFormationEnv(cfg)
    obs = env.reset(4, "cluttered", seed=30_000_400)
    base = episode_signature(obs)
    for key in ("positions", "velocities", "goal", "obstacles", "obstacle_velocities"):
        perturbed = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in obs.items()}
        arr = perturbed[key]
        if getattr(arr, "size", 0) == 0:
            continue
        arr = arr.astype(float).copy()
        arr.reshape(-1)[0] += 0.01
        perturbed[key] = arr
        assert episode_signature(perturbed) != base, f"signature ignores {key}"
