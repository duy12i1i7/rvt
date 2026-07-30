"""Seed-0 dry run for the fully decentralized keep/line selectors (Tasks 12-13).

    python scripts/train_decentralized_selector.py

Trains `decentralized_direct_selector` and `decentralized_recovery_selector` on
train layouts, selects K_score on VALIDATION only from the predeclared grid, and
reports offline prediction metrics plus the reference arms.

Final-test layouts are never loaded: only build_layouts("train"/"val") is
reachable from here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.binary_pilot import load_labels  # noqa: E402
from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.decentralized.models import build_selector  # noqa: E402
from rvt_swarm.decentralized.system_model import K_SCORE_GRID, KEEP, LINE  # noqa: E402
from rvt_swarm.decentralized.training import (  # noqa: E402
    apply_consensus, assert_matches_runtime_consensus, classify_team_label,
    decisive_classification_loss, recovery_loss, simulate_build_team_dataset,
)
from rvt_swarm.provenance import stamp  # noqa: E402
from rvt_swarm.utils import set_seed  # noqa: E402

METHODS = ("decentralized_direct_selector", "decentralized_recovery_selector")
EPOCHS = 24
LR = 3e-4
WEIGHT_DECAY = 1e-5
VAL_EVERY = 4
K_TRAIN = 4              # rounds used during training (nominal K_score)
RESULTS = REPO / "results" / "decentralized" / "dry_run_seed0"


def brier_nll_auroc(p: np.ndarray, y: np.ndarray) -> dict:
    """p, y flattened over (state, mode). Proper scores plus ranking metrics."""
    p = np.clip(p, 1e-7, 1 - 1e-7)
    brier = float(np.mean((p - y) ** 2))
    nll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    pos, neg = p[y > 0.5], p[y <= 0.5]
    if len(pos) and len(neg):
        auroc = float((pos[:, None] > neg[None, :]).mean()
                      + 0.5 * (pos[:, None] == neg[None, :]).mean())
        order = np.argsort(-p)
        ys = y[order]
        tp = np.cumsum(ys)
        prec = tp / np.arange(1, len(ys) + 1)
        auprc = float((prec * ys).sum() / max(ys.sum(), 1))
    else:
        auroc = auprc = float("nan")
    # 10-bin ECE
    bins = np.clip((p * 10).astype(int), 0, 9)
    ece = 0.0
    for b in range(10):
        m = bins == b
        if m.any():
            ece += m.mean() * abs(p[m].mean() - y[m].mean())
    return {"brier": brier, "nll": nll, "auroc": auroc, "auprc": auprc,
            "ece": float(ece)}


def decisive_metrics(scores: np.ndarray, labels: np.ndarray) -> dict:
    """Ordering-invariant decisive-state metrics, ties scoring 0.5.

    Same definition as docs/DECISIVE_MODE_METRIC_SPECIFICATION.md: only states
    where exactly one mode succeeds are scored, and the always-keep /
    always-line / majority references are reported alongside so a degenerate
    predictor is visible rather than flattering.
    """
    keep_only = (labels[:, 0] > .5) & (labels[:, 1] <= .5)
    line_only = (labels[:, 0] <= .5) & (labels[:, 1] > .5)
    dec = keep_only | line_only
    n_dec = int(dec.sum())
    if n_dec == 0:
        return {"decisive_accuracy": float("nan"), "n_decisive": 0}
    sign = np.sign(scores[dec, 1] - scores[dec, 0])       # +1 -> line, -1 -> keep
    want = np.where(line_only[dec], 1.0, -1.0)
    correct = np.where(sign == 0, 0.5, (sign == want).astype(float))
    ko, lo = keep_only[dec], line_only[dec]
    keep_recall = float(correct[ko].mean()) if ko.any() else float("nan")
    line_recall = float(correct[lo].mean()) if lo.any() else float("nan")
    share_keep = float(ko.mean())
    return {
        "decisive_accuracy": float(correct.mean()),
        "decisive_balanced_accuracy": float(np.nanmean([keep_recall, line_recall])),
        "decisive_keep_recall": keep_recall,
        "decisive_line_recall": line_recall,
        "decisive_coverage": float(dec.mean()),
        "n_decisive": n_dec,
        "n_prediction_ties": int((sign == 0).sum()),
        "always_keep_accuracy": share_keep,
        "always_line_accuracy": 1.0 - share_keep,
        "majority_class_accuracy": max(share_keep, 1.0 - share_keep),
    }


def evaluate(model, data, k: int) -> dict:
    """Offline metrics at consensus depth k. Per-robot predictions, team labels."""
    model.eval()
    P, Y, S, L = [], [], [], []
    per_robot_std, resid = [], []
    with torch.no_grad():
        for s in data:
            q = torch.stack([model.score(s.ego[KEEP]), model.score(s.ego[LINE])], -1)
            z = apply_consensus(q, s.P, k)
            probs = torch.sigmoid(z).numpy()
            P.append(probs.mean(0))                 # team-level readout for scoring
            Y.append(s.label.numpy())
            S.append(z.mean(0).numpy())
            L.append(s.label.numpy())
            per_robot_std.append(float(probs.std(0).max()))
            resid.append(float(np.abs(z.numpy() - z.numpy().mean(0)).max()))
    P, Y = np.stack(P), np.stack(Y)
    out = brier_nll_auroc(P.reshape(-1), Y.reshape(-1))
    out.update(decisive_metrics(np.stack(S), np.stack(L)))
    out["robot_prediction_std"] = float(np.mean(per_robot_std))
    out["consensus_residual"] = float(np.mean(resid))
    return out


def main() -> int:
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = ["cluttered"]
    RESULTS.mkdir(parents=True, exist_ok=True)

    drift = assert_matches_runtime_consensus()
    print(f"training/runtime consensus agreement: max abs diff {drift:.2e}")

    labels = load_labels()
    train = simulate_build_team_dataset(cfg, "train", labels)
    val = simulate_build_team_dataset(cfg, "val", labels)
    print(f"train={len(train)} val={len(val)} team states")

    summary = {}
    for method in METHODS:
        set_seed(0)
        model = build_selector(method)
        n_params = sum(p.numel() for p in model.parameters())
        opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
        rng = np.random.default_rng(0)
        loss_fn = (decisive_classification_loss
                   if method == "decentralized_direct_selector" else recovery_loss)
        print(f"\n[{method}] params={n_params}")

        history = []
        for epoch in range(1, EPOCHS + 1):
            model.train(True)
            tot = 0.0
            for idx in rng.permutation(len(train)):
                s = train[idx]
                q = torch.stack([model.score(s.ego[KEEP]), model.score(s.ego[LINE])], -1)
                z = apply_consensus(q, s.P, K_TRAIN)
                loss = loss_fn(z, s.label)
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                tot += float(loss.detach())
            if epoch % VAL_EVERY == 0:
                m = evaluate(model, val, K_TRAIN)
                history.append({"epoch": epoch, "train_loss": tot / len(train), **m})
                print(f"  ep {epoch:3d} loss={tot/len(train):.4f} "
                      f"brier={m['brier']:.4f} auroc={m['auroc']:.3f} "
                      f"dec_acc={m['decisive_accuracy']:.3f}"
                      f"(ak={m['always_keep_accuracy']:.3f}) "
                      f"resid={m['consensus_residual']:.4f}", flush=True)

        # K_score selection on VALIDATION only, from the predeclared grid.
        k_sweep = {k: evaluate(model, val, k) for k in K_SCORE_GRID}
        best_k = min(K_SCORE_GRID, key=lambda k: k_sweep[k]["brier"])
        print(f"  K sweep (val): " + "  ".join(
            f"K={k}:brier={k_sweep[k]['brier']:.4f}/dec={k_sweep[k]['decisive_accuracy']:.3f}"
            for k in K_SCORE_GRID))
        print(f"  selected K_score={best_k}")

        torch.save({"model": model.state_dict(), "k_score": best_k,
                    "n_params": n_params, **stamp(method=method, model_seed=0)},
                   RESULTS / f"{method}_seed0.pt")
        summary[method] = {
            "n_params": n_params, "selected_k_score": best_k,
            "history": history,
            "k_sweep": {str(k): k_sweep[k] for k in K_SCORE_GRID},
            "final_validation": k_sweep[best_k],
        }

    # ---- reference arms that need no learning -----------------------------
    lab = np.stack([s.label.numpy() for s in val])
    summary["references"] = {
        "always_keep": decisive_metrics(np.tile([[1.0, 0.0]], (len(lab), 1)), lab),
        "always_line": decisive_metrics(np.tile([[0.0, 1.0]], (len(lab), 1)), lab),
        "label_prevalence": {k: int(sum(classify_team_label(s.label) == k for s in val))
                             for k in ("keep_only", "line_only",
                                       "both_succeed", "both_fail")},
    }
    (RESULTS / "training_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nwrote {RESULTS/'training_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
