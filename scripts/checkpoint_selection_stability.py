"""Task 8 — which checkpoint-selection criterion is stable? Validation layouts only.

The Method Audit found 8 validation episodes selecting an epoch-5 checkpoint over
an epoch-60 one with ~3x better action RMSE. This measures the alternatives and
their bootstrap rank stability. The criterion is chosen by the predeclared rule in
docs/CHECKPOINT_SELECTION_V2.md, NOT by whichever gives the best final-test result
(no final-test layout is loaded here).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.dataset import collate_graphs, generate_dataset  # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv  # noqa: E402
from rvt_swarm.layouts import build_layouts  # noqa: E402
from rvt_swarm.metrics import EpisodeAccumulator  # noqa: E402
from rvt_swarm.models import build_model  # noqa: E402
from rvt_swarm.policy_runtime import infer_learned_action  # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds  # noqa: E402
from rvt_swarm.train import compute_loss, git_commit, pairwise_ranking_loss  # noqa: E402
from rvt_swarm.utils import set_seed  # noqa: E402

OUT = REPO / "results" / "scenario_headroom"
TAG = "method-audit-v2-complete"
MODEL = "rvt_simple_rank"
EPOCHS, SNAP_EVERY = 24, 4
VAL_EPISODES = 40          # up from 8 -- the audit's core complaint
BOOTSTRAP = 400


def val_episode(cfg, model, layout, n, seed):
    env = SwarmFormationEnv(cfg)
    obs = env.reset(n, "cluttered", seed=seed, layout=layout)
    acc = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance, dt=cfg.env.dt)
    done, last, prev = False, None, 0
    while not done:
        rt = infer_learned_action(MODEL, obs, cfg, model, prev)
        prev = rt["topology"]
        obs, _, done, last = env.step(rt["actions"], rt["topology"])
        acc.update(last)
    return acc.finalize(last)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.train.n_workers = 1
    cfg.env.team_sizes = [4, 6]
    cfg.env.scenarios = ["cluttered"]
    cfg.seeds.model_seed = 0
    print(f"commit={git_commit()} tag={TAG} model={MODEL}")

    train_layouts = build_layouts("train")
    val_layouts = build_layouts("val")
    print(f"train layouts={len(train_layouts)} val layouts={len(val_layouts)}")

    # --- training data from TRAIN layouts only --------------------------------
    ds = generate_dataset(cfg, episodes=24)
    from torch.utils.data import DataLoader, random_split
    n_tr = int(0.9 * len(ds))
    tr, va = random_split(ds, [n_tr, len(ds) - n_tr],
                          generator=torch.Generator().manual_seed(0))
    tl = DataLoader(tr, batch_size=cfg.train.batch_size, shuffle=True,
                    collate_fn=collate_graphs,
                    generator=torch.Generator().manual_seed(0))
    vl = DataLoader(va, batch_size=cfg.train.batch_size, shuffle=False,
                    collate_fn=collate_graphs)

    set_seed(0)
    model = build_model(MODEL, cfg.train.hidden_dim, cfg.train.message_passes)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.train.lr,
                            weight_decay=cfg.train.weight_decay)
    snapshots = []
    for epoch in range(1, EPOCHS + 1):
        model.train(True)
        for b in tl:
            opt.zero_grad(set_to_none=True)
            out = model(b, action_topology=b["topology_target"])
            compute_loss(out, b, MODEL, cfg)["total"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        if epoch % SNAP_EVERY == 0:
            snapshots.append((epoch, {k: v.clone() for k, v in model.state_dict().items()}))
            print(f"  snapshot epoch {epoch}", flush=True)

    # --- score every snapshot on VALIDATION layouts ---------------------------
    val_seeds = [(lay, n, s) for lay in val_layouts for n in (4, 6)
                 for s in setting_episode_seeds(VALIDATION, 0, n, 2, 0)][:VAL_EPISODES]
    print(f"validation episodes per snapshot: {len(val_seeds)}")

    rows, per_ep = [], {}
    for epoch, state in snapshots:
        model.load_state_dict(state)
        model.eval()
        # A: supervised action loss  B: ranking loss  (held-out supervised split)
        a_losses, ranks, accs = [], [], []
        with torch.no_grad():
            for b in vl:
                out = model(b, action_topology=b["topology_target"])
                a_losses.append(float(F.mse_loss(out["actions_by_topology"][:, 0, :],
                                                 b["action_target_keep"])))
                ranks.append(float(pairwise_ranking_loss(out["recoverability_scores"],
                                                         b["recover_scores_target"])))
                s, t = out["recoverability_scores"], b["recover_scores_target"]
                ds_ = s[:, :, None] - s[:, None, :]
                dt_ = t[:, :, None] - t[:, None, :]
                m = dt_.abs() > 1e-9
                if m.sum() > 0:
                    accs.append(float(((torch.sign(ds_) == torch.sign(dt_)) & m).sum() / m.sum()))
        # D: closed-loop task score on validation layouts
        ep_metrics = [val_episode(cfg, model, lay, n, s) for lay, n, s in val_seeds]
        per_ep[epoch] = ep_metrics
        succ = float(np.mean([m["success"] for m in ep_metrics]))
        cf = float(np.mean([m["collision_free"] for m in ep_metrics]))
        goal = float(np.mean([m["goal_reached"] for m in ep_metrics]))
        rows.append({
            "benchmark_tag": TAG, "git_commit": git_commit(), "epoch": epoch,
            "A_val_action_loss": float(np.mean(a_losses)),
            "B_val_rank_loss": float(np.mean(ranks)),
            "C_val_ranking_accuracy": float(np.mean(accs)) if accs else float("nan"),
            "D_val_task_success": succ, "D_val_collision_free": cf, "D_val_goal": goal,
            "E_composite": 0.5 * (float(np.mean(accs)) if accs else 0.0)
                           + 0.5 * succ,
            "val_episodes": len(ep_metrics),
        })
        print(f"  epoch {epoch:3d}  A={rows[-1]['A_val_action_loss']:.5f} "
              f"B={rows[-1]['B_val_rank_loss']:.4f} C={rows[-1]['C_val_ranking_accuracy']:.3f} "
              f"D={succ:.3f} E={rows[-1]['E_composite']:.3f}", flush=True)

    # --- bootstrap rank stability of the episode-based criterion --------------
    rng = np.random.default_rng(12345)
    epochs = [e for e, _ in snapshots]
    winners = {"D_val_task_success": [], "C_val_ranking_accuracy": []}
    n_ep = len(val_seeds)
    for _ in range(BOOTSTRAP):
        idx = rng.integers(0, n_ep, n_ep)
        succ = {e: float(np.mean([per_ep[e][i]["success"] for i in idx])) for e in epochs}
        winners["D_val_task_success"].append(max(succ, key=succ.get))
    # C is computed on the supervised split, which the episode bootstrap cannot
    # resample; its stability is reported as the spread across snapshots instead.
    from collections import Counter
    dwin = Counter(winners["D_val_task_success"])
    top_epoch, top_count = dwin.most_common(1)[0]
    stability = top_count / BOOTSTRAP
    c_vals = [r["C_val_ranking_accuracy"] for r in rows]
    best_c_epoch = epochs[int(np.argmax(c_vals))]

    rows.append({
        "benchmark_tag": TAG, "git_commit": git_commit(), "epoch": -1,
        "bootstrap_draws": BOOTSTRAP,
        "D_modal_winner_epoch": top_epoch,
        "D_winner_stability": stability,
        "D_distinct_winners": len(dwin),
        "C_best_epoch": best_c_epoch,
        "C_spread": float(np.max(c_vals) - np.min(c_vals)),
        "A_best_epoch": epochs[int(np.argmin([r["A_val_action_loss"] for r in rows[:-0] or rows]))]
        if rows else -1,
    })

    keys = sorted({k for r in rows for k in r})
    with (OUT / "checkpoint_selection_stability.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader(); w.writerows(rows)
    print(f"\nwrote {OUT/'checkpoint_selection_stability.csv'}")
    print(f"bootstrap ({BOOTSTRAP} draws, {n_ep} val episodes):")
    print(f"  closed-loop success  -> modal winner epoch {top_epoch}, "
          f"stability {stability:.3f}, {len(dwin)} distinct winners")
    print(f"  ranking accuracy     -> best epoch {best_c_epoch}, "
          f"spread {float(np.max(c_vals)-np.min(c_vals)):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
