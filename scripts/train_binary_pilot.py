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
    build_action_dataset, build_dataset, collate, compute_pilot_loss,
    end_to_end_evaluation, fixed_mode_evaluation, load_labels, selection_key,
    selector_only_evaluation, stratified_action_metrics, stratified_metrics,
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
    # Sparse recovery dataset (unchanged, 759 states) and dense action dataset.
    rec_train = build_dataset(cfg, "train", labels)
    rec_val = build_dataset(cfg, "val", labels)
    act_train = build_action_dataset(cfg, "train")
    act_val = build_action_dataset(cfg, "val")
    print(f"[{args.method} seed {args.seed}] action train={len(act_train)} val={len(act_val)} | "
          f"recovery train={len(rec_train)} val={len(rec_val)}")

    with CheckpointWriterLock(out_dir) as lock:
        set_seed(args.seed)
        model = build_model(args.method, cfg.train.hidden_dim, cfg.train.message_passes)
        n_params = sum(p.numel() for p in model.parameters())
        opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
        order = np.random.default_rng(args.seed)

        candidates, history, best = [], [], None
        steps_per_epoch = int(np.ceil(len(act_train) / BATCH_SIZE))
        no_improve = 0
        rec_ptr = 0
        for epoch in range(1, EPOCHS + 1):
            model.train(True)
            act_idx = order.permutation(len(act_train))
            rec_idx = order.permutation(len(rec_train))
            tot = {"total": 0.0, "action": 0.0, "bce": 0.0, "ce": 0.0}
            gnorm, n_dec_seen, n_batches_no_dec = 0.0, 0, 0
            for i in range(0, len(act_idx), BATCH_SIZE):
                # (1) one dense action batch -- identical IDs/order for every method
                ab = collate([act_train[j] for j in act_idx[i:i + BATCH_SIZE]])
                # (2) one recovery batch, only if the method has a head that needs it
                rb = ro = None
                if args.method != "topology_agnostic_gnn":
                    sl = [rec_train[rec_idx[(rec_ptr + k) % len(rec_idx)]]
                          for k in range(BATCH_SIZE)]
                    rec_ptr += BATCH_SIZE
                    rb = collate(sl)
                    lab = rb["recovery_labels"]
                    dec = int((((lab[:, 0] > .5) & (lab[:, 1] <= .5))
                               | ((lab[:, 0] <= .5) & (lab[:, 1] > .5))).sum())
                    n_dec_seen += dec
                    n_batches_no_dec += int(dec == 0)
                opt.zero_grad(set_to_none=True)
                out = model(ab)
                if rb is not None:
                    ro = model(rb)
                losses = compute_pilot_loss(out, ab, args.method, ro, rb)
                losses["total"].backward()
                gnorm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0))
                opt.step()
                for k in tot:
                    tot[k] += float(losses[k].detach())
            nb = max(steps_per_epoch, 1)
            rec = {"epoch": epoch, "grad_norm": gnorm,
                   "decisive_examples_seen": n_dec_seen,
                   "batches_without_decisive": n_batches_no_dec,
                   **{f"train_{k}": v / nb for k, v in tot.items()}}

            if epoch % VAL_EVERY == 0:
                strat = stratified_metrics(model, rec_val, args.method)
                act_strat = stratified_action_metrics(model, act_val, args.method)
                sel_only = selector_only_evaluation(model, cfg, args.method,
                                                    episodes=CLOSED_LOOP_EPISODES)
                e2e = end_to_end_evaluation(model, cfg, args.method,
                                            episodes=CLOSED_LOOP_EPISODES)
                cl = {"constrained_success": e2e["task_recovery_proxy_success"],
                      "selector_only_success": sel_only["task_recovery_proxy_success"],
                      "end_to_end_success": e2e["task_recovery_proxy_success"]}
                rec["validation"] = strat
                rec["action"] = act_strat
                rec["selector_only"] = sel_only
                rec["end_to_end"] = e2e
                key = selection_key(strat["all"], cl)
                candidates.append({"epoch": epoch, "key": key,
                                   "state": {k: v.clone() for k, v in model.state_dict().items()},
                                   "metrics": strat, "action": act_strat,
                                   "selector_only": sel_only, "end_to_end": e2e,
                                   "closed_loop": cl})
                candidates.sort(key=lambda c: c["key"], reverse=True)
                del candidates[CKPT_POOL:]
                if best is None or key > best["key"]:
                    best, no_improve = candidates[0], 0
                else:
                    no_improve += 1
                a, am = strat["all"], act_strat["all"]
                print(f"  ep {epoch:3d} tot={rec['train_total']:.4f} "
                      f"brier={a['brier']:.4f} auroc={a['auroc']:.3f} "
                      f"dec_acc={a['decisive_accuracy']:.3f}(ak={a['always_keep_accuracy']:.3f}) "
                      f"nRMSE={am['normalized_rmse']:.3f} "
                      f"sel={sel_only['task_recovery_proxy_success']:.3f} "
                      f"e2e={e2e['task_recovery_proxy_success']:.3f}", flush=True)
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
                 "selected_action_metrics": best["action"],
                 "selected_selector_only": best["selector_only"],
                 "selected_end_to_end": best["end_to_end"],
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
                                   "metrics": c["metrics"], "closed_loop": c["closed_loop"],
                                   "action": c["action"], "selector_only": c["selector_only"],
                                   "end_to_end": c["end_to_end"]}
                                  for c in sorted(candidates, key=lambda c: c["epoch"])],
                   "history": [{k: v for k, v in h.items() if k != "validation"}
                               for h in history],
                   "budget": state["budget"],
                   "action_train_states": len(act_train), "action_val_states": len(act_val),
                   "recovery_train_states": len(rec_train), "recovery_val_states": len(rec_val)}
        res_dir = Path(args.results) if args.results else out_dir
        res_dir.mkdir(parents=True, exist_ok=True)
        (res_dir / f"{args.method}_seed{args.seed}_training.json").write_text(
            json.dumps(summary, indent=2, default=str))
        print(f"  selected epoch {best['epoch']}  -> {out_dir/'selected.pt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
