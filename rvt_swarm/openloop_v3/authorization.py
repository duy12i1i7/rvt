"""Fail-closed authorization for the open-loop V3 training driver.

The default is DENY. Official scientific training is not something the driver
can be talked into by a flag, an environment variable or a warning that the user
scrolled past: it requires an authorization artifact that does not exist yet, and
until one does, every scientific path raises.

Three execution modes:

``inspect``     structural, read-only. May touch official TRAIN. Constructs no
                optimizer and takes no gradient.
``mechanical``  a real optimization loop on SYNTHETIC data with seed 0 only.
                Refuses official data outright.
``scientific``  the official TRAIN fit. Requires the authorization artifact.

Dataset classification is deliberately made from PATH, SPLIT and AUTHORITY
metadata -- ``ops/authority.json``, the presence of a ``seal/`` directory -- and
never from scientific records. Refusing a dataset must not require reading the
outcomes one is refusing to read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .authority import (
    OFFICIAL_V3_TRAIN_SEAL_ROOT, PREREGISTRATION_V1_SHA256,
)

MODE_INSPECT = "inspect"
MODE_MECHANICAL = "mechanical"
MODE_SCIENTIFIC = "scientific"
EXECUTION_MODES = (MODE_INSPECT, MODE_MECHANICAL, MODE_SCIENTIFIC)

ORIGIN_SYNTHETIC = "SYNTHETIC"
ORIGIN_OFFICIAL = "OFFICIAL"

SPLIT_TRAIN = "v3_train"
SPLIT_VALIDATION = "v3_validation"

#: Splits and domains that may never be used as training data by this driver.
PROTECTED_SPLIT_TOKENS = (
    "v3_validation", "validation", "reserve", "unused_reserve", "n24",
    "study_b", "near_final", "near-final", "final_test", "final",
)

MECHANICAL_SEED = 0
FROZEN_SCIENTIFIC_SEEDS = (11, 29, 47)


class OpenLoopV3AuthorizationError(PermissionError):
    """The driver refused an action it is not authorized to take."""


class ScientificTrainingNotAuthorized(OpenLoopV3AuthorizationError):
    """No valid scientific-training authorization artifact exists."""


class ValidationAccessRefused(OpenLoopV3AuthorizationError):
    """A VALIDATION dataset was offered to a training path."""


class ProtectedDomainRefused(OpenLoopV3AuthorizationError):
    """A reserve / N24 / Study B / near-final / final dataset was offered."""


class OfficialOptimizationRefused(OpenLoopV3AuthorizationError):
    """Official data reached an optimizer without scientific authorization."""


@dataclass(frozen=True)
class DatasetClassification:
    """What a dataset root is, decided from metadata only."""

    origin: str
    v3_split: Optional[str]
    evidence: str
    sealed: bool


def classify_dataset_root(root: Path, *, declared_split: Optional[str] = None,
                          ) -> DatasetClassification:
    """Classify without opening a single scientific record."""
    path = Path(root)
    authority = path / "ops" / "authority.json"
    sealed = (path / "seal").is_dir()
    if authority.is_file():
        document = json.loads(authority.read_text())
        return DatasetClassification(
            origin=ORIGIN_OFFICIAL, v3_split=str(document.get("v3_split")),
            evidence="ops/authority.json", sealed=sealed)
    if sealed:
        return DatasetClassification(
            origin=ORIGIN_OFFICIAL, v3_split=declared_split,
            evidence="seal/ directory present", sealed=True)
    lowered = str(path).lower()
    for token in ("official-v3-train", "official-v3-validation", "official"):
        if token in lowered:
            return DatasetClassification(
                origin=ORIGIN_OFFICIAL, v3_split=declared_split,
                evidence=f"path contains {token!r}", sealed=sealed)
    return DatasetClassification(
        origin=ORIGIN_SYNTHETIC, v3_split=declared_split,
        evidence="no official authority, seal or path marker", sealed=sealed)


def _reject_protected(classification: DatasetClassification, root: Path) -> None:
    haystack = " ".join(
        part for part in (str(root).lower(), str(classification.v3_split or "").lower())
    )
    for token in PROTECTED_SPLIT_TOKENS:
        if token in haystack:
            if token in ("v3_validation", "validation"):
                raise ValidationAccessRefused(
                    "the open-loop TRAIN development driver has no VALIDATION path; "
                    "VALIDATION is unblinded only by a separately authorized "
                    f"evaluation stage (refused on {token!r})")
            raise ProtectedDomainRefused(
                f"protected domain {token!r} may never be used as training data")


@dataclass(frozen=True)
class ScientificTrainingAuthorization:
    """The artifact a future stage must produce before official training.

    None exists. The class is defined so the driver can name exactly what would
    have to be true, and so the refusal path is testable.
    """

    preregistration_sha256: str
    train_seal_root: str
    implementation_commit: str
    training_image_digest: str
    stage5b_qualification_root: str
    scientific_training_authorized: bool

    def validate(self) -> None:
        if not self.scientific_training_authorized:
            raise ScientificTrainingNotAuthorized(
                "the authorization artifact does not set "
                "scientific_training_authorized = true")
        if self.preregistration_sha256 != PREREGISTRATION_V1_SHA256:
            raise ScientificTrainingNotAuthorized(
                "the authorization binds a different preregistration")
        if self.train_seal_root != OFFICIAL_V3_TRAIN_SEAL_ROOT:
            raise ScientificTrainingNotAuthorized(
                "the authorization binds a different TRAIN seal")
        for name in ("implementation_commit", "training_image_digest",
                     "stage5b_qualification_root"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ScientificTrainingNotAuthorized(
                    f"the authorization does not bind {name}")


def require_optimization_authorization(
    *, mode: str, dataset_root: Path, seed: int,
    classification: Optional[DatasetClassification] = None,
    authorization: Optional[ScientificTrainingAuthorization] = None,
    declared_split: Optional[str] = None,
) -> DatasetClassification:
    """The single gate every optimizer construction must pass. Default: deny."""
    if mode not in EXECUTION_MODES:
        raise OpenLoopV3AuthorizationError(f"unknown execution mode {mode!r}")
    if mode == MODE_INSPECT:
        raise OpenLoopV3AuthorizationError(
            "inspect mode constructs no optimizer; it must not reach this gate")
    resolved = classification or classify_dataset_root(
        dataset_root, declared_split=declared_split)
    _reject_protected(resolved, Path(dataset_root))

    if mode == MODE_MECHANICAL:
        if resolved.origin != ORIGIN_SYNTHETIC:
            raise OfficialOptimizationRefused(
                "mechanical qualification runs on synthetic fixtures only; "
                f"this root classifies as {resolved.origin} via {resolved.evidence}")
        if int(seed) != MECHANICAL_SEED:
            raise OpenLoopV3AuthorizationError(
                f"mechanical qualification uses seed {MECHANICAL_SEED} only; "
                f"seed {seed} is not permitted")
        return resolved

    # mode == MODE_SCIENTIFIC
    if authorization is None:
        raise ScientificTrainingNotAuthorized(
            "official scientific training requires an authorization artifact "
            "binding the preregistration root, the TRAIN seal root, the qualified "
            "implementation commit, the qualified training image and the Stage-5B "
            "qualification root. No such artifact exists.")
    authorization.validate()
    if resolved.origin != ORIGIN_OFFICIAL or resolved.v3_split != SPLIT_TRAIN:
        raise OfficialOptimizationRefused(
            "scientific training runs on official v3_train only")
    if int(seed) not in FROZEN_SCIENTIFIC_SEEDS:
        raise OpenLoopV3AuthorizationError(
            f"seed {seed} is not one of the frozen scientific seeds "
            f"{FROZEN_SCIENTIFIC_SEEDS}")
    return resolved


def require_training_dataset(root: Path, *, declared_split: Optional[str] = None,
                             ) -> DatasetClassification:
    """Classify a dataset offered as TRAINING data and refuse the forbidden ones."""
    resolved = classify_dataset_root(root, declared_split=declared_split)
    _reject_protected(resolved, Path(root))
    return resolved
