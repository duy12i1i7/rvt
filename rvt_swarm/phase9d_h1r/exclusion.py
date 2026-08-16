"""The permanent design-pilot exclusion set and its guard.

Every source identity touched while *designing* Protocol V2 is burned: it may
never appear in official V2 TRAIN, VALIDATION or final evaluation data. The
exclusion set is a committed artifact and the guard is a hard failure, not a
warning, so a future official generator cannot quietly reuse a pilot identity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Set

from ..phase8.common import sha256_document

EXCLUSION_SCHEMA_VERSION = "rvt-phase9d-h1r-design-pilot-exclusion-set/v1"
DEFAULT_EXCLUSION_PATH = Path(
    "results/rvt_fd24/phase9d_h1r_design_pilot_exclusion_set_v1.json")

#: The identity dimensions that make a source episode unique. Seeds are part of
#: the identity because the same layout under a different seed stream is a
#: different realized trajectory.
IDENTITY_KEY = ("study", "split", "family", "team_size", "layout_id",
                "source_policy", "episode_id", "seed_identity")


class DesignPilotReuseError(RuntimeError):
    """An official V2 job tried to reuse a design-pilot source identity."""


def design_pilot_identity(**fields: Any) -> str:
    missing = [name for name in IDENTITY_KEY if name not in fields]
    if missing:
        raise ValueError(f"design-pilot identity is missing {missing}")
    extra = [name for name in fields if name not in IDENTITY_KEY]
    if extra:
        raise ValueError(f"design-pilot identity must not carry {extra}")
    payload = {name: fields[name] for name in IDENTITY_KEY}
    payload["team_size"] = int(payload["team_size"])
    return sha256_document(payload)


def load_exclusion_set(path: Optional[Path] = None) -> Set[str]:
    path = Path(path or DEFAULT_EXCLUSION_PATH)
    if not path.exists():
        return set()
    document = json.loads(path.read_text(encoding="ascii"))
    return {str(entry["design_pilot_identity_sha256"])
            for entry in document.get("excluded_identities", [])}


def assert_not_design_pilot_identity(
    identity_or_fields: Any, *, path: Optional[Path] = None,
    excluded: Optional[Iterable[str]] = None,
) -> str:
    """Fail closed if this source identity was consumed by the V2 design pilot."""
    if isinstance(identity_or_fields, Mapping):
        identity = design_pilot_identity(**dict(identity_or_fields))
    else:
        identity = str(identity_or_fields)
    burned = set(excluded) if excluded is not None else load_exclusion_set(path)
    if identity in burned:
        raise DesignPilotReuseError(
            f"source identity {identity[:16]}... was consumed by the Protocol V2 "
            "design pilot and is permanently excluded from official V2 data")
    return identity


def build_exclusion_document(entries: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Canonical exclusion artifact from the identities a pilot actually used."""
    excluded = []
    for entry in entries:
        fields = {name: entry[name] for name in IDENTITY_KEY}
        excluded.append({**fields, "team_size": int(fields["team_size"]),
                         "design_pilot_identity_sha256": design_pilot_identity(**fields)})
    excluded.sort(key=lambda item: item["design_pilot_identity_sha256"])
    identities = [item["design_pilot_identity_sha256"] for item in excluded]
    if len(set(identities)) != len(identities):
        raise ValueError("design-pilot exclusion set contains duplicate identities")
    return {
        "schema_version": EXCLUSION_SCHEMA_VERSION,
        "purpose": ("source identities consumed while designing Recoverability "
                    "Protocol V2; permanently excluded from official V2 TRAIN, "
                    "VALIDATION and final evaluation"),
        "permanent": True,
        "identity_key": list(IDENTITY_KEY),
        "excluded_identity_count": len(excluded),
        "excluded_identities": excluded,
        "study_a_n24_identities": 0,
        "study_b_identities": 0,
        "final_test_identities": 0,
    }
