"""Disabled-by-default diagnostic adapter for Phase 5 FD24 shadow inference.

Nothing in the current decision or controller path imports this module. Shadow
outputs are typed diagnostics and have no route to topology choice, lifecycle,
communication, or control actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import torch

from ..fd24.model import (
    RVTLocalBatchOutput,
    RVTFD24LocalModel,
    prepare_fd24_model_batch,
)
from .ego_graph_v2 import RobotLocalEgoGraph


@dataclass(frozen=True)
class FD24ShadowInferenceConfig:
    model_shadow_inference_enabled: bool = False
    include_diagnostic_embeddings: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.model_shadow_inference_enabled, bool):
            raise TypeError("shadow inference enabled flag must be Boolean")
        if not isinstance(self.include_diagnostic_embeddings, bool):
            raise TypeError("diagnostic embedding flag must be Boolean")


@dataclass(frozen=True)
class FD24ShadowInferenceResult:
    enabled: bool
    graph_count: int
    candidate_count: int
    output_shapes: Tuple[Tuple[str, Tuple[int, ...]], ...]
    all_valid: bool
    model_output: Optional[RVTLocalBatchOutput]


class FD24ShadowInferenceAdapter:
    """Evaluate canonical local graphs without changing runtime behavior."""

    def __init__(
        self,
        config: FD24ShadowInferenceConfig,
        model: Optional[RVTFD24LocalModel] = None,
    ) -> None:
        if not isinstance(config, FD24ShadowInferenceConfig):
            raise TypeError("shadow adapter requires FD24ShadowInferenceConfig")
        if model is not None and not isinstance(model, RVTFD24LocalModel):
            raise TypeError("shadow adapter model must be RVTFD24LocalModel")
        self.config = config
        self.model = model

    def evaluate(
        self,
        graphs: Sequence[RobotLocalEgoGraph],
    ) -> FD24ShadowInferenceResult:
        if not self.config.model_shadow_inference_enabled:
            return FD24ShadowInferenceResult(False, 0, 0, (), True, None)
        if self.model is None:
            raise RuntimeError("enabled shadow inference requires a model")
        local_batch = prepare_fd24_model_batch(graphs)
        prior_training = self.model.training
        self.model.eval()
        try:
            with torch.no_grad():
                output = self.model(
                    local_batch,
                    include_diagnostic_embedding=(
                        self.config.include_diagnostic_embeddings
                    ),
                )
        finally:
            self.model.train(prior_training)
        shapes = (
            ("recoverability_logit", tuple(output.recoverability_logit.shape)),
            ("residual_action", tuple(output.residual_action.shape)),
            ("candidate_topology_id", tuple(output.candidate_topology_id.shape)),
        )
        count = local_batch.n_graphs
        return FD24ShadowInferenceResult(
            enabled=True,
            graph_count=count,
            candidate_count=count,
            output_shapes=shapes,
            all_valid=bool(output.validity.all()),
            model_output=output,
        )
