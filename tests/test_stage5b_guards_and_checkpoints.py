"""Fail-closed authorization, the study checkpoint envelope, and offline isolation."""

import ast
import json
import pathlib

import pytest
import torch

from rvt_swarm.fd24.checkpoint import canonical_state_dict_hash
from rvt_swarm.fd24.configuration import FD24ModelConfig
from rvt_swarm.fd24.model import RVTFD24LocalModel
from rvt_swarm.openloop_v3.authority import (
    M2_MODEL_CONFIG_SHA256, PREREGISTRATION_V1_SHA256,
    OpenLoopV3AuthorityError, load_open_loop_v3_authority,
)
from rvt_swarm.openloop_v3.authorization import (
    MODE_INSPECT, MODE_MECHANICAL, MODE_SCIENTIFIC, OfficialOptimizationRefused,
    OpenLoopV3AuthorizationError, ProtectedDomainRefused,
    ScientificTrainingAuthorization, ScientificTrainingNotAuthorized,
    ValidationAccessRefused, classify_dataset_root,
    require_optimization_authorization, require_training_dataset,
)
from rvt_swarm.openloop_v3.envelope import (
    SHADOW_DISABLED, StudyCheckpointEnvelopeError, SYNTHETIC_MECHANICAL,
    build_study_checkpoint_envelope, load_study_checkpoint_envelope,
    restore_m1, save_study_checkpoint_envelope,
)
from rvt_swarm.openloop_v3.m1 import M1LocalPredictor
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG

REPO = pathlib.Path(__file__).resolve().parents[1]
COMMIT = "0" * 40


# ------------------------------------------------------------------ authority
def test_the_four_frozen_artifacts_verify():
    authority = load_open_loop_v3_authority(REPO)
    assert authority.preregistration["status"] == "FROZEN"
    assert authority.scientific_training_authorized is False
    assert authority.validation_unblinding_authorized is False
    assert authority.permissions["model_driver_implementation_authorized"] is True


def test_a_tampered_artifact_is_refused(tmp_path):
    records = tmp_path / "results" / "rvt_fd24"
    records.mkdir(parents=True)
    source = REPO / "results" / "rvt_fd24"
    for path in source.glob("open_loop_v3_*.json"):
        (records / path.name).write_text(path.read_text())
    victim = records / "open_loop_v3_m1_input_contract_v1.json"
    document = json.loads(victim.read_text())
    document["input_dimension"] = 57
    victim.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    with pytest.raises(OpenLoopV3AuthorityError):
        load_open_loop_v3_authority(tmp_path)


# ------------------------------------------------------------------- guards
def test_a_synthetic_directory_classifies_synthetic(tmp_path):
    classification = classify_dataset_root(tmp_path)
    assert classification.origin == "SYNTHETIC"


def test_official_authority_metadata_classifies_official(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"v3_split": "v3_train"}))
    classification = classify_dataset_root(tmp_path)
    assert classification.origin == "OFFICIAL"
    assert classification.v3_split == "v3_train"
    assert classification.evidence.startswith("ops/authority.json")
    assert "explicit v3_split" in classification.evidence


def test_a_seal_directory_alone_classifies_official(tmp_path):
    (tmp_path / "seal").mkdir()
    assert classify_dataset_root(tmp_path).origin == "OFFICIAL"


def test_validation_is_refused_without_reading_any_record(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"v3_split": "v3_validation"}))
    with pytest.raises(ValidationAccessRefused):
        require_training_dataset(tmp_path)
    # the refusal must not have needed a scientific record to exist
    assert not (tmp_path / "stage_b").exists()


@pytest.mark.parametrize("split", ["reserve", "n24", "study_b", "near_final", "final_test"])
def test_protected_domains_are_refused(tmp_path, split):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"v3_split": split}))
    with pytest.raises(ProtectedDomainRefused):
        require_training_dataset(tmp_path)


def test_mechanical_mode_refuses_official_data(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"v3_split": "v3_train"}))
    with pytest.raises(OfficialOptimizationRefused):
        require_optimization_authorization(
            mode=MODE_MECHANICAL, dataset_root=tmp_path, seed=0)


def test_mechanical_mode_refuses_the_frozen_scientific_seeds(tmp_path):
    for seed in (11, 29, 47):
        with pytest.raises(OpenLoopV3AuthorizationError):
            require_optimization_authorization(
                mode=MODE_MECHANICAL, dataset_root=tmp_path, seed=seed)


def test_mechanical_mode_accepts_synthetic_seed_zero(tmp_path):
    classification = require_optimization_authorization(
        mode=MODE_MECHANICAL, dataset_root=tmp_path, seed=0)
    assert classification.origin == "SYNTHETIC"


def test_scientific_mode_without_an_authorization_artifact_is_refused(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"v3_split": "v3_train"}))
    with pytest.raises(ScientificTrainingNotAuthorized):
        require_optimization_authorization(
            mode=MODE_SCIENTIFIC, dataset_root=tmp_path, seed=11)


def test_a_forged_authorization_that_denies_itself_is_refused(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"v3_split": "v3_train"}))
    forged = ScientificTrainingAuthorization(
        preregistration_sha256=PREREGISTRATION_V1_SHA256,
        train_seal_root="3a281b0ff8647302ec7aece2f4a061111aa8ef87c743d5d6626ebed741615c22",
        implementation_commit="abc", training_image_digest="sha256:abc",
        stage5b_qualification_root="root", scientific_training_authorized=False)
    with pytest.raises(ScientificTrainingNotAuthorized):
        require_optimization_authorization(
            mode=MODE_SCIENTIFIC, dataset_root=tmp_path, seed=11,
            authorization=forged)


def test_an_authorization_binding_the_wrong_preregistration_is_refused(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"v3_split": "v3_train"}))
    forged = ScientificTrainingAuthorization(
        preregistration_sha256="f" * 64,
        train_seal_root="3a281b0ff8647302ec7aece2f4a061111aa8ef87c743d5d6626ebed741615c22",
        implementation_commit="abc", training_image_digest="sha256:abc",
        stage5b_qualification_root="root", scientific_training_authorized=True)
    with pytest.raises(ScientificTrainingNotAuthorized):
        require_optimization_authorization(
            mode=MODE_SCIENTIFIC, dataset_root=tmp_path, seed=11,
            authorization=forged)


def test_inspect_mode_may_not_reach_the_optimizer_gate(tmp_path):
    with pytest.raises(OpenLoopV3AuthorizationError):
        require_optimization_authorization(
            mode=MODE_INSPECT, dataset_root=tmp_path, seed=0)


def test_an_unknown_mode_is_refused(tmp_path):
    with pytest.raises(OpenLoopV3AuthorizationError):
        require_optimization_authorization(
            mode="whatever", dataset_root=tmp_path, seed=0)


# --------------------------------------------------------------- envelopes
def _m2():
    torch.manual_seed(0)
    return RVTFD24LocalModel(FD24ModelConfig(), DEFAULT_RUNTIME_CONFIG)


def test_m1_envelope_round_trip(tmp_path):
    torch.manual_seed(0)
    model = M1LocalPredictor()
    envelope = build_study_checkpoint_envelope(
        family="M1", model=model, source_commit=COMMIT, training_seed=0,
        learning_rate=1e-4, weight_decay=0.0, refit_step=None,
        training_status=SYNTHETIC_MECHANICAL)
    path = tmp_path / "m1.pt"
    save_study_checkpoint_envelope(path, envelope)
    loaded = load_study_checkpoint_envelope(path)
    assert loaded["model_family"] == "M1"
    assert loaded["state_dict_sha256"] == envelope["state_dict_sha256"]
    restored = restore_m1(loaded)
    features = torch.zeros((2, 56), dtype=torch.float32)
    torch.testing.assert_close(model(features), restored(features),
                               rtol=0.0, atol=0.0)


def test_m2_envelope_wraps_the_existing_fd24_checkpoint(tmp_path):
    model = _m2()
    envelope = build_study_checkpoint_envelope(
        family="M2", model=model, source_commit=COMMIT, training_seed=0,
        learning_rate=3e-4, weight_decay=1e-4, refit_step=4000,
        training_status=SYNTHETIC_MECHANICAL, runtime_config=DEFAULT_RUNTIME_CONFIG)
    assert envelope["fd24_model_config_sha256"] == M2_MODEL_CONFIG_SHA256
    payload = envelope["family_payload"]["fd24_checkpoint"]
    assert payload["checkpoint_schema_version"] == "rvt-fd24-checkpoint/v1"
    assert payload["training_status"] == SYNTHETIC_MECHANICAL
    path = tmp_path / "m2.pt"
    save_study_checkpoint_envelope(path, envelope)
    loaded = load_study_checkpoint_envelope(path)
    assert loaded["state_dict_sha256"] == envelope["state_dict_sha256"]


def test_envelope_binds_the_frozen_preregistration():
    envelope = build_study_checkpoint_envelope(
        family="M1", model=M1LocalPredictor(), source_commit=COMMIT,
        training_seed=0, learning_rate=1e-4, weight_decay=0.0, refit_step=None,
        training_status=SYNTHETIC_MECHANICAL)
    assert envelope[
        "open_loop_v3_recoverability_predictor_preregistration_v1_sha256"
    ] == PREREGISTRATION_V1_SHA256
    assert envelope["role"] == "ARTIFACT_EXECUTION_PROVENANCE"
    assert envelope["scientific_authority"] is False
    assert envelope["selection_rule_changed_by_this_envelope"] is False


def test_a_corrupted_state_dict_fails_closed(tmp_path):
    envelope = dict(build_study_checkpoint_envelope(
        family="M1", model=M1LocalPredictor(), source_commit=COMMIT,
        training_seed=0, learning_rate=1e-4, weight_decay=0.0, refit_step=None,
        training_status=SYNTHETIC_MECHANICAL))
    payload = dict(envelope["family_payload"])
    state = dict(payload["state_dict"])
    state["network.0.bias"] = state["network.0.bias"] + 1.0
    payload["state_dict"] = state
    envelope["family_payload"] = payload
    path = tmp_path / "corrupt.pt"
    save_study_checkpoint_envelope(path, envelope)
    with pytest.raises(StudyCheckpointEnvelopeError):
        load_study_checkpoint_envelope(path)


def test_a_scientifically_trained_envelope_is_refused_without_authorization():
    with pytest.raises(StudyCheckpointEnvelopeError):
        build_study_checkpoint_envelope(
            family="M1", model=M1LocalPredictor(), source_commit=COMMIT,
            training_seed=11, learning_rate=1e-4, weight_decay=0.0,
            refit_step=1000, training_status="scientifically-trained")


def test_only_a_scientifically_trained_checkpoint_may_leave_shadow_disabled():
    with pytest.raises(StudyCheckpointEnvelopeError):
        build_study_checkpoint_envelope(
            family="M1", model=M1LocalPredictor(), source_commit=COMMIT,
            training_seed=0, learning_rate=1e-4, weight_decay=0.0, refit_step=None,
            training_status=SYNTHETIC_MECHANICAL,
            deployment_classification="deployable-candidate")


def test_m1_cannot_be_forced_into_the_m2_schema():
    with pytest.raises(StudyCheckpointEnvelopeError):
        build_study_checkpoint_envelope(
            family="M2", model=M1LocalPredictor(), source_commit=COMMIT,
            training_seed=0, learning_rate=1e-4, weight_decay=0.0, refit_step=None,
            training_status=SYNTHETIC_MECHANICAL,
            runtime_config=DEFAULT_RUNTIME_CONFIG)


def test_the_existing_fd24_checkpoint_validation_is_not_relaxed():
    """A non-frozen architecture must still be refused by the FD24 contract path."""
    torch.manual_seed(0)
    other = RVTFD24LocalModel(FD24ModelConfig(hidden_dimension=64),
                              DEFAULT_RUNTIME_CONFIG)
    with pytest.raises(StudyCheckpointEnvelopeError):
        build_study_checkpoint_envelope(
            family="M2", model=other, source_commit=COMMIT, training_seed=0,
            learning_rate=1e-4, weight_decay=0.0, refit_step=None,
            training_status=SYNTHETIC_MECHANICAL,
            runtime_config=DEFAULT_RUNTIME_CONFIG)


# ------------------------------------------------------- offline isolation
def test_no_deployable_module_imports_the_offline_training_package():
    """The offline package must stay unreachable from the deployable path."""
    offenders = []
    for package in ("rvt_swarm/decentralized", "rvt_swarm/fd24"):
        for path in sorted((REPO / package).rglob("*.py")):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "openloop_v3" in node.module:
                        offenders.append(str(path))
                    if node.level and any(
                            alias.name == "openloop_v3" for alias in node.names):
                        offenders.append(str(path))
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "openloop_v3" in alias.name:
                            offenders.append(str(path))
    assert offenders == []


def test_the_official_train_record_without_a_v3_split_key_resolves_to_train(tmp_path):
    """The real TRAIN record predates the key; it must still classify as TRAIN.

    Stringifying the missing key would have yielded the split "None", which
    matches no protected token and therefore silently passes every refusal.
    """
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({
        "train_manifest_root": "6390cd31", "validation_selected": False,
        "reserve_selected": False}))
    classification = classify_dataset_root(tmp_path)
    assert classification.origin == "OFFICIAL"
    assert classification.v3_split == "v3_train"
    assert "train_manifest_root" in classification.evidence


def test_an_official_record_naming_no_split_is_refused(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"run_id": "x"}))
    with pytest.raises(OpenLoopV3AuthorizationError):
        require_training_dataset(tmp_path)


def test_a_record_that_contradicts_the_caller_is_a_hard_error(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"v3_split": "v3_validation"}))
    with pytest.raises(OpenLoopV3AuthorizationError):
        classify_dataset_root(tmp_path, declared_split="v3_train")


def test_a_validation_record_without_the_key_still_resolves_to_validation(tmp_path):
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "authority.json").write_text(json.dumps({"validation_selected": True}))
    with pytest.raises(ValidationAccessRefused):
        require_training_dataset(tmp_path)
