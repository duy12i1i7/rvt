"""OPEN_LOOP_V3_STUDY_CHECKPOINT_ENVELOPE_V1 -- artifact provenance, not authority.

The existing FD24 checkpoint contract accepts only ``RVTFD24LocalModel``. It
therefore represents M2 exactly and cannot represent M1 at all. Forcing M1 into
it would mean loosening a validated schema to admit a model it was never written
for, which is a worse outcome than adding a thin family-neutral wrapper.

So this envelope wraps rather than replaces:

* for M2 it BINDS the existing FD24 checkpoint payload and its hashes, and calls
  the existing builder unchanged -- no FD24 validation is relaxed;
* for M1 it defines a small closed schema with the same deterministic
  state-dict hashing.

The envelope defines no scientific semantics. It selects nothing, scores nothing
and changes no selection rule; it records which frozen authority a given
parameter blob was produced under. Stage 5B may only mint envelopes marked
``synthetic-mechanical`` / ``shadow-disabled``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import torch

from ..fd24.checkpoint import (
    FD24CheckpointError, build_fd24_checkpoint, canonical_state_dict_hash,
)
from ..fd24.model import RVTFD24LocalModel
from ..phase8.common import attach_canonical_hash
from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from .authority import (
    M1_INPUT_CONTRACT_V1_SHA256, M2_MODEL_CONFIG_SHA256,
    PREREGISTRATION_V1_SHA256, TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256,
)
from .m1 import M1_HIDDEN_WIDTH, M1_INPUT_DIMENSION, M1LocalPredictor

STUDY_CHECKPOINT_ENVELOPE_SCHEMA_VERSION = "rvt-open-loop-v3-study-checkpoint-envelope/v1"
ENVELOPE_ROLE = "ARTIFACT_EXECUTION_PROVENANCE"
SYNTHETIC_MECHANICAL = "synthetic-mechanical"
SCIENTIFICALLY_TRAINED = "scientifically-trained"
SHADOW_DISABLED = "shadow-disabled"

M1_STATE_DICT_KEYS = (
    "network.0.bias", "network.0.weight", "network.2.bias", "network.2.weight",
)


class StudyCheckpointEnvelopeError(ValueError):
    """An envelope-contract violation that must fail closed."""


def _validated_state(model: torch.nn.Module) -> Dict[str, torch.Tensor]:
    return {name: tensor.detach().cpu().clone()
            for name, tensor in model.state_dict().items()}


def _m1_family_payload(model: M1LocalPredictor) -> Mapping[str, Any]:
    state = _validated_state(model)
    if tuple(sorted(state)) != M1_STATE_DICT_KEYS:
        raise StudyCheckpointEnvelopeError(
            f"unexpected M1 state dict keys: {tuple(sorted(state))}")
    if state["network.0.weight"].shape != (M1_HIDDEN_WIDTH, M1_INPUT_DIMENSION):
        raise StudyCheckpointEnvelopeError("M1 input width is not the frozen 56")
    if state["network.2.weight"].shape != (1, M1_HIDDEN_WIDTH):
        raise StudyCheckpointEnvelopeError("M1 hidden width is not the frozen 32")
    for tensor in state.values():
        if tensor.dtype != torch.float32:
            raise StudyCheckpointEnvelopeError("M1 parameters must be float32")
        if not bool(torch.isfinite(tensor).all()):
            raise StudyCheckpointEnvelopeError("M1 parameters must be finite")
    return {
        "family_schema_version": "rvt-open-loop-v3-m1-checkpoint/v1",
        "input_dimension": M1_INPUT_DIMENSION,
        "hidden_width": M1_HIDDEN_WIDTH,
        "m1_local_non_graph_input_contract_v1_sha256": M1_INPUT_CONTRACT_V1_SHA256,
        "state_dict_sha256": canonical_state_dict_hash(state),
        "state_dict": state,
    }


def build_study_checkpoint_envelope(
    *, family: str, model: torch.nn.Module, source_commit: str,
    training_seed: int, learning_rate: float, weight_decay: float,
    refit_step: Optional[int], training_status: str,
    deployment_classification: str = SHADOW_DISABLED,
    runtime_config: Optional[RuntimeConfig] = None,
    hyperparameter_provenance: Optional[Mapping[str, Any]] = None,
    scientific_training_authorization: Optional[Mapping[str, Any]] = None,
) -> Mapping[str, Any]:
    """Build one envelope. Refuses a scientifically-trained mark without authority."""
    if family not in ("M1", "M2"):
        raise StudyCheckpointEnvelopeError("the study ladder has learned families M1 and M2")
    if training_status == SCIENTIFICALLY_TRAINED and not scientific_training_authorization:
        raise StudyCheckpointEnvelopeError(
            "a scientifically-trained envelope requires a scientific-training "
            "authorization artifact; none exists")
    if training_status not in (SYNTHETIC_MECHANICAL, SCIENTIFICALLY_TRAINED, "untrained"):
        raise StudyCheckpointEnvelopeError(f"unknown training status {training_status!r}")
    if deployment_classification != SHADOW_DISABLED and (
            training_status != SCIENTIFICALLY_TRAINED):
        raise StudyCheckpointEnvelopeError(
            "only a scientifically-trained checkpoint may leave shadow-disabled")

    if family == "M2":
        if not isinstance(model, RVTFD24LocalModel):
            raise StudyCheckpointEnvelopeError("M2 requires RVTFD24LocalModel")
        if runtime_config is None:
            raise StudyCheckpointEnvelopeError("M2 requires the runtime configuration")
        # The existing builder is called unchanged; its validation is not relaxed.
        try:
            payload = build_fd24_checkpoint(
                model, runtime_config, source_commit,
                training_status=training_status,
                deployment_classification=deployment_classification)
        except FD24CheckpointError as exc:
            raise StudyCheckpointEnvelopeError(
                f"the existing FD24 checkpoint contract refused this model: {exc}") from exc
        if payload["model_config_sha256"] != M2_MODEL_CONFIG_SHA256:
            raise StudyCheckpointEnvelopeError(
                "M2 must use the frozen model configuration")
        family_block = {
            "family_schema_version": payload["checkpoint_schema_version"],
            "fd24_model_config_sha256": payload["model_config_sha256"],
            "fd24_state_dict_sha256": payload["state_dict_sha256"],
            "fd24_checkpoint": payload,
        }
        state_hash = payload["state_dict_sha256"]
        runtime_hash = payload["runtime_config_sha256"]
    else:
        if not isinstance(model, M1LocalPredictor):
            raise StudyCheckpointEnvelopeError("M1 requires M1LocalPredictor")
        family_block = _m1_family_payload(model)
        state_hash = family_block["state_dict_sha256"]
        runtime_hash = (canonical_runtime_hash(runtime_config)
                        if runtime_config is not None else None)

    body = {
        "schema_version": STUDY_CHECKPOINT_ENVELOPE_SCHEMA_VERSION,
        "role": ENVELOPE_ROLE,
        "scientific_authority": False,
        "open_loop_v3_recoverability_predictor_preregistration_v1_sha256":
            PREREGISTRATION_V1_SHA256,
        "open_loop_v3_train_internal_fold_manifest_v1_sha256":
            TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256,
        "model_family": family,
        "family_schema_version": family_block["family_schema_version"],
        "state_dict_sha256": state_hash,
        "runtime_config_sha256": runtime_hash,
        "source_commit": source_commit,
        "training_seed": int(training_seed),
        "hyperparameters": {"optimizer": "AdamW",
                            "learning_rate": float(learning_rate),
                            "weight_decay": float(weight_decay)},
        "refit_step": None if refit_step is None else int(refit_step),
        "hyperparameter_provenance": dict(hyperparameter_provenance or {}),
        "training_status": training_status,
        "deployment_classification": deployment_classification,
        "selection_rule_changed_by_this_envelope": False,
    }
    if family == "M1":
        body["m1_local_non_graph_input_contract_v1_sha256"] = M1_INPUT_CONTRACT_V1_SHA256
    else:
        body["fd24_model_config_sha256"] = M2_MODEL_CONFIG_SHA256
    envelope = dict(attach_canonical_hash(
        body, "open_loop_v3_study_checkpoint_envelope_v1_sha256"))
    envelope["family_payload"] = family_block
    return envelope


def save_study_checkpoint_envelope(path: Path | str,
                                   envelope: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    torch.save(dict(envelope), temporary)
    temporary.replace(destination)


def load_study_checkpoint_envelope(path: Path | str) -> Mapping[str, Any]:
    """Load and re-verify. A corrupted state dict fails closed."""
    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping):
        raise StudyCheckpointEnvelopeError("envelope root must be an object")
    if payload.get("schema_version") != STUDY_CHECKPOINT_ENVELOPE_SCHEMA_VERSION:
        raise StudyCheckpointEnvelopeError("unknown study checkpoint envelope schema")
    family_block = payload.get("family_payload")
    if not isinstance(family_block, Mapping):
        raise StudyCheckpointEnvelopeError("envelope carries no family payload")
    if payload["model_family"] == "M1":
        state = family_block["state_dict"]
    else:
        state = family_block["fd24_checkpoint"]["state_dict"]
    recomputed = canonical_state_dict_hash(state)
    if recomputed != payload["state_dict_sha256"]:
        raise StudyCheckpointEnvelopeError(
            "envelope state-dict hash does not recompute; the parameters on disk "
            "are not the parameters that were recorded")
    if payload["model_family"] == "M2" and (
            recomputed != family_block["fd24_state_dict_sha256"]):
        raise StudyCheckpointEnvelopeError("FD24 payload hash disagrees with the envelope")
    return payload


def restore_m1(envelope: Mapping[str, Any]) -> M1LocalPredictor:
    if envelope["model_family"] != "M1":
        raise StudyCheckpointEnvelopeError("this envelope does not carry an M1 model")
    model = M1LocalPredictor()
    model.load_state_dict(envelope["family_payload"]["state_dict"])
    return model
