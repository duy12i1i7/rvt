"""Stage 5D pre-reveal: verify authority and freeze the evaluation manifest.

This runs in a container with NO validation mount, so the manifest is provably
frozen before any VALIDATION outcome byte could be read. It reloads both
checkpoints and proves deterministic inference on a SYNTHETIC graph.
"""
from __future__ import annotations
import hashlib, json, os, pathlib, sys

sys.path.insert(0, "/opt/rvt"); os.chdir("/opt/rvt")
import torch
from rvt_swarm.phase8.common import attach_canonical_hash, verify_canonical_hash
from rvt_swarm.fd24.configuration import fd24_model_config_from_source
from rvt_swarm.fd24.model import RVTFD24LocalModel, prepare_fd24_model_batch
from rvt_swarm.openloop_v3 import synthetic
from rvt_swarm.openloop_v3.authority import (
    FAMILY_SELECTION_RULE_V1_SHA256, M1_INPUT_CONTRACT_V1_SHA256,
    M2_MODEL_CONFIG_SHA256, OFFICIAL_V3_TRAIN_SEAL_ROOT,
    OFFICIAL_V3_VALIDATION_SEAL_ROOT, PREREGISTRATION_V1_SHA256,
    TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256, load_open_loop_v3_authority,
)
from rvt_swarm.openloop_v3.bootstrap import (
    BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED, CONFIDENCE_LEVEL,
)
from rvt_swarm.openloop_v3.envelope import load_study_checkpoint_envelope, restore_m1
from rvt_swarm.openloop_v3.m1 import m1_features
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG
from rvt_swarm.topology_registry import COMPACT

OUT = pathlib.Path("/out")
REVEAL_TS = sys.argv[1] if len(sys.argv) > 1 else "UNSET"
def digest(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

assert not pathlib.Path("/validation").exists(), \
    "the pre-reveal container must have no validation mount"
print("no_validation_mount_present True", flush=True)

# ------------------------------------------------------------- §1 authority
authority = load_open_loop_v3_authority(pathlib.Path("/opt/rvt"))
dev = json.loads((OUT / "open_loop_v3_train_model_development_v1.json").read_text())
auth5c = json.loads((OUT / "open_loop_v3_scientific_training_authorization_v1.json").read_text())
selection = json.loads((OUT / "train_hp_selection_v1.json").read_text())
m0 = json.loads((OUT / "m0_fitted_train_artifact_v1.json").read_text())
train_seal = json.loads(pathlib.Path("/train/seal/official_v3_train_seal_v1.json").read_text())

expect = {
 "train_seal": (train_seal["official_v3_train_seal_root"], OFFICIAL_V3_TRAIN_SEAL_ROOT),
 "prereg": (PREREGISTRATION_V1_SHA256,
            "8619ac4c8a60740209d826910d9002d12d63f825886b4869e08c883024e7dbf6"),
 "stage5b_qual": (auth5c["bindings"]["stage5b_qualification_root"],
                  "9bfb1f2ab7882f7d1ae19fe0fdfb7b6659de1c254422c842973fe50f9892e3e3"),
 "stage5c_auth": (auth5c["open_loop_v3_scientific_training_authorization_v1_sha256"],
                  "2c6da926bd45655888115fba4675ac35edb18f87927815bbf27220483d22db62"),
 "dev_root": (dev["open_loop_v3_train_model_development_root"],
              "1ed37294a787f6eb232e5fc0ccbba88ec2d36d3ba974bb17233d0d5a5ca76f33"),
 "hp_root": (selection["train_hp_selection_v1_sha256"],
             "9ed9a334248f4c01888202d3a9df323a95e6d21b20e40948eaaf49d9b962851e"),
 "rule_root": (FAMILY_SELECTION_RULE_V1_SHA256,
               "f65e60fee5b5c0e7249b3594a25d4cb54bf826c19be2cf3aad75df5f1b72f1f5"),
 "validation_seal_expected": (OFFICIAL_V3_VALIDATION_SEAL_ROOT,
                              "770957243df01a4077ef331e55b1e6ee892b64f2c410112e656ed38832fd8d84"),
 "m0_artifact": (digest(OUT / "m0_fitted_train_artifact_v1.json"),
                 "1907f68ea989042c1da56fb9ec50b4f9aec935b9ebbb4311d945f31212c61154"),
}
ok = True
for name, (got, want) in expect.items():
    good = got == want
    ok &= good
    print(f"  {name}: {'OK' if good else 'MISMATCH'} {got}", flush=True)
assert verify_canonical_hash(dev, "open_loop_v3_train_model_development_root")
assert verify_canonical_hash(train_seal, "official_v3_train_seal_root")
assert verify_canonical_hash(m0, "m0_fitted_train_artifact_v1_sha256")
if not ok:
    raise SystemExit("AUTHORITY MISMATCH -- refusing to proceed to reveal")
print("authority_ok True", flush=True)

# ------------------------------------------- §4 checkpoint reload + determinism
CKPT = {"M1": OUT / "checkpoints" / "M1-seed47.pt",
        "M2": OUT / "checkpoints" / "M2-seed47.pt"}
EXPECT_FILE = {
 "M1": "60273cf0a79f8c4b32b1c567f51e6ae6cffb8b51e8eba7878015dbb133d53b2f",
 "M2": "84ec5025a270f97e0a2aab2d5f4fb7a47d23897141c315b1802cf3860abf0a46"}
graph = synthetic.synthetic_graph(team_size=5, robot=0, candidate=COMPACT,
                                  step=3, jitter=0.1)
m1_probe = m1_features(graph).unsqueeze(0)
m2_probe = prepare_fd24_model_batch((graph,))
reload_report = {}
for family, path in CKPT.items():
    file_hash = digest(path)
    assert file_hash == EXPECT_FILE[family], (family, file_hash)
    envelope = load_study_checkpoint_envelope(path)
    assert envelope["training_status"] == "scientifically-trained"
    assert envelope["deployment_classification"] == "shadow-disabled"
    assert envelope["training_seed"] == 47
    if family == "M1":
        assert envelope["m1_local_non_graph_input_contract_v1_sha256"] == M1_INPUT_CONTRACT_V1_SHA256
        a, b = restore_m1(envelope), restore_m1(load_study_checkpoint_envelope(path))
        a.eval(); b.eval()
        with torch.no_grad():
            first, second = a(m1_probe), b(m1_probe)
        residual_before = residual_after = None
    else:
        assert envelope["fd24_model_config_sha256"] == M2_MODEL_CONFIG_SHA256
        payload = envelope["family_payload"]["fd24_checkpoint"]
        cfg = fd24_model_config_from_source(payload["model_config"])
        def build():
            model = RVTFD24LocalModel(cfg, DEFAULT_RUNTIME_CONFIG)
            model.load_state_dict(payload["state_dict"]); model.eval(); return model
        a, b = build(), build()
        with torch.no_grad():
            first = a.recoverability_head(a.conditioned_representation(m2_probe))
            second = b.recoverability_head(b.conditioned_representation(m2_probe))
        from rvt_swarm.fd24.checkpoint import canonical_state_dict_hash
        residual_before = canonical_state_dict_hash({
            n: t.detach().cpu().clone()
            for n, t in a.residual_action_head.state_dict().items()})
        refit = json.loads(next(
            p for p in (OUT / "refits").glob("*.json")
            if json.loads(p.read_text())["spec"]["model_family"] == "M2"
            and json.loads(p.read_text())["spec"]["seed"] == 47).read_text())
        residual_after = refit["residual_state_sha256_after"]
        assert residual_before == residual_after, (residual_before, residual_after)
    assert torch.equal(first, second) and bool(torch.isfinite(first).all())
    reload_report[family] = {
        "checkpoint_file": path.name, "file_sha256": file_hash,
        "state_dict_sha256": envelope["state_dict_sha256"],
        "envelope_root": envelope["open_loop_v3_study_checkpoint_envelope_v1_sha256"],
        "training_seed": envelope["training_seed"],
        "hyperparameters": dict(envelope["hyperparameters"]),
        "refit_step": envelope["refit_step"],
        "deterministic_inference": True,
        "residual_state_sha256": residual_before}
    print(f"  {family} reload OK state={envelope['state_dict_sha256'][:16]} "
          f"deterministic=True", flush=True)

# ------------------------------------------------------ §3 evaluation manifest
impl = {name: digest(pathlib.Path("/opt/rvt") / rel) for name, rel in (
    ("loss_v3", "rvt_swarm/fd24/loss_v3.py"),
    ("metrics_v3", "rvt_swarm/fd24/metrics_v3.py"),
    ("loader_v3", "rvt_swarm/fd24/loader_v3.py"),
    ("bootstrap", "rvt_swarm/openloop_v3/bootstrap.py"),
    ("calibration", "rvt_swarm/openloop_v3/calibration.py"),
    ("selection", "rvt_swarm/openloop_v3/selection.py"),
    ("m0", "rvt_swarm/openloop_v3/m0.py"),
    ("m1", "rvt_swarm/openloop_v3/m1.py"),
    ("rehydrate", "rvt_swarm/openloop_v3/rehydrate.py"),
    ("driver", "rvt_swarm/openloop_v3/driver.py"))}

body = {
 "schema_version": "rvt-open-loop-v3-validation-evaluation-manifest/v1",
 "name": "OPEN_LOOP_V3_VALIDATION_EVALUATION_MANIFEST_V1",
 "status": "FROZEN_BEFORE_VALIDATION_OUTCOME_ACCESS",
 "frozen_before_reveal": True,
 "validation_outcome_accessed_at_freeze_time": False,
 "pre_reveal_container_had_validation_mount": False,
 "reveal_scheduled_utc": REVEAL_TS,
 "authority": {
  "official_v3_validation_seal_root": OFFICIAL_V3_VALIDATION_SEAL_ROOT,
  "official_v3_validation_content_root":
      "fa12acba2e8fffc0ba85a992fca9d18654d9e14d0efef1bca366a760ca390283",
  "official_v3_train_seal_root": OFFICIAL_V3_TRAIN_SEAL_ROOT,
  "open_loop_v3_recoverability_predictor_preregistration_v1_sha256":
      PREREGISTRATION_V1_SHA256,
  "stage5b_qualification_root": auth5c["bindings"]["stage5b_qualification_root"],
  "open_loop_v3_scientific_training_authorization_v1_sha256":
      auth5c["open_loop_v3_scientific_training_authorization_v1_sha256"],
  "open_loop_v3_train_model_development_root":
      dev["open_loop_v3_train_model_development_root"],
  "train_hp_selection_v1_sha256": selection["train_hp_selection_v1_sha256"],
  "open_loop_v3_family_selection_rule_v1_sha256": FAMILY_SELECTION_RULE_V1_SHA256,
  "open_loop_v3_train_internal_fold_manifest_v1_sha256":
      TRAIN_INTERNAL_FOLD_MANIFEST_V1_SHA256,
  "qualified_implementation_commit": auth5c["bindings"]["qualified_implementation_commit"],
  "qualified_training_image_digest": auth5c["bindings"]["qualified_training_image_digest"],
 },
 "families": {
  "M0": {"kind": "constant", "p_hat": m0["p_hat"],
         "artifact": "m0_fitted_train_artifact_v1.json",
         "artifact_sha256": digest(OUT / "m0_fitted_train_artifact_v1.json"),
         "refitting": "NONE"},
  "M1": reload_report["M1"],
  "M2": reload_report["M2"],
 },
 "metric_implementations": impl,
 "primary_metric": {
  "name": "event_equal_grouped_bernoulli_nll",
  "formula": "-[k log p + (R-k) log(1-p)] / R, mean over N robots, 0.5/0.5 over candidates, mean over events",
  "implementation": "rvt_swarm/fd24/loss_v3.py::event_loss and dataset_loss",
  "forbidden_substitution": "(p - k/R)^2",
  "r3_reweighting": "NONE", "class_weighting": "NONE"},
 "secondary_metrics": {
  "brier": {"formula": "p^2 - 2p(k/R) + k/R",
            "implementation": "rvt_swarm/fd24/metrics_v3.py::brier_event and brier_split"},
  "calibration": {"bins": 10,
                  "boundaries": [[0.0,0.1],[0.1,0.2],[0.2,0.3],[0.3,0.4],[0.4,0.5],
                                 [0.5,0.6],[0.6,0.7],[0.7,0.8],[0.8,0.9],[0.9,1.0]],
                  "final_bin_right_closed": True,
                  "observation_pairs": "robot level (q, k/R), weight 1/(2 N_e E)",
                  "role": "DIAGNOSTIC_ONLY"},
  "participates_in_selection": False},
 "row_event_weighting_rule": {
  "robot_rows_within_candidate": "mean over N",
  "candidates_within_event": {"COMPACT": 0.5, "LINE": 0.5},
  "events": "unweighted mean",
  "replica": "divide by R through the frozen grouped Bernoulli NLL"},
 "bootstrap": {
  "implementation": "rvt_swarm/openloop_v3/bootstrap.py",
  "implementation_sha256": impl["bootstrap"],
  "resampling_unit": "SOURCE_EPISODE",
  "stratification": "VALIDATION_LAYOUT",
  "replicates": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED,
  "interval": "95 percent percentile", "confidence_level": CONFIDENCE_LEVEL,
  "paired": True, "rng": "numpy.random.default_rng(20260821)"},
 "family_selection_rule_root": FAMILY_SELECTION_RULE_V1_SHA256,
 "temperature_scaling": False,
 "fitting_on_validation": False,
 "threshold_tuning": False,
 "subgroup_driven_model_choice": False,
 "seed_selection_after_reveal": False,
 "ensembling": False,
 "checkpoint_averaging": False,
 "alternative_hp_evaluated_for_selection": False,
 "protected_domain_access": 0,
}
sealed = attach_canonical_hash(
    body, "open_loop_v3_validation_evaluation_manifest_v1_sha256")
path = OUT / "open_loop_v3_validation_evaluation_manifest_v1.json"
path.write_text(json.dumps(sealed, indent=1, sort_keys=True) + "\n", encoding="ascii")
print("EVALUATION_MANIFEST_ROOT",
      sealed["open_loop_v3_validation_evaluation_manifest_v1_sha256"], flush=True)
print("validation_outcome_accessed NO", flush=True)
print("validation_model_evaluations 0", flush=True)
print("protected_domain_access 0", flush=True)
print("PREREVEAL_OK", flush=True)
