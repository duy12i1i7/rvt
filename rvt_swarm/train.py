from __future__ import annotations

from pathlib import Path
from typing import Dict

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, random_split

from .config import Config
from .dataset import SwarmDataset, collate_graphs, generate_dataset
from .evaluate import rollout_validation_score, rollout_validation_summary
from .models import build_model
from .utils import set_seed, torch_device


def epochs_for_model(cfg: Config, model_name: str) -> int:
    if model_name == "rvt_swarm":
        return cfg.train.epochs_rvt_swarm
    if model_name == "instant_cert":
        return cfg.train.epochs_instant_cert
    if model_name == "gnn_only":
        return cfg.train.epochs_gnn_only
    return cfg.train.epochs


def split_dataset(ds: SwarmDataset):
    n = len(ds)
    n_train = int(0.9 * n)
    n_val = n - n_train
    return random_split(ds, [n_train, n_val], generator=torch.Generator().manual_seed(ds.cfg.train.seed))


def pairwise_ranking_loss(pred_scores: torch.Tensor, target_scores: torch.Tensor) -> torch.Tensor:
    diffs_t = target_scores[:, :, None] - target_scores[:, None, :]
    diffs_p = pred_scores[:, :, None] - pred_scores[:, None, :]
    sign = torch.sign(diffs_t)
    mask = sign != 0
    if mask.sum() == 0:
        return pred_scores.new_tensor(0.0)
    margins = 1.0 - sign[mask] * diffs_p[mask]
    return torch.relu(margins).mean()


def compute_loss(outputs: Dict, batch: Dict, model_name: str, cfg: Config, epoch: int = 999):
    losses = {}
    losses["action"] = F.mse_loss(outputs["actions"], batch["action_target"])

    # Curriculum warmup: gradually ramp up auxiliary losses for rvt_swarm
    warmup = cfg.train.curriculum_warmup_epochs
    if model_name == "rvt_swarm" and epoch <= warmup:
        aux_scale = max(0.0, (epoch - 1) / max(warmup, 1))
    else:
        aux_scale = 1.0

    if outputs["recoverability"] is not None and model_name in ["rvt_swarm", "instant_cert"] and cfg.method.use_recoverability:
        losses["recover"] = F.mse_loss(outputs["recoverability"], batch["recover_target"]) * aux_scale
    else:
        losses["recover"] = torch.tensor(0.0, device=batch["node_x"].device)
    if outputs["topology_logits"] is not None and model_name == "rvt_swarm" and cfg.method.use_topology:
        losses["topology"] = F.cross_entropy(outputs["topology_logits"], batch["topology_target"]) * aux_scale
        losses["score_map"] = F.mse_loss(outputs["recoverability_scores"], batch["recover_scores_target"]) * aux_scale
        losses["rank"] = pairwise_ranking_loss(outputs["recoverability_scores"], batch["recover_scores_target"]) * aux_scale
        losses["aux"] = F.mse_loss(outputs["aux"], batch["aux_target"]) * aux_scale
        losses["uncertainty"] = (outputs["uncertainty"].mean() * 0.02 if outputs["uncertainty"] is not None else batch["node_x"].new_tensor(0.0)) * aux_scale
    else:
        losses["topology"] = torch.tensor(0.0, device=batch["node_x"].device)
        losses["score_map"] = torch.tensor(0.0, device=batch["node_x"].device)
        losses["rank"] = torch.tensor(0.0, device=batch["node_x"].device)
        losses["aux"] = torch.tensor(0.0, device=batch["node_x"].device)
        losses["uncertainty"] = torch.tensor(0.0, device=batch["node_x"].device)
    total = (
        cfg.train.lambda_action * losses["action"]
        + cfg.train.lambda_recover * losses["recover"]
        + cfg.train.lambda_topology * (losses["topology"] + 0.8 * losses["score_map"] + 0.45 * losses["rank"])
        + cfg.train.lambda_aux * losses["aux"]
        + losses["uncertainty"]
    )
    losses["total"] = total
    return losses


def run_epoch(model, loader, optimizer, device, model_name: str, cfg: Config, train: bool, epoch: int = 999):
    model.train(train)
    totals = {k: 0.0 for k in ["total", "action", "recover", "topology", "score_map", "rank", "aux", "uncertainty"]}
    n_batches = 0
    for batch in loader:
        batch = {k: v.to(device) if torch.is_tensor(v) else v for k, v in batch.items()}
        if train:
            optimizer.zero_grad(set_to_none=True)
        outputs = model(batch)
        losses = compute_loss(outputs, batch, model_name, cfg, epoch)
        if train:
            losses["total"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        for k in totals:
            totals[k] += float(losses[k].item())
        n_batches += 1
    for k in totals:
        totals[k] /= max(n_batches, 1)
    return totals


def loss_checkpoint_metric(val_losses: Dict[str, float]) -> tuple[str, float, str]:
    return ("total", val_losses["total"], "min")


def rollout_validation_start_epoch(cfg: Config, warmup: int) -> int:
    interval = max(int(cfg.train.rollout_val_interval), 1)
    if warmup > 0:
        return warmup + 1
    return interval


def should_run_rollout_validation(cfg: Config, model_name: str, epoch: int, warmup: int) -> bool:
    if not cfg.train.rollout_val_enabled:
        return False
    if model_name not in {"rvt_swarm", "gnn_only", "instant_cert"}:
        return False
    start_epoch = rollout_validation_start_epoch(cfg, warmup)
    interval = max(int(cfg.train.rollout_val_interval), 1)
    return epoch >= start_epoch and (epoch - start_epoch) % interval == 0


def train_model(model_name: str, cfg: Config, out_dir: str = "results", dataset: SwarmDataset | None = None) -> str:
    set_seed(cfg.train.seed)
    device = torch_device(cfg.train.device)
    ds = dataset if dataset is not None else generate_dataset(cfg)
    train_ds, val_ds = split_dataset(ds)
    train_loader = DataLoader(train_ds, batch_size=cfg.train.batch_size, shuffle=True, collate_fn=collate_graphs)
    val_loader = DataLoader(val_ds, batch_size=cfg.train.batch_size, shuffle=False, collate_fn=collate_graphs)
    model = build_model(model_name, cfg.train.hidden_dim, cfg.train.message_passes, cfg.train.aux_gradient_scale).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.train.lr, weight_decay=cfg.train.weight_decay)

    num_epochs = epochs_for_model(cfg, model_name)
    patience = cfg.train.early_stopping_patience
    min_delta = cfg.train.early_stopping_min_delta

    best_val = float("inf")
    best_epoch = 0
    patience_counter = 0
    best_mode = "min"
    last_rollout_score = None
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    best_ckpt = out_path / f"{model_name}_best.pt"
    last_ckpt = out_path / f"{model_name}_last.pt"
    legacy_ckpt = out_path / f"{model_name}.pt"

    # For rvt_swarm with curriculum warmup, early stopping must not activate
    # until warmup is complete, because aux losses ramp up and inflate total loss.
    warmup = cfg.train.curriculum_warmup_epochs if model_name == "rvt_swarm" else 0

    for epoch in range(1, num_epochs + 1):
        tr = run_epoch(model, train_loader, optimizer, device, model_name, cfg, True, epoch)
        va = run_epoch(model, val_loader, optimizer, device, model_name, cfg, False, epoch)

        # During warmup: always save, don't count patience
        in_warmup = epoch <= warmup

        rollout_summary = None
        ran_rollout = should_run_rollout_validation(cfg, model_name, epoch, warmup)
        rollout_start = rollout_validation_start_epoch(cfg, warmup)
        if ran_rollout:
            rollout_summary = rollout_validation_summary(model_name, cfg, model, str(out_path))
            last_rollout_score = rollout_validation_score(rollout_summary)

        use_rollout_metric = (
            cfg.train.rollout_val_enabled
            and model_name in {"rvt_swarm", "gnn_only", "instant_cert"}
            and epoch >= rollout_start
        )
        metric_ready = not use_rollout_metric or ran_rollout
        update_best = False
        if in_warmup:
            metric_name, tracking, metric_mode = loss_checkpoint_metric(va)
        elif use_rollout_metric:
            metric_name, metric_mode = "rollout_score", "max"
            tracking = last_rollout_score if last_rollout_score is not None else float("nan")
        else:
            metric_name, tracking, metric_mode = loss_checkpoint_metric(va)

        # When switching from loss-based to rollout-based checkpointing,
        # reset the comparator so old supervised-loss checkpoints don't dominate.
        if metric_ready and metric_mode != best_mode:
            best_mode = metric_mode
            best_val = float("-inf") if metric_mode == "max" else float("inf")
            patience_counter = 0

        if in_warmup:
            update_best = True
            best_val = tracking
            best_epoch = epoch
            patience_counter = 0
        elif use_rollout_metric:
            if metric_ready:
                improved = tracking > (best_val + min_delta)
                if improved:
                    best_val = tracking
                    best_epoch = epoch
                    patience_counter = 0
                    update_best = True
                else:
                    patience_counter += 1
        else:
            improved = tracking < (best_val - min_delta)
            if improved:
                best_val = tracking
                best_epoch = epoch
                patience_counter = 0
                update_best = True
            else:
                patience_counter += 1

        if update_best:
            state = {
                "model": model.state_dict(),
                "config": cfg,
                "epoch": epoch,
                "best_val": best_val,
                "best_metric": metric_name,
                "best_metric_mode": best_mode,
                "validation_summary": rollout_summary,
                "model_name": model_name,
            }
            torch.save(state, best_ckpt)
            if cfg.train.save_best_only:
                torch.save(state, legacy_ckpt)

        torch.save({
            "model": model.state_dict(),
            "config": cfg,
            "epoch": epoch,
            "best_val": best_val,
            "best_metric": metric_name,
            "best_metric_mode": best_mode,
            "validation_summary": rollout_summary,
            "model_name": model_name,
        }, last_ckpt)

        warmup_tag = " [warmup]" if in_warmup else ""
        rollout_tag = ""
        if rollout_summary is not None and last_rollout_score is not None:
            rollout_tag = (
                f" roll_succ={rollout_summary['success']:.3f}"
                f" roll_cf={rollout_summary['collision_free']:.3f}"
                f" roll_form={rollout_summary['form_ok']:.3f}"
                f" roll_score={last_rollout_score:.4f}"
            )
        print(
            f"[{model_name}] epoch {epoch:02d} train={tr['total']:.4f} val={va['total']:.4f} "
            f"rank={va['rank']:.4f} topo={va['topology']:.4f} "
            f"track_{metric_name}={tracking:.4f}{rollout_tag}{warmup_tag}"
        )

        if not in_warmup and patience_counter >= patience:
            print(
                f"[{model_name}] early stopping at epoch {epoch}; "
                f"best epoch={best_epoch}, best {metric_name}={best_val:.4f}"
            )
            break

    if best_ckpt.exists():
        state = torch.load(best_ckpt, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        print(
            f"[{model_name}] loaded best checkpoint from epoch {state.get('epoch', best_epoch):02d} "
            f"with {state.get('best_metric', 'total')}={state.get('best_val', best_val):.4f}"
        )
        torch.save(state, legacy_ckpt)
        return str(best_ckpt)
    return str(legacy_ckpt)
