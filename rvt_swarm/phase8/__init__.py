"""Offline Phase 8 scientific-protocol contracts.

Nothing in this package is imported by the deployable decentralized runtime.
It defines immutable experiment specifications and qualification utilities only.
"""

from .common import (
    EXPERIMENT_PROTOCOL_SCHEMA_VERSION,
    PHASE8_APPROVED_BASE_COMMIT,
)

__all__ = (
    "EXPERIMENT_PROTOCOL_SCHEMA_VERSION",
    "PHASE8_APPROVED_BASE_COMMIT",
)
