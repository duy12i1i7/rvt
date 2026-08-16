"""Fixed-budget V2 source-manifest compilation.

The manifest is fixed prospectively: a compiled V2 source manifest declares
exactly the frozen source-episode budget, caps selected events at K per
episode, and can never be refilled because an episode turned out to have
`M < K`. Nothing here runs an episode, evaluates a candidate or authorizes
generation -- it compiles and validates the plan.

Fail-closed rules, all of them hard errors rather than warnings:

* the episode count must equal the frozen budget exactly;
* no design-pilot identity may appear;
* no sealed domain (Study-A N=24, Study B, final test) may appear;
* no outcome-dependent stopping rule may be attached.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Set

from ..phase8.common import sha256_document
from .acquisition_v2 import DEFAULT_K
from .exclusion import (
    DesignPilotReuseError, design_pilot_identity, load_exclusion_set,
)

MANIFEST_SCHEMA_VERSION = "rvt-recoverability-v2-source-manifest/v1"

#: Frozen Study-A source-episode budget, read from
#: `results/rvt_fd24/datasets/generation_budget_v1.json`. V2 changes source-state
#: acquisition, never the source-episode budget.
FROZEN_SOURCE_EPISODE_BUDGET: Mapping[str, int] = {"train": 1200, "validation": 300}

#: The frozen decision-event caps the budget also declares. K = 5 saturates them
#: exactly, so a V2 manifest can never exceed the frozen event budget.
FROZEN_DECISION_EVENT_CAP: Mapping[str, int] = {"train": 6000, "validation": 1500}

SEALED_STUDIES = ("study_a_n24_evaluation", "study_b_with_n24", "final_test")
SEALED_SPLITS = ("n24_evaluation", "final_test", "test")

FORBIDDEN_STOPPING_RULES = (
    "generate until 30 labels", "generate until class balance is good",
    "generate until a family reaches a target", "adaptive refill",
    "replenish missing events",
)


class ManifestCompilationError(ValueError):
    """A V2 manifest that must not be compiled."""


def _episode_identity(episode: Mapping[str, Any]) -> Dict[str, Any]:
    required = ("study", "split", "family", "team_size", "layout_id",
                "source_policy", "episode_id", "seed_identity")
    missing = [name for name in required if name not in episode]
    if missing:
        raise ManifestCompilationError(f"source episode is missing {missing}")
    return {name: episode[name] for name in required}


def compile_v2_source_manifest(
    split: str,
    episodes: Sequence[Mapping[str, Any]],
    *,
    protocol_sha256: str,
    exclusion_path: Optional[Any] = None,
    excluded: Optional[Iterable[str]] = None,
    k: int = DEFAULT_K,
) -> Dict[str, Any]:
    """Compile one fixed-budget V2 source manifest, or fail closed."""
    if split not in FROZEN_SOURCE_EPISODE_BUDGET:
        raise ManifestCompilationError(
            f"split {split!r} has no frozen V2 source-episode budget; sealed and "
            "unauthorized splits cannot be compiled")
    budget = FROZEN_SOURCE_EPISODE_BUDGET[split]
    if len(episodes) != budget:
        raise ManifestCompilationError(
            f"{split} manifest declares {len(episodes)} source episodes against the "
            f"frozen budget of {budget}; the budget is fixed prospectively and is "
            "never enlarged or reduced to reach an outcome")

    burned: Set[str] = (set(excluded) if excluded is not None
                        else load_exclusion_set(exclusion_path))
    identities: Dict[str, Dict[str, Any]] = {}
    for episode in episodes:
        fields = _episode_identity(episode)
        if str(fields["study"]) in SEALED_STUDIES:
            raise ManifestCompilationError(
                f"sealed study {fields['study']!r} may not enter a V2 manifest")
        if str(fields["split"]) in SEALED_SPLITS:
            raise ManifestCompilationError(
                f"sealed split {fields['split']!r} may not enter a V2 manifest")
        if int(fields["team_size"]) == 24:
            raise ManifestCompilationError(
                "N=24 is sealed for Study-A zero-shot evaluation and may not enter a "
                "V2 training or validation manifest")
        if str(fields["split"]) != split:
            raise ManifestCompilationError(
                f"episode declares split {fields['split']!r} in a {split!r} manifest")
        identity = design_pilot_identity(**fields)
        if identity in burned:
            raise DesignPilotReuseError(
                f"source identity {identity[:16]}... was consumed by the Protocol V2 "
                "design pilot and is permanently excluded from official V2 data")
        if identity in identities:
            raise ManifestCompilationError(
                f"duplicate source-episode identity {identity[:16]}...")
        identities[identity] = fields

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "split": split,
        "source_acquisition_protocol_sha256": protocol_sha256,
        "acquisition_rule": "REALIZED_TRAJECTORY_UNIFORM_K",
        "K": int(k),
        "source_episodes": budget,
        "maximum_selected_source_events": budget * int(k),
        "frozen_decision_event_cap": FROZEN_DECISION_EVENT_CAP[split],
        "maximum_saturates_frozen_cap":
            budget * int(k) == FROZEN_DECISION_EVENT_CAP[split],
        "actual_selected_events_may_be_lower": True,
        "adaptive_refill_permitted": False,
        "outcome_dependent_stopping_permitted": False,
        "forbidden_stopping_rules": list(FORBIDDEN_STOPPING_RULES),
        "design_pilot_identities_excluded": len(burned),
        "episode_identity_sha256": sorted(identities),
        "sealed_studies_present": 0,
        "n24_episodes": 0,
        "authorizes_official_generation": False,
    }
    manifest["v2_source_manifest_sha256"] = sha256_document(manifest)
    return manifest
