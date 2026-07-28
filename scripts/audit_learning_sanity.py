"""Task 1 — can the models actually learn the expert targets?

A. Micro-overfit: a tiny fixed dataset that any correctly-wired model should
   memorise. Failure here is an optimisation/wiring bug, not a data problem.
B. Small-data generalization: identical budgets, validation-split rollouts only.

TRAINING AND VALIDATION SPLITS ONLY. No final-test scenario is touched.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.dataset import collate_graphs, generate_dataset  # noqa: E402
from rvt_swarm.evaluate import rollout_validation_summary  # noqa: E402
from rvt_swarm.models import build_model  # noqa: E402
from rvt_swarm.train import compute_loss, git_commit  # noqa: E402
from rvt_swarm.utils import set_seed  # noqa: E402

OUT = REPO / "results" / "method_audit"
BENCHMARK_TAG = "benchmark-protocol-v2-smoke"
MODELS = ["gnn_only", "rvt_swarm"]


def audit_config(expert_episodes: int) -> Config:
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.train.n_workers = 4
    cfg.train.expert_episodes = expert_episodes
    cfg.env.team_sizes = [4, 8]
    cfg.env.scenarios = ["open_field", "cluttered", "narrow_passage", "dynamic_obstacles"]
    cfg.train.rollout_val_team_sizes = [5, 11]
    cfg.train.rollout_val_scenarios = ["open_field", "narrow_passage"]
    cfg.train.rollout_val_episodes_per_setting = 2
    cfg.seeds.model_seed = 0
    cfg.seeds.training_data_seed = 0
    cfg.seeds.validation_seed = 0
    return cfg


def diagnostics(model, out, batch, name, cfg) -> dict:
    """Action RMSE, topology accuracy, ranking accuracy -- in interpretable units."""
    d = {}
    if name == "rvt_swarm" and out.get("actions_by_topology") is not None:
        pred = out["actions_by_topology"][:, 0, :]
    else:
        pred = out["actions"]
    tgt = batch["action_target_keep"]
    d["action_rmse_norm"] = float(torch.sqrt(F.mse_loss(pred, tgt)).item())
    d["action_rmse_mps2"] = d["action_rmse_norm"] * cfg.env.max_accel
    d["target_action_std"] = float(tgt.std().item())

    if out.get("topology_logits") is not None:
        pred_t = out["topology_logits"].argmax(dim=-1)
        d["topology_accuracy"] = float((pred_t == batch["topology_target"].view(-1)).float().mean())
        s, t = out["recoverability_scores"], batch["recover_scores_target"]
        ds_ = s[:, :, None] - s[:, None, :]
        dt_ = t[:, :, None] - t[:, None, :]
        mask = dt_.abs() > 1e-9
        d["ranking_accuracy"] = (
            float(((torch.sign(ds_) == torch.sign(dt_)) & mask).sum() / mask.sum())
            if mask.sum() > 0 else float("nan")
        )
        d["score_rmse"] = float(torch.sqrt(F.mse_loss(s, t)).item())
    else:
        d.update(topology_accuracy=float("nan"), ranking_accuracy=float("nan"),
                 score_rmse=float("nan"))
    return d


def micro_overfit(cfg: Config, n_samples: int = 64, steps: int = 1500) -> list:
    print(f"\n{'='*72}\nA. MICRO-OVERFIT  ({n_samples} samples, {steps} steps)\n{'='*72}")
    ds = generate_dataset(cfg, episodes=2)
    samples = [ds[i] for i in range(min(n_samples, len(ds)))]
    batch = collate_graphs(samples)
    rows = []
    for name in MODELS:
        set_seed(0)
        model = build_model(name, cfg.train.hidden_dim, cfg.train.message_passes)
        opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.0)
        first = last = None
        for step in range(steps):
            opt.zero_grad(set_to_none=True)
            at = batch["topology_target"] if name == "rvt_swarm" else None
            out = model(batch, action_topology=at) if name == "rvt_swarm" else model(batch)
            losses = compute_loss(out, batch, name, cfg)
            losses["total"].backward()
            gnorm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1e9))
            before = [p.detach().clone() for p in model.parameters()]
            opt.step()
            upd = float(torch.sqrt(sum(((p.detach() - b) ** 2).sum()
                                       for p, b in zip(model.parameters(), before))))
            if step % 100 == 0 or step == steps - 1:
                with torch.no_grad():
                    o = model(batch, action_topology=at) if name == "rvt_swarm" else model(batch)
                    dg = diagnostics(model, o, batch, name, cfg)
                rec = {
                    "test": "micro_overfit", "model": name, "step": step,
                    "total_loss": float(losses["total"]), "action_loss": float(losses["action"]),
                    "topology_loss": float(losses["topology"]),
                    "score_loss": float(losses["score_map"]),
                    "rank_loss": float(losses["rank"]),
                    "grad_norm": gnorm, "param_update_norm": upd,
                    "has_nan": int(not np.isfinite(float(losses["total"]))),
                    **dg,
                }
                rows.append(rec)
                if first is None:
                    first = rec
                last = rec
                if step % 500 == 0:
                    print(f"  [{name}] step {step:4d} total={rec['total_loss']:.5f} "
                          f"act_rmse={rec['action_rmse_mps2']:.4f} m/s^2 "
                          f"topo_acc={rec['topology_accuracy']:.3f} "
                          f"rank_acc={rec['ranking_accuracy']:.3f} |g|={gnorm:.3f}")
        print(f"  [{name}] initial total={first['total_loss']:.5f} -> final={last['total_loss']:.5f} "
              f"({100*(1-last['total_loss']/max(first['total_loss'],1e-12)):.1f}% reduction)")
        print(f"  [{name}] action RMSE {first['action_rmse_mps2']:.4f} -> "
              f"{last['action_rmse_mps2']:.4f} m/s^2 "
              f"(target std {last['target_action_std']*cfg.env.max_accel:.4f})")
    return rows


def small_data_generalization(cfg: Config, epochs: int = 60, val_every: int = 5) -> list:
    print(f"\n{'='*72}\nB. SMALL-DATA GENERALIZATION  ({epochs} epochs, val every {val_every})\n{'='*72}")
    from torch.utils.data import DataLoader, random_split

    ds = generate_dataset(cfg)
    n_train = int(0.9 * len(ds))
    tr, va = random_split(ds, [n_train, len(ds) - n_train],
                          generator=torch.Generator().manual_seed(0))
    print(f"  dataset {len(ds)} samples -> train {len(tr)} / heldout-loss {len(va)}")
    rows = []
    for name in MODELS:
        set_seed(cfg.seeds.model_seed)
        model = build_model(name, cfg.train.hidden_dim, cfg.train.message_passes)
        opt = torch.optim.AdamW(model.parameters(), lr=cfg.train.lr,
                                weight_decay=cfg.train.weight_decay)
        tl = DataLoader(tr, batch_size=cfg.train.batch_size, shuffle=True,
                        collate_fn=collate_graphs,
                        generator=torch.Generator().manual_seed(cfg.seeds.model_seed))
        vl = DataLoader(va, batch_size=cfg.train.batch_size, shuffle=False,
                        collate_fn=collate_graphs)
        best_key, best_epoch = None, 0
        for epoch in range(1, epochs + 1):
            model.train(True)
            tot = nb = 0.0
            for b in tl:
                opt.zero_grad(set_to_none=True)
                at = b["topology_target"] if name == "rvt_swarm" else None
                o = model(b, action_topology=at) if name == "rvt_swarm" else model(b)
                ls = compute_loss(o, b, name, cfg)
                ls["total"].backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                tot += float(ls["total"]); nb += 1
            train_loss = tot / max(nb, 1)

            model.train(False)
            vtot = vnb = 0.0
            dg_acc = []
            with torch.no_grad():
                for b in vl:
                    at = b["topology_target"] if name == "rvt_swarm" else None
                    o = model(b, action_topology=at) if name == "rvt_swarm" else model(b)
                    ls = compute_loss(o, b, name, cfg)
                    vtot += float(ls["total"]); vnb += 1
                    dg_acc.append(diagnostics(model, o, b, name, cfg))
            val_loss = vtot / max(vnb, 1)
            dg = {k: float(np.nanmean([d[k] for d in dg_acc])) for k in dg_acc[0]}

            rec = {"test": "small_data", "model": name, "epoch": epoch,
                   "train_loss": train_loss, "val_loss": val_loss, **dg}
            if epoch % val_every == 0 or epoch == 1:
                summary = rollout_validation_summary(name, cfg, model, str(OUT / "tmp_ckpt"))
                rec.update({
                    "val_success": summary["success"],
                    "val_goal_reached": summary["goal_reached"],
                    "val_collision_free": summary["collision_free"],
                    "val_form_ok": summary["form_ok"],
                    "val_time_in_tube": summary["time_in_formation_tube"],
                    "val_form_rms_mean": summary["form_rms_mean"],
                    "val_deadlock": summary["deadlock"],
                    "val_collapse": summary["irreversible_collapse"],
                })
                key = (summary["success"], summary["goal_reached"],
                       summary["collision_free"], summary["form_ok"])
                if best_key is None or key > best_key:
                    best_key, best_epoch = key, epoch
                print(f"  [{name}] ep {epoch:3d} train={train_loss:.5f} val={val_loss:.5f} "
                      f"act_rmse={dg['action_rmse_mps2']:.4f} "
                      f"| VAL succ={summary['success']:.3f} cf={summary['collision_free']:.3f} "
                      f"goal={summary['goal_reached']:.3f} tube={summary['time_in_formation_tube']:.3f}")
            rows.append(rec)
        print(f"  [{name}] best validation checkpoint epoch = {best_epoch}")
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg_micro = audit_config(expert_episodes=2)
    cfg_small = audit_config(expert_episodes=30)
    print(f"commit={git_commit()}  benchmark_tag={BENCHMARK_TAG}")
    rows = micro_overfit(cfg_micro) + small_data_generalization(cfg_small)
    keys = sorted({k for r in rows for k in r})
    with (OUT / "learning_curves.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["benchmark_tag", "git_commit"] + keys)
        w.writeheader()
        for r in rows:
            w.writerow({"benchmark_tag": BENCHMARK_TAG, "git_commit": git_commit(), **r})
    print(f"\nwrote {OUT / 'learning_curves.csv'} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
