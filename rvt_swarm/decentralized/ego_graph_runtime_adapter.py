"""Phase 4 compatibility adapter from current local runtime data to V2.

The active Phase 1 selector remains on ego-graph V1. This adapter gives future
model code one explicit entry point without changing controller actions,
topology scores, or commitment behavior in Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..runtime_configuration import RuntimeConfig
from .ego_graph_v2 import (
    RobotLocalEgoGraph,
    RobotLocalTopologyMetadata,
    build_robot_local_ego_graph,
)
from .system_model import RobotView


@dataclass(frozen=True)
class RobotLocalEgoGraphRuntimeAdapter:
    """Bind immutable mission data and adapt one current ``RobotView``."""

    runtime_config: RuntimeConfig
    local_topology: RobotLocalTopologyMetadata

    def build(
        self,
        view: RobotView,
        candidate_topology_id: int,
        observation_step: int,
    ) -> RobotLocalEgoGraph:
        return build_robot_local_ego_graph(
            view,
            self.runtime_config,
            self.local_topology,
            candidate_topology_id,
            observation_step,
        )
