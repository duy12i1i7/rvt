"""Execution-authority provenance guard.

Clean-room generation may run only under the exact frozen image, source commit
and dependency lock. Authority is the immutable image DIGEST; a mutable tag is
never authority.
"""
from __future__ import annotations

import re

CLEAN_ROOM_GENERATION_IMAGE_DIGEST = (
    "sha256:43d354ca94c0178f46edee5ef390a11012f8238787eb26e3eff49b8a6c81139a")
CLEAN_ROOM_SOURCE_COMMIT = "3eca3f1a3a480c40b46b46edcdae82a5af3698a9"
CLEAN_ROOM_DEPENDENCY_LOCK_ROOT = (
    "bbcbec1014f16906b7877f34b73cdd173794e4c83e1aa2733f739559ffc8bb3b")

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class ProvenanceError(ValueError):
    """An execution-provenance violation that must fail closed."""


def assert_execution_authority(*, image_reference: str, source_commit: str,
                               dependency_lock_root: str) -> None:
    """Refuse anything but the exact frozen execution authority."""
    if not _DIGEST.match(image_reference):
        raise ProvenanceError(
            f"image authority must be an immutable sha256 digest, not {image_reference!r}; "
            "a mutable tag is never authority")
    if image_reference != CLEAN_ROOM_GENERATION_IMAGE_DIGEST:
        raise ProvenanceError(f"unauthorized generation image digest {image_reference!r}")
    if not _COMMIT.match(source_commit):
        raise ProvenanceError(
            f"source commit must be the full 40-character hash, not {source_commit!r}")
    if source_commit != CLEAN_ROOM_SOURCE_COMMIT:
        raise ProvenanceError(f"unauthorized source commit {source_commit!r}")
    if dependency_lock_root != CLEAN_ROOM_DEPENDENCY_LOCK_ROOT:
        raise ProvenanceError(f"unauthorized dependency lock root {dependency_lock_root!r}")
