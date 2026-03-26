from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, random_split

from .config import Config
from .dataset import SwarmDataset, collate_graphs, generate_dataset
from .evaluate import rollout_validation_key, rollout_validation_score, rollout_validation_summary
from .models import build_model
from .utils import score_dispersion_tensor, set_seed, torch_device


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
    return F.softplus(-(sign[mask] * diffs_p[mask])).mean()


def soft_topology_alignment_loss(logits: torch.Tensor, target_scores: torch.Tensor) -> torch.Tensor:
    # Align topology preference with the full recoverability score map rather
    # than a brittle argmax label. This keeps topology supervision consistent
    # with the docs' counterfactual "positive margin wins" semantics.
    target_dist = torch.softmax(target_scores, dim=-1)
    return F.kl_div(F.log_softmax(logits, dim=-1), target_dist, reduction="batchmean")


def select_action_target(batch: Dict, model_name: str, cfg: Config) -> torch.Tensor:
    # Keep action supervision aligned with runtime execution.
    # `rvt_swarm` can switch topology online; the baselines `gnn_only`
    # and `instant_cert` always execute topology 0 at runtime.
    if model_name == "rvt_swarm" and cfg.method.use_topology:
        return batch["action_target_best"]
    return batch["action_target_keep"]


def compute_loss(outputs: Dict, batch: Dict, model_name: str, cfg: Config, epoch: int = 999):
    losses = {}
    if model_name == "rvt_swarm" and cfg.method.use_topology and outputs.get("actions_by_topology") is not None:
        losses["action"] = F.mse_loss(outputs["actions_by_topology"], batch["action_target_all"])
    else:
        losses["action"] = F.mse_loss(outputs["actions"], select_action_target(batch, model_name, cfg))

    if outputs["recoverability"] is not None and model_name == "instant_cert" and cfg.method.use_recoverability:
        losses["recover"] = F.mse_loss(outputs["recoverability"], batch["recover_target"])
    else:
        losses["recover"] = torch.tensor(0.0, device=batch["node_x"].device)
    if outputs["topology_logits"] is not None and model_name == "rvt_swarm" and cfg.method.use_topology:
        losses["aux"] = F.mse_loss(outputs["aux"], batch["aux_target"])
        if cfg.method.use_recoverability:
            losses["topology"] = soft_topology_alignment_loss(
                outputs["topology_logits"],
                batch["recover_scores_target"],
            )
            losses["score_map"] = F.mse_loss(outputs["recoverability_scores"], batch["recover_scores_target"])
            losses["rank"] = pairwise_ranking_loss(outputs["recoverability_scores"], batch["recover_scores_target"])
            if outputs["uncertainty"] is not None:
                score_scale = score_dispersion_tensor(batch["recover_scores_target"]).mean()
                losses["uncertainty"] = outputs["uncertainty"].mean() / (1.0 + score_scale)
            else:
                losses["uncertainty"] = batch["node_x"].new_tensor(0.0)
        else:
            losses["topology"] = F.cross_entropy(outputs["topology_logits"], batch["topology_target"])
            losses["score_map"] = batch["node_x"].new_tensor(0.0)
            losses["rank"] = batch["node_x"].new_tensor(0.0)
            losses["uncertainty"] = batch["node_x"].new_tensor(0.0)
    else:
        losses["topology"] = torch.tensor(0.0, device=batch["node_x"].device)
        losses["score_map"] = torch.tensor(0.0, device=batch["node_x"].device)
        losses["rank"] = torch.tensor(0.0, device=batch["node_x"].device)
        losses["aux"] = torch.tensor(0.0, device=batch["node_x"].device)
        losses["uncertainty"] = torch.tensor(0.0, device=batch["node_x"].device)
    topology_terms = [losses["topology"]]
    if model_name == "rvt_swarm" and cfg.method.use_topology and cfg.method.use_recoverability:
        topology_terms.extend([losses["score_map"], losses["rank"]])
    topology_bundle = torch.stack(topology_terms).mean()
    active_terms = [losses["action"]]
    if model_name == "instant_cert" and cfg.method.use_recoverability:
        active_terms.append(losses["recover"])
    if model_name == "rvt_swarm" and cfg.method.use_topology:
        active_terms.extend([topology_bundle, losses["aux"]])
        if cfg.method.use_recoverability:
            active_terms.append(losses["uncertainty"])
    total = torch.stack(active_terms).mean()
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
        if model_name == "rvt_swarm":
            action_topology = batch["topology_target"] if cfg.method.use_topology else torch.zeros_like(batch["topology_target"])
            outputs = model(batch, action_topology=action_topology)
        else:
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


def rollout_candidate_path(out_path: Path, model_name: str, epoch: int) -> Path:
    return out_path / f"{model_name}_rollout_epoch{epoch:03d}.pt"


def maybe_record_rollout_candidate(
    *,
    records: list[dict[str, object]],
    out_path: Path,
    model_name: str,
    epoch: int,
    score_key: tuple[float, ...],
    score: float,
    state: Dict[str, object],
    topk: int,
) -> None:
    candidate_path = rollout_candidate_path(out_path, model_name, epoch)
    torch.save(state, candidate_path)
    records.append(
        {
            "key": tuple(float(x) for x in score_key),
            "score": float(score),
            "epoch": int(epoch),
            "path": candidate_path,
        }
    )
    records.sort(key=lambda item: (tuple(item["key"]), int(item["epoch"])), reverse=True)
    while len(records) > max(topk, 1):
        dropped = records.pop()
        dropped_path = Path(dropped["path"])
        if dropped_path.exists():
            dropped_path.unlink()


def recheck_rollout_candidates(
    model_name: str,
    cfg: Config,
    model,
    records: list[dict[str, object]],
    out_path: Path,
    device: torch.device,
) -> tuple[dict[str, object] | None, dict[str, float] | None, float | None]:
    if not records:
        return None, None, None

    recheck_eps = max(
        int(cfg.train.rollout_val_recheck_episodes_per_setting),
        int(cfg.train.rollout_val_episodes_per_setting),
    )
    seed_offset = int(cfg.train.rollout_val_recheck_seed_offset)

    best_state = None
    best_summary = None
    best_score = None
    best_key = None
    best_epoch = -1
    for record in records:
        state = torch.load(Path(record["path"]), map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        model.eval()
        summary = rollout_validation_summary(
            model_name,
            cfg,
            model,
            str(out_path),
            episodes_per_setting=recheck_eps,
            seed_offset=seed_offset,
        )
        score = rollout_validation_score(summary)
        key = rollout_validation_key(summary)
        epoch = int(state.get("epoch", record["epoch"]))
        if (
            best_key is None
            or key > best_key
            or (key == best_key and (best_score is None or score > best_score or (score == best_score and epoch > best_epoch)))
        ):
            best_state = state
            best_summary = summary
            best_score = score
            best_key = key
            best_epoch = epoch

    return best_state, best_summary, best_score


def train_model(model_name: str, cfg: Config, out_dir: str = "results", dataset: SwarmDataset | None = None) -> str:
    set_seed(cfg.train.seed)
    device = torch_device(cfg.train.device)
    ds = dataset if dataset is not None else generate_dataset(cfg)
    train_ds, val_ds = split_dataset(ds)
    train_loader = DataLoader(
        train_ds,
        batch_size=cfg.train.batch_size,
        shuffle=True,
        collate_fn=collate_graphs,
        generator=torch.Generator().manual_seed(cfg.train.seed),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg.train.batch_size,
        shuffle=False,
        collate_fn=collate_graphs,
        generator=torch.Generator().manual_seed(cfg.train.seed + 1),
    )
    model = build_model(model_name, cfg.train.hidden_dim, cfg.train.message_passes).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.train.lr, weight_decay=cfg.train.weight_decay)

    num_epochs = epochs_for_model(cfg, model_name)
    patience = cfg.train.early_stopping_patience
    min_delta = cfg.train.early_stopping_min_delta

    best_val = float("inf")
    best_epoch = 0
    patience_counter = 0
    best_mode = "min"
    last_rollout_score = None
    last_rollout_key = None
    best_rollout_key = None
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    best_ckpt = out_path / f"{model_name}_best.pt"
    last_ckpt = out_path / f"{model_name}_last.pt"
    legacy_ckpt = out_path / f"{model_name}.pt"
    rollout_candidates: list[dict[str, object]] = []

    warmup = 0

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
            last_rollout_key = rollout_validation_key(rollout_summary)

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
            best_rollout_key = None
            patience_counter = 0

        if in_warmup:
            update_best = True
            best_val = tracking
            best_epoch = epoch
            patience_counter = 0
        elif use_rollout_metric:
            if metric_ready:
                improved = (
                    best_rollout_key is None
                    or (last_rollout_key is not None and last_rollout_key > best_rollout_key)
                    or (
                        last_rollout_key is not None
                        and last_rollout_key == best_rollout_key
                        and tracking > (best_val + min_delta)
                    )
                )
                if improved:
                    best_val = tracking
                    best_rollout_key = last_rollout_key
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
        else:
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

        if (
            ran_rollout
            and not in_warmup
            and use_rollout_metric
            and last_rollout_score is not None
            and np.isfinite(last_rollout_score)
        ):
            maybe_record_rollout_candidate(
                records=rollout_candidates,
                out_path=out_path,
                model_name=model_name,
                epoch=epoch,
                score_key=last_rollout_key if last_rollout_key is not None else tuple(),
                score=last_rollout_score,
                state=state,
                topk=int(cfg.train.rollout_val_topk_checkpoints),
            )

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

    if rollout_candidates:
        rechecked_state, rechecked_summary, rechecked_score = recheck_rollout_candidates(
            model_name,
            cfg,
            model,
            rollout_candidates,
            out_path,
            device,
        )
        if rechecked_state is not None and rechecked_score is not None:
            rechecked_state = dict(rechecked_state)
            rechecked_state["best_val"] = float(rechecked_score)
            rechecked_state["best_metric"] = "rollout_recheck_score"
            rechecked_state["best_metric_mode"] = "max"
            rechecked_state["validation_summary"] = rechecked_summary
            torch.save(rechecked_state, best_ckpt)
            torch.save(rechecked_state, legacy_ckpt)
            print(
                f"[{model_name}] rollout recheck selected epoch {rechecked_state.get('epoch', 0):02d} "
                f"with rollout_recheck_score={rechecked_score:.4f}"
            )
        for record in rollout_candidates:
            candidate_path = Path(record["path"])
            if candidate_path.exists():
                candidate_path.unlink()

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
