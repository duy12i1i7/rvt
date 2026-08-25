"""Stage 5D -- create the FROZEN_MODEL and the validation selection root."""
from __future__ import annotations
import hashlib, json, os, pathlib, shutil, sys

sys.path.insert(0, "/opt/rvt"); os.chdir("/opt/rvt")
from rvt_swarm.phase8.common import attach_canonical_hash, verify_canonical_hash

OUT = pathlib.Path("/out")          # stage-5c workspace
DEST = pathlib.Path("/selection")   # stage-5d outputs
def digest(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

manifest = json.loads((OUT / "open_loop_v3_validation_evaluation_manifest_v1.json").read_text())
result = json.loads((DEST / "validation_evaluation_result_v1.json").read_text())
dev = json.loads((OUT / "open_loop_v3_train_model_development_v1.json").read_text())
assert verify_canonical_hash(result, "validation_evaluation_result_v1_sha256")
assert verify_canonical_hash(manifest, "open_loop_v3_validation_evaluation_manifest_v1_sha256")

winner = result["family_selection"]["winner"]
assert winner in ("M0", "M1", "M2")
source = {"M0": OUT / "m0_fitted_train_artifact_v1.json",
          "M1": OUT / "checkpoints" / "M1-seed47.pt",
          "M2": OUT / "checkpoints" / "M2-seed47.pt"}[winner]
frozen_name = {"M0": "FROZEN_MODEL_M0_constant.json",
               "M1": "FROZEN_MODEL_M1-seed47.pt",
               "M2": "FROZEN_MODEL_M2-seed47.pt"}[winner]
frozen_path = DEST / frozen_name
shutil.copyfile(source, frozen_path)
assert digest(frozen_path) == digest(source), "frozen model copy diverged"

frozen_body = {
 "schema_version": "rvt-open-loop-v3-scientific-frozen-model/v1",
 "name": "SCIENTIFIC_FROZEN_OPEN_LOOP_MODEL",
 "model_family": winner,
 "selected_by": "the frozen open-loop V3 family-selection rule, one-shot VALIDATION",
 "family_selection_rule_root": manifest["family_selection_rule_root"],
 "artifact": frozen_name,
 "artifact_sha256": digest(frozen_path),
 "source_artifact_sha256": digest(source),
 "training_seed": 47 if winner != "M0" else None,
 "hyperparameters": (manifest["families"][winner]["hyperparameters"]
                     if winner != "M0" else {"optimizer": "NONE"}),
 "refit_step": (manifest["families"][winner]["refit_step"]
                if winner != "M0" else None),
 "state_dict_sha256": (manifest["families"][winner]["state_dict_sha256"]
                       if winner != "M0" else None),
 "scientific_status": "SCIENTIFIC_FROZEN_OPEN_LOOP_MODEL",
 "deployment_classification": "shadow-disabled",
 "deployable": False, "safety_certified": False, "production_qualified": False,
 "retrained_after_family_selection": False,
 "refit_using_validation": False,
 "temperature_scaling_activated": False,
 "authority": {
  "open_loop_v3_recoverability_predictor_preregistration_v1_sha256":
      manifest["authority"]["open_loop_v3_recoverability_predictor_preregistration_v1_sha256"],
  "official_v3_train_seal_root": manifest["authority"]["official_v3_train_seal_root"],
  "official_v3_validation_seal_root": manifest["authority"]["official_v3_validation_seal_root"],
  "open_loop_v3_train_model_development_root":
      dev["open_loop_v3_train_model_development_root"],
  "qualified_implementation_commit": manifest["authority"]["qualified_implementation_commit"],
  "qualified_training_image_digest": manifest["authority"]["qualified_training_image_digest"],
 },
}
frozen = attach_canonical_hash(frozen_body, "scientific_frozen_open_loop_model_v1_sha256")
(DEST / "scientific_frozen_open_loop_model_v1.json").write_text(
    json.dumps(frozen, indent=1, sort_keys=True) + "\n", encoding="ascii")

body = {
 "schema_version": "rvt-open-loop-v3-validation-selection/v1",
 "name": "OPEN_LOOP_V3_VALIDATION_SELECTION",
 "status": "ONE_SHOT_VALIDATION_SELECTION_COMPLETE",
 "open_loop_v3_validation_evaluation_manifest_v1_sha256":
     manifest["open_loop_v3_validation_evaluation_manifest_v1_sha256"],
 "evaluation_manifest_file_sha256":
     digest(OUT / "open_loop_v3_validation_evaluation_manifest_v1.json"),
 "validation_reveal_occurred": True,
 "validation_reveal_timestamp_utc": result["validation_reveal_timestamp_utc"],
 "official_v3_validation_seal_root": result["official_v3_validation_seal_root"],
 "official_v3_validation_content_root": result["official_v3_validation_content_root"],
 "validation_dataset_changed": False,
 "validation_status": "SPENT_MODEL_SELECTION_SET",
 "validation_blinded": False,
 "validation_reusable_for_model_selection": False,
 "validation_is_unbiased_final_generalization_evidence": False,
 "prediction_artifacts": {
  family: {"file": f"validation_predictions_{family}.json",
           "artifact_sha256": digest(DEST / f"validation_predictions_{family}.json"),
           "predictions_root": result["coverage"][family]["predictions_root"],
           "rows": result["coverage"][family]["rows"],
           "coverage": result["coverage"][family]["coverage"]}
  for family in ("M0", "M1", "M2")},
 "aggregate_metrics": result["aggregate_metrics"],
 "paired_bootstrap": result["paired_bootstrap"],
 "family_selection": result["family_selection"],
 "validation_evaluation_result_v1_sha256":
     result["validation_evaluation_result_v1_sha256"],
 "validation_evaluation_result_file_sha256":
     digest(DEST / "validation_evaluation_result_v1.json"),
 "frozen_model": {
  "scientific_frozen_open_loop_model_v1_sha256":
      frozen["scientific_frozen_open_loop_model_v1_sha256"],
  "model_family": winner, "artifact": frozen_name,
  "artifact_sha256": digest(frozen_path),
  "deployment_classification": "shadow-disabled"},
 "temperature_scaling_activated": False,
 "parameters_fitted_on_validation": 0,
 "optimizer_steps": 0, "gradient_updates": 0,
 "threshold_tuning": False, "seed_selection_after_reveal": False,
 "ensembling": False, "checkpoint_averaging": False,
 "protected_domain_access": 0,
 "scientific_scope": {
  "establishes": [
   "under the frozen open-loop protocol, both learned families reduce the "
   "event-equal grouped Bernoulli NLL relative to the constant baseline on the "
   "frozen VALIDATION layouts",
   "M2 reduces it further than M1 under the frozen paired interval",
  ],
  "does_not_establish": [
   "closed-loop benefit", "topology-selection benefit", "causal graph advantage",
   "safety improvement", "generalization to protected domains",
   "an unbiased generalization estimate -- VALIDATION is the selection set",
  ]},
}
sealed = attach_canonical_hash(body, "open_loop_v3_validation_selection_root")
path = DEST / "open_loop_v3_validation_selection_v1.json"
path.write_text(json.dumps(sealed, indent=1, sort_keys=True) + "\n", encoding="ascii")
print("FAMILY_WINNER", winner, flush=True)
print("FROZEN_MODEL", frozen_name, digest(frozen_path), flush=True)
print("FROZEN_MODEL_ROOT", frozen["scientific_frozen_open_loop_model_v1_sha256"], flush=True)
print("VALIDATION_SELECTION_ROOT", sealed["open_loop_v3_validation_selection_root"], flush=True)
print("bytes", path.stat().st_size, flush=True)
