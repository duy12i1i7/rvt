"""RB-21 operational qualification helpers.

This package is deliberately downstream of the frozen scientific runtime.  It
owns scheduling, measurement, persistence and authorization checks; it does not
define a controller, selector, target, rollout horizon or scientific identity.
"""

from .rb21_manifest import (
    RB19_PROVENANCE_ROOT,
    RB20_REPRODUCTION_HASH,
    TARGET_V4_HASH,
    build_benchmark_manifest,
    build_target_benchmark_manifest,
    capture_environment,
)
from .rb21_units import (
    RecoverabilityAtomicUnit,
    ResidualAtomicUnit,
    ThreadSettings,
    scientific_semantic_digest,
)

__all__ = [
    "RB19_PROVENANCE_ROOT",
    "RB20_REPRODUCTION_HASH",
    "TARGET_V4_HASH",
    "RecoverabilityAtomicUnit",
    "ResidualAtomicUnit",
    "ThreadSettings",
    "build_benchmark_manifest",
    "build_target_benchmark_manifest",
    "capture_environment",
    "scientific_semantic_digest",
]
