"""Authoritative robot-local RVT-FD24 architecture namespace."""

from .configuration import (
    FD24_MODEL_CONFIG_SCHEMA_VERSION,
    ROBOT_LOCAL_ACTION_COMPONENTS,
    FD24ModelConfig,
    canonical_model_config_hash,
    residual_action_limits,
)
from .model import (
    FD24_MODEL_SCHEMA_VERSION,
    DirectLocalActionAblationHead,
    FD24LocalModelBatch,
    RVTLocalBatchOutput,
    RVTLocalCandidateOutput,
    RVTFD24LocalModel,
    prepare_fd24_model_batch,
)

__all__ = (
    "FD24_MODEL_CONFIG_SCHEMA_VERSION",
    "FD24_MODEL_SCHEMA_VERSION",
    "ROBOT_LOCAL_ACTION_COMPONENTS",
    "DirectLocalActionAblationHead",
    "FD24LocalModelBatch",
    "FD24ModelConfig",
    "RVTLocalBatchOutput",
    "RVTLocalCandidateOutput",
    "RVTFD24LocalModel",
    "canonical_model_config_hash",
    "prepare_fd24_model_batch",
    "residual_action_limits",
)
