from __future__ import annotations

from pathlib import Path
from typing import Dict

import torch

from .config import Config, TOPOLOGY_IDS
from .dataset import build_graph
from .models import build_model
from .safety import choose_counterfactual_topology, simple_recover_shield


LEARNED_METHODS = {"rvt_swarm", "gnn_only", "instant_cert"}


def is_learned_method(method: str) -> bool:
    return method in LEARNED_METHODS


def batch_from_obs(obs: Dict, cfg: Config, device: torch.device) -> Dict[str, torch.Tensor]:
    node_x, edge_index, edge_attr = build_graph(obs, cfg)
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
    with torch.no_grad():
        out = model(batch)

    actions = out["actions"].cpu().numpy() * cfg.env.max_accel
    topology = 0
    recoverability = None
    uncertainty = None
    recoverability_scores = None

    if out["topology_logits"] is not None and cfg.method.use_topology:
        topology = choose_counterfactual_topology(
            obs,
            out["topology_logits"],
            out["recoverability_scores"],
            cfg,
            prev_topology,
            out.get("uncertainty"),
        )
    if out["recoverability_scores"] is not None:
        recoverability_scores = out["recoverability_scores"].squeeze(0).detach().cpu().numpy()
    if out["recoverability"] is not None and cfg.method.use_recoverability:
        uncertainty = (
            float(out["uncertainty"].mean().cpu().item())
            if out.get("uncertainty") is not None
            else 0.0
        )
        if recoverability_scores is not None and cfg.method.use_topology:
            recoverability = float(recoverability_scores[TOPOLOGY_IDS.index(topology)])
        else:
            recoverability = float(out["recoverability"].squeeze().cpu().item())
    if method in {"rvt_swarm", "instant_cert"}:
        actions = simple_recover_shield(
            actions,
            obs,
            cfg,
            recoverability,
            topology,
            recoverability_scores,
        )

    return {
        "actions": actions,
        "topology": topology,
        "recoverability": recoverability,
        "recoverability_scores": recoverability_scores,
        "uncertainty": uncertainty,
        "outputs": out,
    }
