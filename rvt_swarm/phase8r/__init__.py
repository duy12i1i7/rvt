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

__all__ = [
    "CANDIDATE_COUNT",
    "CANONICAL_MULTIPLIERS",
    "RESIDUAL_CANDIDATE_LATTICE_SCHEMA_VERSION",
    "RESIDUAL_EXPERT_V1_ID",
    "RESIDUAL_EXPERT_V2_ID",
    "canonical_lattice_hash",
    "residual_candidate_lattice",
    "zero_residual_index",
]
