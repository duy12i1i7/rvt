"""Task 1 — the simplified model does not contain, use, or depend on the removed components.

Removed on Method-Audit-v2 evidence: uncertainty head and adjustment, auxiliary
head, topology-classification head (kept only as a separate baseline model),
lower-bound loss, multi-level lexicographic selector, and the hard-negative
action-label perturbation.
"""

from __future__ import annotations

import torch

from rvt_swarm.config import Config
from rvt_swarm.dataset import collate_graphs, generate_dataset
from rvt_swarm.models import build_model
from rvt_swarm.train import compute_loss

VARIANTS = ["gnn_topology_agnostic", "rvt_full_legacy", "rvt_simple_rank",
            "direct_topology_classifier"]
LOSS_KEY = {"gnn_topology_agnostic": "gnn_only", "rvt_full_legacy": "rvt_swarm"}


def _cfg() -> Config:
    cfg = Config()
    cfg.train.n_workers = 1
    cfg.env.team_sizes = [4]
    cfg.env.scenarios = ["open_field"]
    return cfg


def _batch(cfg, n=8):
    ds = generate_dataset(cfg, episodes=1)
    return collate_graphs([ds[i] for i in range(min(n, len(ds)))])


def _forward(name, model, batch):
    at = batch["topology_target"] if name != "gnn_topology_agnostic" else None
    return model(batch, action_topology=at) if at is not None else model(batch)


# --------------------------------------------------------------------------
# The variants exist and are distinct
# --------------------------------------------------------------------------
def test_all_named_variants_build() -> None:
    for name in VARIANTS:
        assert build_model(name) is not None


def test_fixed_keep_policy_is_not_a_learned_model() -> None:
    import pytest

    with pytest.raises(ValueError, match="non-learned baseline"):
        build_model("fixed_keep_policy")


def test_legacy_implementation_is_untouched() -> None:
    """`rvt_full_legacy` must still be the original five-head model."""
    m = build_model("rvt_full_legacy")
    for head in ("uncertainty_head", "aux_head", "topology_consensus", "topology_refine"):
        assert hasattr(m, head), f"legacy model lost {head}"


# --------------------------------------------------------------------------
# The simplified model does not contain the removed modules
# --------------------------------------------------------------------------
def test_simplified_model_has_no_removed_heads() -> None:
    m = build_model("rvt_simple_rank")
    for head in ("uncertainty_head", "aux_head", "topology_consensus", "topology_refine"):
        assert not hasattr(m, head), f"rvt_simple_rank still defines {head}"
    assert hasattr(m, "score_head")
    assert hasattr(m, "base_action_head")


def test_simplified_model_emits_no_removed_outputs() -> None:
    cfg = _cfg()
    batch = _batch(cfg)
    out = _forward("rvt_simple_rank", build_model("rvt_simple_rank"), batch)
    for key in ("uncertainty", "aux", "topology_logits"):
        assert out[key] is None, f"rvt_simple_rank still produces {key}"
    assert out["recoverability_scores"] is not None


def test_simplified_model_score_is_not_uncertainty_adjusted() -> None:
    """`recoverability_scores` and the raw head must be the identical tensor."""
    cfg = _cfg()
    out = _forward("rvt_simple_rank", build_model("rvt_simple_rank"), _batch(cfg))
    assert torch.equal(out["recoverability_scores"], out["raw_recoverability_scores"])


def test_simplified_model_has_fewer_parameters_than_legacy() -> None:
    p_simple = sum(p.numel() for p in build_model("rvt_simple_rank").parameters())
    p_legacy = sum(p.numel() for p in build_model("rvt_full_legacy").parameters())
    assert p_simple < p_legacy, f"{p_simple} !< {p_legacy}"


# --------------------------------------------------------------------------
# The simplified loss has exactly the specified terms
# --------------------------------------------------------------------------
def test_simplified_loss_is_action_plus_rank_only() -> None:
    cfg = _cfg()
    batch = _batch(cfg)
    out = _forward("rvt_simple_rank", build_model("rvt_simple_rank"), batch)
    losses = compute_loss(out, batch, "rvt_simple_rank", cfg)

    for removed in ("lower_bound", "aux", "uncertainty", "topology", "recover"):
        assert float(losses[removed]) == 0.0, f"{removed} is still contributing"
    expected = float(losses["action"]) + cfg.audit.lambda_rank * float(losses["rank"])
    assert abs(float(losses["total"]) - expected) < 1e-6


def test_score_term_is_off_by_default_and_separable() -> None:
    cfg = _cfg()
    batch = _batch(cfg)
    model = build_model("rvt_simple_rank")

    out = _forward("rvt_simple_rank", model, batch)
    base = float(compute_loss(out, batch, "rvt_simple_rank", cfg)["total"])

    cfg.audit.lambda_score = 0.5
    out2 = _forward("rvt_simple_rank", model, batch)
    losses2 = compute_loss(out2, batch, "rvt_simple_rank", cfg)
    assert float(losses2["total"]) > base, "lambda_score had no effect when enabled"
    assert abs(float(losses2["total"]) - (base + 0.5 * float(losses2["score_map"]))) < 1e-5


def test_lambda_rank_scales_only_the_ranking_term() -> None:
    cfg = _cfg()
    batch = _batch(cfg)
    model = build_model("rvt_simple_rank")
    out = _forward("rvt_simple_rank", model, batch)
    a = compute_loss(out, batch, "rvt_simple_rank", cfg)
    cfg.audit.lambda_rank = 2.0
    b = compute_loss(out, batch, "rvt_simple_rank", cfg)
    assert abs(float(b["total"]) - (float(a["action"]) + 2.0 * float(a["rank"]))) < 1e-6


# --------------------------------------------------------------------------
# Removed components cannot influence the simplified model
# --------------------------------------------------------------------------
def test_uncertainty_toggle_cannot_change_simplified_inference() -> None:
    """`use_uncertainty_adjustment` is a no-op for a model with no uncertainty head."""
    from rvt_swarm.policy_runtime import infer_learned_action
    from rvt_swarm.environment import SwarmFormationEnv
    from rvt_swarm.splits import episode_seed

    cfg = _cfg()
    model = build_model("rvt_simple_rank")
    obs = SwarmFormationEnv(cfg).reset(4, "open_field", seed=episode_seed("validation", 0, 4, 0))

    cfg.audit.use_uncertainty_adjustment = True
    a = infer_learned_action("rvt_simple_rank", obs, cfg, model, 0)
    cfg.audit.use_uncertainty_adjustment = False
    b = infer_learned_action("rvt_simple_rank", obs, cfg, model, 0)

    assert a["topology"] == b["topology"]
    assert torch.allclose(torch.tensor(a["actions"]), torch.tensor(b["actions"]))


def test_selector_variants_cannot_change_simplified_inference() -> None:
    """The lexicographic selector and its tie-breaks are bypassed entirely."""
    from rvt_swarm.policy_runtime import infer_learned_action
    from rvt_swarm.environment import SwarmFormationEnv
    from rvt_swarm.splits import episode_seed

    cfg = _cfg()
    model = build_model("rvt_simple_rank")
    obs = SwarmFormationEnv(cfg).reset(4, "open_field", seed=episode_seed("validation", 0, 4, 1))

    ref = infer_learned_action("rvt_simple_rank", obs, cfg, model, 0)
    for mode in ("lexicographic", "logits_argmax", "score_argmax"):
        cfg.audit.selector_mode = mode
        got = infer_learned_action("rvt_simple_rank", obs, cfg, model, 0)
        assert got["topology"] == ref["topology"], f"selector_mode={mode} changed the choice"
    for dwell in (0, 5, 10):
        cfg.audit.min_dwell_steps = dwell
        assert infer_learned_action("rvt_simple_rank", obs, cfg, model, 0)["topology"] == ref["topology"]


def test_simplified_selection_is_plain_argmax_over_the_score() -> None:
    from rvt_swarm.config import LEARNED_TOPOLOGY_IDS
    from rvt_swarm.policy_runtime import infer_learned_action
    from rvt_swarm.environment import SwarmFormationEnv
    from rvt_swarm.splits import episode_seed

    cfg = _cfg()
    model = build_model("rvt_simple_rank")
    for ep in range(4):
        obs = SwarmFormationEnv(cfg).reset(4, "open_field",
                                           seed=episode_seed("validation", 0, 4, ep))
        rt = infer_learned_action("rvt_simple_rank", obs, cfg, model, 0)
        scores = rt["recoverability_scores"]
        assert rt["topology"] == LEARNED_TOPOLOGY_IDS[int(scores.argmax())]


def test_hard_negative_mining_can_be_disabled() -> None:
    cfg_on = _cfg()
    cfg_off = _cfg()
    cfg_off.audit.use_hard_negative_mining = False
    n_on = len(generate_dataset(cfg_on, episodes=2))
    n_off = len(generate_dataset(cfg_off, episodes=2))
    assert n_off <= n_on, "disabling hard negatives should not add samples"
