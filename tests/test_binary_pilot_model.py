"""Task 2 and Task 6 — the pilot model contains only what it should, and
checkpoint directories cannot be written by two processes at once.
"""

from __future__ import annotations

import os
from multiprocessing import get_context

import pytest
import torch

from rvt_swarm.config import Config
from rvt_swarm.dataset import collate_graphs, generate_dataset
from rvt_swarm.models import BINARY_MODES, build_model
from rvt_swarm.writer_lock import (
    CheckpointWriterConflict,
    CheckpointWriterLock,
    verify_single_writer,
)


def _cfg() -> Config:
    cfg = Config()
    cfg.train.n_workers = 1
    cfg.env.team_sizes = [4]
    cfg.env.scenarios = ["open_field"]
    return cfg


@pytest.fixture(scope="module")
def batch():
    cfg = Config()
    cfg.train.n_workers = 1
    cfg.env.team_sizes = [4]
    cfg.env.scenarios = ["open_field"]
    ds = generate_dataset(cfg, episodes=1)
    return collate_graphs([ds[i] for i in range(8)])


# ==========================================================================
# The model is binary and contains nothing that was removed
# ==========================================================================
def test_mode_set_is_binary_keep_line() -> None:
    assert BINARY_MODES == (0, 2), "pilot must use keep and line only"
    m = build_model("rvt_binary_recovery")
    assert m.topology_count == 2


def test_split_cannot_be_produced(batch) -> None:
    out = build_model("rvt_binary_recovery")(batch)
    assert out["recovery_probs"].shape[-1] == 2, "a third mode output exists"
    assert out["actions_by_topology"].shape[1] == 2, "a third action slice exists"


def test_removed_heads_are_absent() -> None:
    m = build_model("rvt_binary_recovery")
    for head in ("uncertainty_head", "aux_head", "topology_consensus",
                 "topology_refine", "score_head", "topology_delta_head"):
        assert not hasattr(m, head), f"pilot model still defines {head}"
    for head in ("backbone", "base_action_head", "mode_action_head", "recovery_head"):
        assert hasattr(m, head), f"pilot model is missing {head}"


def test_removed_outputs_are_none(batch) -> None:
    out = build_model("rvt_binary_recovery")(batch)
    for key in ("uncertainty", "aux", "topology_logits"):
        assert out[key] is None, f"pilot model still produces {key}"


def test_recovery_outputs_are_probabilities(batch) -> None:
    out = build_model("rvt_binary_recovery")(batch)
    p = out["recovery_probs"]
    assert torch.all(p >= 0.0) and torch.all(p <= 1.0)
    # Two INDEPENDENT heads: they must not be constrained to sum to one.
    assert not torch.allclose(p.sum(dim=-1), torch.ones(p.shape[0]), atol=1e-3), (
        "recovery probabilities look like a softmax; they must be independent sigmoids"
    )


def test_inference_rule_is_argmax_over_recovery_probability(batch) -> None:
    model = build_model("rvt_binary_recovery")
    out = model(batch)
    expected = torch.argmax(out["recovery_probs"], dim=-1)
    chosen = out["actions_by_topology"][
        torch.arange(out["actions"].shape[0]), expected[batch["batch_index"]]]
    assert torch.allclose(out["actions"], chosen)


def test_selector_and_uncertainty_knobs_cannot_affect_the_pilot_model(batch) -> None:
    """The removed selector machinery must be unreachable, not merely unused."""
    model = build_model("rvt_binary_recovery")
    ref = model(batch)["recovery_probs"].clone()
    cfg = _cfg()
    for mode in ("lexicographic", "logits_argmax", "score_argmax", "fixed"):
        cfg.audit.selector_mode = mode
        assert torch.allclose(model(batch)["recovery_probs"], ref)
    cfg.audit.use_uncertainty_adjustment = False
    assert torch.allclose(model(batch)["recovery_probs"], ref)


def test_classifier_baseline_shares_the_trunk_but_uses_a_softmax(batch) -> None:
    a = build_model("rvt_binary_recovery")
    b = build_model("direct_keep_line_classifier")
    assert sum(p.numel() for p in a.parameters()) == sum(p.numel() for p in b.parameters())
    out = b(batch)
    assert "class_logits" in out
    assert torch.allclose(out["recovery_probs"].sum(dim=-1),
                          torch.ones(out["recovery_probs"].shape[0]), atol=1e-5), (
        "the classifier baseline must be a softmax over {keep, line}"
    )


# ==========================================================================
# Task 6 — checkpoint writer exclusivity
# ==========================================================================
def test_lock_is_acquired_and_released(tmp_path) -> None:
    lock = CheckpointWriterLock(tmp_path / "seed_0")
    with lock:
        assert (tmp_path / "seed_0" / ".writer.lock").exists()
    assert not (tmp_path / "seed_0" / ".writer.lock").exists()


def _child_try_lock(directory, q):
    from rvt_swarm.writer_lock import CheckpointWriterConflict, CheckpointWriterLock
    try:
        CheckpointWriterLock(directory).acquire()
        q.put("acquired")
    except CheckpointWriterConflict:
        q.put("conflict")
    except Exception as exc:  # pragma: no cover
        q.put(f"error:{exc}")


def test_second_live_process_is_refused(tmp_path) -> None:
    """The exact failure that corrupted the method-audit checkpoints."""
    d = tmp_path / "seed_0"
    holder = CheckpointWriterLock(d).acquire()
    try:
        ctx = get_context("spawn")
        q = ctx.Queue()
        p = ctx.Process(target=_child_try_lock, args=(str(d), q))
        p.start()
        result = q.get(timeout=60)
        p.join(timeout=60)
        assert result == "conflict", f"a second process was allowed in: {result}"
    finally:
        holder.release()


def test_stale_lock_from_a_dead_process_is_reclaimed(tmp_path) -> None:
    import json

    d = tmp_path / "seed_1"
    d.mkdir(parents=True)
    (d / ".writer.lock").write_text(json.dumps(
        {"pid": 999_999_999, "token": "dead", "time": 0.0}))
    with CheckpointWriterLock(d) as lock:
        assert lock.token != "dead"


def test_verify_single_writer_detects_mixed_tokens(tmp_path) -> None:
    d = tmp_path / "mixed"
    d.mkdir(parents=True)
    torch.save({"model": {}, "writer_token": "aaaa"}, d / "m1.pt")
    torch.save({"model": {}, "writer_token": "bbbb"}, d / "m2.pt")
    report = verify_single_writer(d)
    assert not report["single_writer"]
    assert len(report["distinct_tokens"]) == 2

    clean = tmp_path / "clean"
    clean.mkdir(parents=True)
    torch.save({"model": {}, "writer_token": "aaaa"}, clean / "m1.pt")
    torch.save({"model": {}, "writer_token": "aaaa"}, clean / "m2.pt")
    assert verify_single_writer(clean)["single_writer"]
