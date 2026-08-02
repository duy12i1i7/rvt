"""Explicit compatibility namespace for the historical whole-swarm graph.

This module is prohibited in ``rvt_swarm.decentralized``. It preserves the
68-node-feature/11-edge-feature graph expected by historical checkpoints and
results without presenting that representation as robot-local.
"""

from __future__ import annotations

from typing import Dict

from .config import Config
from .dataset import build_graph, build_graph_arrays


LEGACY_GLOBAL_GRAPH_SCHEMA = "legacy-global-graph/68x11-unversioned"


def build_legacy_global_graph_arrays(obs: Dict, cfg: Config):
    """Historical joint-observation builder; never allowed in strict runtime."""
    return build_graph_arrays(obs, cfg)


def build_legacy_global_graph(obs: Dict, cfg: Config):
    """Historical tensor adapter retained for checkpoint reproducibility."""
    return build_graph(obs, cfg)
