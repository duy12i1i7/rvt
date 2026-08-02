from __future__ import annotations

from pathlib import Path
from typing import Dict

import torch

from .config import Config, LEARNED_TOPOLOGY_IDS
from .legacy_global_graph import build_legacy_global_graph
from .models import build_model
from .safety import choose_counterfactual_topology, simple_recover_shield


LEARNED_METHODS = {"rvt_swarm", "gnn_only", "instant_cert",
                   "rvt_simple_rank", "direct_topology_classifier",
                   "rvt_binary_recovery", "direct_keep_line_classifier",
                   "topology_agnostic_gnn"}


def is_learned_method(method: str) -> bool:
    return method in LEARNED_METHODS


def batch_from_obs(obs: Dict, cfg: Config, device: torch.device) -> Dict[str, torch.Tensor]:
    """Historical global-checkpoint adapter; not the strict local V2 path."""
    node_x, edge_index, edge_attr = build_legacy_global_graph(obs, cfg)
    return {
        "node_x": node_x.to(device),
        "edge_index": edge_index.to(device),
        "edge_attr": edge_attr.to(device),
        "batch_index": torch.zeros(node_x.shape[0], dtype=torch.long, device=device),
    }


def load_learned_model(method: str, cfg: Config, ckpt_dir: str, device: torch.device):
    if not is_learned_method(method):
        raise ValueError(f"{method} is not a learned method")
    model = build_model(
        method,
        cfg.train.hidden_dim,
        cfg.train.message_passes,
    ).to(device)
    ckpt = torch.load(Path(ckpt_dir) / f"{method}.pt", map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model


def infer_learned_action(
    method: str,
    obs: Dict,
    cfg: Config,
    model,
    prev_topology: int,
) -> Dict[str, object]:
    device = next(model.parameters()).device
    batch = batch_from_obs(obs, cfg, device)
    action_topology = None
    if method in ("rvt_swarm", "rvt_simple_rank") and not cfg.method.use_topology:
        action_topology = torch.zeros((1,), dtype=torch.long, device=device)
    with torch.no_grad():
        if action_topology is None:
            out = model(batch)
        else:
            out = model(batch, action_topology=action_topology)

    topology = 0
    recoverability = None
    uncertainty = None
    recoverability_scores = None
    audit = cfg.audit_config() if hasattr(cfg, "audit_config") else None
    topology_scores = out["recoverability_scores"] if cfg.method.use_recoverability else None
    if (
        topology_scores is not None
        and audit is not None
        and not audit.use_uncertainty_adjustment
        and out.get("raw_recoverability_scores") is not None
    ):
        # Diagnostic variant: rank on the raw score head, bypassing the
        # dispersion-scaled uncertainty adjustment. No retraining required.
        topology_scores = out["raw_recoverability_scores"]

    selector_stats: Dict[str, object] = {}
    if method in ("rvt_binary_recovery", "direct_keep_line_classifier"):
        from .binary_pilot import MODES as BIN_MODES
        probs = out["recovery_probs"].squeeze(0).detach().cpu().numpy()
        idx = int(probs.argmax())
        topology = BIN_MODES[idx]
        selector_stats = {"reason": "argmax_recovery_probability",
                          "probs": probs.tolist(), "selected": int(topology)}
        actions = out["actions_by_topology"][:, idx, :]
        recoverability_scores = probs
    elif method == "topology_agnostic_gnn":
        actions = out["actions"]
        topology = 0
    elif method == "rvt_simple_rank" and cfg.method.use_topology:
        # Direct argmax over the per-mode ranking score. No lexicographic key,
        # no tie-break levels, no uncertainty adjustment.
        scores_np = topology_scores.squeeze(0).detach().cpu().numpy()
        topology = LEARNED_TOPOLOGY_IDS[int(scores_np.argmax())]
        selector_stats = {"reason": "score_argmax_simple", "scores": scores_np.tolist(),
                          "selected": int(topology)}
        topo_idx = LEARNED_TOPOLOGY_IDS.index(topology)
        actions = out["actions_by_topology"][:, topo_idx, :]
    elif out["topology_logits"] is not None and cfg.method.use_topology:
        topology = choose_counterfactual_topology(
            obs,
            out["topology_logits"],
            topology_scores,
            cfg,
            prev_topology,
            out.get("uncertainty"),
            stats=selector_stats,
        )
        topo_idx = LEARNED_TOPOLOGY_IDS.index(topology)
        if out.get("actions_by_topology") is not None:
            actions = out["actions_by_topology"][:, topo_idx, :]
        elif hasattr(model, "decode_actions") and out.get("node_latent") is not None:
            topo_tensor = torch.tensor([topo_idx], device=device, dtype=torch.long)
            actions = model.decode_actions(out["node_latent"], batch["batch_index"], topo_tensor)
        else:
            actions = out["actions"]
    else:
        actions = out["actions"]
    actions = actions.detach().cpu().numpy() * cfg.env.max_accel
    if topology_scores is not None:
        recoverability_scores = topology_scores.squeeze(0).detach().cpu().numpy()
    if out["recoverability"] is not None and cfg.method.use_recoverability:
        uncertainty = (
            float(out["uncertainty"].mean().cpu().item())
            if out.get("uncertainty") is not None
            else 0.0
        )
        if recoverability_scores is not None and cfg.method.use_topology:
            recoverability = float(recoverability_scores[LEARNED_TOPOLOGY_IDS.index(topology)])
        else:
            recoverability = float(out["recoverability"].squeeze().cpu().item())
    safety_stats: Dict[str, float] = {}
    nominal_actions = actions.copy()
    if method in {"rvt_swarm", "instant_cert"}:
        actions = simple_recover_shield(
            actions,
            obs,
            cfg,
            recoverability,
            topology,
            recoverability_scores,
            stats=safety_stats,
        )

    return {
        "actions": actions,
        "nominal_actions": nominal_actions,
        "topology": topology,
        "recoverability": recoverability,
        "recoverability_scores": recoverability_scores,
        "uncertainty": uncertainty,
        "safety_stats": safety_stats,
        "selector_stats": selector_stats,
        "outputs": out,
    }
