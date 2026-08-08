"""Phase 8R -- pre-data residual expert specification completion.

Specification and enumeration only. No supervision producer, no data.
"""

from .residual_lattice import (
    CANDIDATE_COUNT,
    CANONICAL_MULTIPLIERS,
    RESIDUAL_CANDIDATE_LATTICE_SCHEMA_VERSION,
    RESIDUAL_EXPERT_V1_ID,
    RESIDUAL_EXPERT_V2_ID,
    canonical_lattice_hash,
    residual_candidate_lattice,
    zero_residual_index,
)
from .utility_v2 import (
    LOCAL_ACTION_INFORMATION,
    OFFLINE_LABEL_ORACLE,
    RESIDUAL_UTILITY_V2_SCHEMA_VERSION,
    UTILITY_INFORMATION_CLASS,
    ResidualUtilityError,
    clearance_slack,
    normalized_action_deviation,
    normalized_clearance_margin,
    normalized_formation_error,
    normalized_progress,
)

__all__ = [
    "CANDIDATE_COUNT",
    "CANONICAL_MULTIPLIERS",
    "LOCAL_ACTION_INFORMATION",
    "OFFLINE_LABEL_ORACLE",
    "RESIDUAL_CANDIDATE_LATTICE_SCHEMA_VERSION",
    "RESIDUAL_EXPERT_V1_ID",
    "RESIDUAL_EXPERT_V2_ID",
    "RESIDUAL_UTILITY_V2_SCHEMA_VERSION",
    "ResidualUtilityError",
    "UTILITY_INFORMATION_CLASS",
    "canonical_lattice_hash",
    "clearance_slack",
    "normalized_action_deviation",
    "normalized_clearance_margin",
    "normalized_formation_error",
    "normalized_progress",
    "residual_candidate_lattice",
    "zero_residual_index",
]
