"""Load and verify the frozen open-loop V3 authority artifacts.

Every constant here is a value frozen by Stage 5A-R. They are compared against
the artifacts on disk rather than trusted, and a mismatch raises: an
implementation that silently ran against a different preregistration would be
worse than one that refused to run at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..phase8.common import verify_canonical_hash

PREREGISTRATION_V1_SHA256 = (
    "8619ac4c8a60740209d826910d9002d12d63f825886b4869e08c883024e7dbf6")
TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256 = (
    "e648a4d42064929ded390fcbf06eb2da9ec6569809d58ae75a26fa3d0e0b6ba2")
M1_INPUT_CONTRACT_V1_SHA256 = (
    "d017de30f1ce65d0c7bc84551124cebb5781b05c2ece6b8e82708a87fc4fb4fd")
FAMILY_SELECTION_RULE_V1_SHA256 = (
    "f65e60fee5b5c0e7249b3594a25d4cb54bf826c19be2cf3aad75df5f1b72f1f5")
M2_MODEL_CONFIG_SHA256 = (
    "44cc7176a38e79d938952398ccb08d7fe2646643ddfe6dec08822a60de9fb1a3")
OFFICIAL_V3_TRAIN_SEAL_ROOT = (
    "3a281b0ff8647302ec7aece2f4a061111aa8ef87c743d5d6626ebed741615c22")
OFFICIAL_V3_VALIDATION_SEAL_ROOT = (
    "770957243df01a4077ef331e55b1e6ee892b64f2c410112e656ed38832fd8d84")

_RECORDS = Path("results/rvt_fd24")
_FILES = {
    "preregistration": (
        "open_loop_v3_recoverability_predictor_preregistration_v1.json",
        "open_loop_v3_recoverability_predictor_preregistration_v1_sha256",
        PREREGISTRATION_V1_SHA256),
    "fold_manifest": (
        "open_loop_v3_train_internal_fold_manifest_v1.json",
        "open_loop_v3_train_internal_fold_manifest_v1_sha256",
        TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256),
    "m1_contract": (
        "open_loop_v3_m1_input_contract_v1.json",
        "m1_local_non_graph_input_contract_v1_sha256",
        M1_INPUT_CONTRACT_V1_SHA256),
    "selection_rule": (
        "open_loop_v3_family_selection_rule_v1.json",
        "open_loop_v3_family_selection_rule_v1_sha256",
        FAMILY_SELECTION_RULE_V1_SHA256),
}


class OpenLoopV3AuthorityError(ValueError):
    """A frozen open-loop authority artifact is missing, altered or unverifiable."""


@dataclass(frozen=True)
class OpenLoopV3Authority:
    """The four frozen documents, each verified against its frozen root."""

    preregistration: Mapping[str, Any]
    fold_manifest: Mapping[str, Any]
    m1_contract: Mapping[str, Any]
    selection_rule: Mapping[str, Any]

    @property
    def permissions(self) -> Mapping[str, Any]:
        return self.preregistration["permissions"]

    @property
    def scientific_training_authorized(self) -> bool:
        return bool(self.permissions["scientific_training_authorized"])

    @property
    def validation_unblinding_authorized(self) -> bool:
        return bool(self.permissions["validation_unblinding_authorized"])


def load_open_loop_v3_authority(root: Path) -> OpenLoopV3Authority:
    """Read and verify all four artifacts, or raise."""
    resolved = {}
    for key, (name, field, expected) in _FILES.items():
        path = Path(root) / _RECORDS / name
        if not path.exists():
            raise OpenLoopV3AuthorityError(f"frozen authority artifact missing: {name}")
        document = json.loads(path.read_text(encoding="ascii"))
        if document.get(field) != expected:
            raise OpenLoopV3AuthorityError(
                f"{name} declares {str(document.get(field))[:16]}..., expected "
                f"{expected[:16]}...")
        if not verify_canonical_hash(document, field):
            raise OpenLoopV3AuthorityError(f"{name} canonical root does not recompute")
        resolved[key] = document
    prereg = resolved["preregistration"]
    if prereg["status"] != "FROZEN":
        raise OpenLoopV3AuthorityError("the preregistration is not FROZEN")
    if prereg["authoritative_scope"] != "OPEN_LOOP_V3_RECOVERABILITY_PREDICTOR_STUDY":
        raise OpenLoopV3AuthorityError("unexpected preregistration scope")
    # The parent must bind the children it claims to bind.
    if (prereg["R6_train_internal_folds"]
            ["open_loop_v3_train_internal_fold_manifest_v1_sha256"]
            != TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256):
        raise OpenLoopV3AuthorityError("preregistration does not bind this fold manifest")
    if (prereg["R8_model_ladder"]["M1"]["m1_local_non_graph_input_contract_v1_sha256"]
            != M1_INPUT_CONTRACT_V1_SHA256):
        raise OpenLoopV3AuthorityError("preregistration does not bind this M1 contract")
    if (prereg["R17_family_selection_rule"]
            ["open_loop_v3_family_selection_rule_v1_sha256"]
            != FAMILY_SELECTION_RULE_V1_SHA256):
        raise OpenLoopV3AuthorityError("preregistration does not bind this selection rule")
    if (prereg["R8_model_ladder"]["M2"]["fd24_model_config_sha256"]
            != M2_MODEL_CONFIG_SHA256):
        raise OpenLoopV3AuthorityError("preregistration does not bind this M2 config")
    return OpenLoopV3Authority(
        preregistration=prereg, fold_manifest=resolved["fold_manifest"],
        m1_contract=resolved["m1_contract"],
        selection_rule=resolved["selection_rule"])
