"""RB21P cross-platform numerical portability audit helpers."""

from .audit import (
    audit_authoritative_layouts,
    audit_fd24_batch_numerics,
    audit_fd24_cuda_forward,
    audit_rb20_semantic_replay,
)

__all__ = [
    "audit_authoritative_layouts",
    "audit_fd24_batch_numerics",
    "audit_fd24_cuda_forward",
    "audit_rb20_semantic_replay",
]
