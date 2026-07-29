"""Stage 1/3 — train one (method, seed) of the binary keep/line pilot.

    python scripts/train_binary_pilot.py <method> <seed> [--dry-run]

Validation-only checkpoint selection under the frozen hierarchy. Final-test
layouts are never loaded by this script.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.binary_pilot import (  # noqa: E402
    build_dataset, closed_loop_validation, collate, compute_pilot_loss, load_labels,
    selection_key, stratified_metrics,
)
from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.models import build_model  # noqa: E402
from rvt_swarm.provenance import stamp  # noqa: E402
from rvt_swarm.utils import set_seed  # noqa: E402
from rvt_swarm.writer_lock import CheckpointWriterLock  # noqa: E402

CKPT_ROOT = REPO / "checkpoints" / "binary_mode_pilot_v1"
METHODS = ("topology_agnostic_gnn", "direct_keep_line_classifier", "rvt_binary_recovery")

# ---- Equal budgets for every method. No method-specific tuning. -------------
EPOCHS = 24
BATCH_SIZE = 32
LR = 3e-4
WEIGHT_DECAY = 1e-5
VAL_EVERY = 4                 # -> 6 validation calls, 6 checkpoint candidates
PATIENCE = 6
CKPT_POOL = 6
CLOSED_LOOP_EPISODES = 2


def pilot_config() -> Config:
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.train.n_workers = 1
    cfg.env.scenarios = ["cluttered"]
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("method", choices=METHODS)
    ap.add_argument("seed", type=int)
    ap.add_argument("--out-root", default=str(CKPT_ROOT))
    ap.add_argument("--results", default=None)
    args = ap.parse_args()

    cfg = pilot_config()
    cfg.seeds.model_seed = args.seed
    prov = stamp(method=args.method, model_seed=args.seed)
    out_dir = Path(args.out_root) / args.method / f"seed_{args.seed}"

    labels = load_labels()
    train = build_dataset(cfg, "train", labels)
    val = build_dataset(cfg, "val", labels)
    print(f"[{args.method} seed {args.seed}] train={len(train)} val={len(val)} states")

    with CheckpointWriterLock(out_dir) as lock:
        set_seed(args.seed)
        model = build_model(args.method, cfg.train.hidden_dim, cfg.train.message_passes)
        n_params = sum(p.numel() for p in model.parameters())
        opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
        order = np.random.default_rng(args.seed)

        candidates, history, best = [], [], None
        steps_per_epoch = int(np.ceil(len(train) / BATCH_SIZE))
        no_improve = 0
        for epoch in range(1, EPOCHS + 1):
            model.train(True)
            idx = order.permutation(len(train))
            tot = {"total": 0.0, "action": 0.0, "bce": 0.0, "ce": 0.0}
            gnorm = 0.0
            for i in range(0, len(idx), BATCH_SIZE):
                b = collate([train[j] for j in idx[i:i + BATCH_SIZE]])
                opt.zero_grad(set_to_none=True)
                out = model(b)
                losses = compute_pilot_loss(out, b, args.method)
                losses["total"].backward()
                gnorm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0))
                opt.step()
                for k in tot:
                    tot[k] += float(losses[k])
            nb = max(steps_per_epoch, 1)
            rec = {"epoch": epoch, "grad_norm": gnorm,
                   **{f"train_{k}": v / nb for k, v in tot.items()}}

            if epoch % VAL_EVERY == 0:
                strat = stratified_metrics(model, val, args.method)
                cl = closed_loop_validation(model, cfg, args.method,
                                            episodes=CLOSED_LOOP_EPISODES)
                rec["validation"] = strat
                rec["closed_loop"] = cl
                key = selection_key(strat["all"], cl)
                candidates.append({"epoch": epoch, "key": key,
                                   "state": {k: v.clone() for k, v in model.state_dict().items()},
                                   "metrics": strat, "closed_loop": cl})
                candidates.sort(key=lambda c: c["key"], reverse=True)
                del candidates[CKPT_POOL:]
                if best is None or key > best["key"]:
                    best, no_improve = candidates[0], 0
                else:
                    no_improve += 1
                a = strat["all"]
                print(f"  ep {epoch:3d} total={rec['train_total']:.5f} "
                      f"brier={a['brier']:.4f} nll={a['nll']:.4f} auroc={a['auroc']:.3f} "
                      f"top1={a['top1_mode_accuracy']:.3f} rmse={a['action_rmse_norm']:.4f} "
                      f"cl_succ={cl['constrained_success']:.3f}", flush=True)
                if no_improve >= PATIENCE:
                    print(f"  early stop at epoch {epoch}")
                    break
            history.append(rec)

        best = candidates[0]
        state = {"model": best["state"], "epoch": best["epoch"],
                 "writer_token": lock.token, "owner_pid": __import__("os").getpid(),
                 "n_params": n_params, "selection_key": list(best["key"]),
                 "selected_validation_metrics": best["metrics"]["all"],
                 "selected_closed_loop": best["closed_loop"],
                 "budget": {"epochs": EPOCHS, "batch_size": BATCH_SIZE, "lr": LR,
                            "weight_decay": WEIGHT_DECAY, "val_every": VAL_EVERY,
                            "patience": PATIENCE, "ckpt_pool": CKPT_POOL,
                            "steps_per_epoch": steps_per_epoch,
                            "max_optimizer_steps": EPOCHS * steps_per_epoch,
                            "hyperparameter_trials": 0},
                 **prov}
        torch.save(state, out_dir / "selected.pt")

        summary = {**prov, "n_params": n_params, "selected_epoch": best["epoch"],
                   "selection_key": list(best["key"]),
                   "candidates": [{"epoch": c["epoch"], "key": list(c["key"]),
                                   "metrics": c["metrics"], "closed_loop": c["closed_loop"]}
                                  for c in sorted(candidates, key=lambda c: c["epoch"])],
                   "history": [{k: v for k, v in h.items() if k != "validation"}
                               for h in history],
                   "budget": state["budget"],
                   "train_states": len(train), "val_states": len(val)}
        res_dir = Path(args.results) if args.results else out_dir
        res_dir.mkdir(parents=True, exist_ok=True)
        (res_dir / f"{args.method}_seed{args.seed}_training.json").write_text(
            json.dumps(summary, indent=2, default=str))
        print(f"  selected epoch {best['epoch']}  -> {out_dir/'selected.pt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
