"""CR-0R -- amend the clean-room contract to V2, closing exactly three degrees of freedom."""
from __future__ import annotations
import copy, hashlib, json, pathlib, subprocess, sys, time
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import attach_canonical_hash, verify_canonical_hash
from rvt_swarm.cleanroom.a3_control import (
    BLOCKS, CANDIDATE_EMBEDDING_DIMENSION, CANDIDATE_TABLE_SIZE,
    CAPACITY_MATCH_TOLERANCE_FRACTION, DROPOUT_PROBABILITY, HIDDEN_DIMENSION,
    INPUT_DIMENSION, capacity_match_report,
)
from rvt_swarm.cleanroom.safety_contract import (
    PRIMARY_ENDPOINTS, SECONDARY_ENDPOINTS, RO_CONTACT_M, RR_CONTACT_M,
    TIGHTEST_SURFACE_MARGIN_M, TTC_VIOLATION_THRESHOLD_S,
)

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def h(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
v1 = json.loads((R / "rvt_swarm_clean_room_global_contract_v1.json").read_text())
assert verify_canonical_hash(v1, "rvt_swarm_clean_room_global_contract_root")
V1_ROOT = v1["rvt_swarm_clean_room_global_contract_root"]

v2 = copy.deepcopy(v1)
del v2["rvt_swarm_clean_room_global_contract_root"]
v2["schema_version"] = "rvt-swarm-clean-room-global-contract/v2"
v2["name"] = "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V2"
v2["stage"] = "CR-0R"
v2["cr0_source_commit"] = subprocess.run(
    ["git","-C",str(ROOT),"rev-parse","HEAD"], capture_output=True, text=True).stdout.strip()

v2["amendment"] = {
 "amends": "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V1",
 "v1_root": V1_ROOT,
 "v1_tag": "rvt-cleanroom-cr0-v1",
 "v1_preserved_unmodified": True,
 "made_before_any_clean_room_data_existed": True,
 "made_before_any_clean_room_model_training": True,
 "no_empirical_clean_room_outcome_informed_these_changes": True,
 "scope": ["confirmatory safety margins", "exact A3 mechanism-control definition",
           "protected-layout generalization semantics",
           "the interpretation-rule consequences of those three"],
 "all_other_v1_decisions": "PRESERVED",
}

# ------------------------------------------------ closure 1: safety margins ---
v2["safety_contract"] = {
 "safety_is_a_core_outcome": True,
 "status": "FULLY_SPECIFIED_AT_CR0R -- no safety margin is deferred to CL-DEV-R or CR-8",
 "frozen_physical_constants": {
   "robot_radius_m": 0.18, "obstacle_radius_m": 0.35,
   "inter_robot_safety_margin_m": 0.04, "obstacle_clearance_margin_m": 0.37,
   "min_rr_distance_m": 0.40, "min_ro_distance_m": 0.55,
   "rr_physical_contact_m": RR_CONTACT_M, "ro_physical_contact_m": RO_CONTACT_M,
   "tightest_engineered_surface_margin_m": TIGHTEST_SURFACE_MARGIN_M,
   "maximum_speed_mps": 0.90, "maximum_acceleration_mps2": 0.60,
   "source": "rvt_swarm/config.py and rvt_swarm/runtime_configuration.py, unmodified"},
 "inherited_frozen_pilot_gate": {
   "source": "results/rvt_fd24/phase9d_h1_requirement_map_v1.json::collision_gate",
   "collision_free_point_estimate_minimum": 0.95,
   "absolute_degradation_maximum": 0.01,
   "note": "an engineering tolerance established in pilot development and reused "
           "verbatim; it was not re-derived and not chosen to be easy to pass"},
 "primary_endpoints": [
   {"key": e.key, "definition": e.definition, "unit": e.unit,
    "aggregation_unit": e.aggregation_unit, "direction_of_harm": e.direction_of_harm,
    "non_inferiority_margin": e.margin, "margin_justification": e.margin_justification,
    "absolute_floor": e.absolute_floor,
    "interval": "paired stratified cluster bootstrap over source episodes, stratified "
                "by layout, 10000 replicates, seed 20260901, one-sided 95 percent bound "
                "on the harmful side",
    "treatment_contrast": "full recoverability-aware RVT minus the frozen "
                          "no-recoverability reactive comparator B1",
    "pass_rule": ("lower95(treatment - comparator) > -margin"
                  if e.direction_of_harm == "decrease"
                  else "upper95(treatment - comparator) < +margin")
    + ("; AND the treatment point estimate must be at least the absolute floor"
       if e.absolute_floor is not None else "")}
   for e in PRIMARY_ENDPOINTS],
 "secondary_endpoints": [
   {"key": e.key, "definition": e.definition, "unit": e.unit,
    "aggregation_unit": e.aggregation_unit, "role": e.role,
    "pass_rule": "NONE -- diagnostic only",
    "justification": e.margin_justification} for e in SECONDARY_ENDPOINTS],
 "ttc_violation_threshold_s": TTC_VIOLATION_THRESHOLD_S,
 "ttc_threshold_justification": "the full braking time from top speed, "
     "max_speed / max_acceleration = 0.9 / 0.6 = 1.5 s; below it a collision cannot "
     "be avoided by braking alone",
 "multiplicity": {
   "procedure": "INTERSECTION_UNION_TEST",
   "rule": "H-CL2 passes only if EVERY primary endpoint passes",
   "alpha_correction": "NONE_REQUIRED",
   "why": "under an intersection-union test the composite holds the nominal level "
          "without correction, because rejecting the union null requires rejecting "
          "every component null"},
 "central_claim_conjunction": "the central closed-loop claim requires H-CL1 benefit "
     "PASS *and* H-CL2 safety non-inferiority PASS",
 "progress_with_safety_failure": "CENTRAL_CLAIM_FAILS",
 "interpretation_rule": "progress or recovery improvement accompanied by unacceptable "
     "safety degradation DOES NOT support the central claim",
 "silent_safety_for_progress_trade": "FORBIDDEN",
 "endpoint_implementations": v1["safety_contract"]["endpoint_implementations"],
 "margins_chosen_using_any_clean_room_outcome": False,
 "margin_modification_after_this_amendment": "FORBIDDEN",
 "implementation": "rvt_swarm/cleanroom/safety_contract.py",
 "implementation_sha256": h("rvt_swarm/cleanroom/safety_contract.py"),
}

# --------------------------------------------------- closure 2: A3 exactness ---
cap = capacity_match_report()
v2["a3_mechanism_control"] = {
 "status": "SCIENTIFIC_DEFINITION_IMMUTABLE_FROM_CR0R",
 "purpose": "isolate ITERATIVE MESSAGE PASSING over the ego graph, with capacity and "
            "available information held fixed",
 "architecture": f"permutation-invariant pooled local MLP: input projection to width "
   f"{HIDDEN_DIMENSION}, then {BLOCKS} residual blocks of "
   "LayerNorm -> Linear -> ReLU -> Linear, then LayerNorm and a single logit head",
 "hidden_dimension": HIDDEN_DIMENSION, "blocks": BLOCKS,
 "activation": "relu", "normalization": "layer_norm",
 "dropout_probability": DROPOUT_PROBABILITY, "numerical_dtype": "float32",
 "input_dimension": INPUT_DIMENSION,
 "inputs": "the SAME admitted set as M2 (node_x, node_feature_valid_mask, node_kind, "
   "edge_index, edge_attr, edge_feature_valid_mask, edge_type, root_index, "
   "candidate_topology_id), consumed as: root node features and mask, mean and max "
   "pooling over one-hop neighbor node features and masks, mean and max pooling over "
   "incident edge features and masks, and the candidate-topology embedding",
 "forbidden_inputs": v1["model_families"]["input_contract"]["forbidden_predictor_inputs"],
 "topology_identity_visible": True,
 "topology_visibility_note": "A3 is conditioned on the candidate topology at M2's "
   "embedding width. It is NOT the topology-blinded ablation; that contrast is A2.",
 "neighbor_information_visible": True,
 "neighbor_visibility_note": "neighbor information is retained through permutation-"
   "invariant pooling. Removing it would confound 'no message passing' with "
   "'no neighbors' and would not isolate the mechanism.",
 "message_passing_removal": "edge_index is used ONLY to identify one-hop incidence to "
   "the root. There is no propagation between non-root nodes, no iterated exchange, and "
   "no attention. A single unordered aggregation replaces the message-passing blocks.",
 "candidate_embedding_dimension": CANDIDATE_EMBEDDING_DIMENSION,
 "candidate_table_size": CANDIDATE_TABLE_SIZE,
 "parameter_count": cap["a3_parameters"],
 "m2_recoverability_path_parameters": cap["m2_recoverability_path_parameters"],
 "capacity_matching_criterion": "total trainable parameter count of the A3 model versus "
   "M2's recoverability-path parameter count",
 "capacity_matching_tolerance_fraction": CAPACITY_MATCH_TOLERANCE_FRACTION,
 "residual_mismatch_absolute": cap["absolute_difference"],
 "residual_mismatch_relative": cap["relative_difference"],
 "residual_mismatch_predeclared_limitation": "exact integer capacity equality is not "
   "attainable at integer width. Width 184 is the closest achievable match and is "
   f"{abs(cap['absolute_difference'])} parameters BELOW M2, i.e. A3 is very slightly "
   "under-parameterised; this direction is conservative for a claim that message "
   "passing helps, since it cannot inflate A3.",
 "training_recipe": {
   "optimizer": "AdamW", "learning_rate": 0.001, "weight_decay": 0.0001,
   "note": "identical to the frozen M2 recipe, so the contrast is not confounded by "
           "optimization settings",
   "gradient_norm_clip": 1.0, "warmup_steps": 2000,
   "lr_schedule_after_warmup": "CONSTANT", "maximum_optimizer_steps": 50000,
   "evaluation_interval_steps": 1000, "patience_scheduled_evaluations": 8,
   "improvement_rule": "STRICT_IMPROVEMENT_ONLY", "min_delta": 0.0,
   "tie_rule": "on machine-visible equality choose the EARLIER checkpoint",
   "batch": "16 decision-event groups", "precision": "float32", "device": "CPU",
   "loss": "the same event-equal grouped Bernoulli NLL as M1 and M2",
   "weighting": "identical to the frozen weighting contract",
   "checkpoint_rule": "strict lower held-out TRAIN-R NLL; on exact tie the EARLIER step",
   "stopping_rule": "early stopping on the held-out TRAIN-R internal fold only",
   "refit_step_rule": v1["training_recipe"]["refit_step_rule"],
   "determinism": v1["training_recipe"]["shared"]["determinism"],
   "initialization": v1["training_recipe"]["shared"]["initialization"]},
 "seeds": [11, 29, 47],
 "participates_in_SELECT_R_family_selection": False,
 "planned_training_stage": "CR-2, from scratch on TRAIN-R",
 "architecture_or_recipe_change_after_TRAIN_R_exists": "FORBIDDEN",
 "runtime_and_checkpoint_binding_for_the_mechanism_study": "may be bound at CR-8; the "
   "scientific definition above is immutable from now",
 "supports_claim": "if full RVT beats A3 under the frozen mechanism contrast, that "
   "supports iterative message passing over the ego graph contributing beyond a "
   "capacity-matched permutation-invariant pooled model with the same inputs",
 "does_not_support_claim": "it does not establish that any particular architectural "
   "detail of M2 is necessary, does not identify WHICH relational information matters, "
   "does not establish closed-loop or safety benefit on its own, and does not license "
   "a general claim that graph neural networks are required for recoverability",
 "M1_vs_M2_alone_admissible_for_message_passing_causality": False,
 "implementation": "rvt_swarm/cleanroom/a3_control.py",
 "implementation_sha256": h("rvt_swarm/cleanroom/a3_control.py"),
}
v2["baselines_and_ablations"]["A3_capacity_matched_non_message_passing"] = (
 "FROZEN EXACTLY at CR-0R; see the a3_mechanism_control block")

# ------------------------------------- closure 3: protected-layout semantics ---
v2["protected_generalization"] = {
 "case": "CASE_A",
 "case_determination": "rvt_swarm/phase8/scenario.py defines SCENARIO_FAMILIES as a "
   "frozen tuple of exactly 10 families F1..F10. No eleventh family exists. Creating a "
   "genuinely held-out layout FAMILY would require modifying the frozen scientific "
   "generator, which is forbidden, so no held-out family namespace is available.",
 "known_layout_families": ["F1","F2","F3","F4","F5","F6","F7","F8","F9","F10"],
 "protected_identities": "new layout INSTANCES at the held-out generator offset 0.79, "
   "the reserved final-test base, within the known families F1..F10",
 "exact_terminology": "unseen layout instances within known layout families",
 "forbidden_claim_language": ["unseen layout families","novel layout families",
   "unseen layouts (unqualified)","new environments","a new domain",
   "out-of-distribution generalization","domain generalization",
   "generalizes to unseen scenario types"],
 "allowed_claim_language": "generalization to unseen layout instances within the known "
   "layout families F1-F10, at a held-out generator offset",
 "broad_family_level_generalization": "OUTSIDE_THE_CURRENT_CONFIRMATORY_SCOPE",
 "why_not_extended": "introducing new layout families would require modifying the frozen "
   "scientific generator; this is reported rather than silently done",
 "distinction_that_must_not_be_conflated": {
   "identity_disjoint_confirmation": "IID-ish confirmation on identity-disjoint samples "
     "drawn from the SAME known layout population. TRAIN-R, SELECT-R, CL-DEV-R and "
     "MAIN-R are all of this kind.",
   "distribution_or_domain_generalization": "a shift to a genuinely different layout "
     "population. NOT tested anywhere in this programme."},
 "intended_stress_dimensions": ["unseen layout instances within F1-F10",
   "team-size shifts","environment and obstacle shifts","partial-observability stress"],
 "inaccessible_until": "the clean novelty checkpoint",
 "forbidden_after_reveal": ["model selection","controller tuning","threshold tuning",
   "ablation redesign"],
 "F9_local_observability": v1["protected_generalization"]["F9_local_observability"],
}
v2["disjointness_contract"]["layout_offset_assignment"]["declared_limitation"] = (
 v1["disjointness_contract"]["layout_offset_assignment"]["declared_limitation"]
 + " Resolved at CR-0R as CASE_A: PROTECTED-R tests unseen layout INSTANCES within the "
   "known families F1-F10, never unseen families.")

# ------------------------------------------------------- claim language (6) ---
v2["dataset_role_claim_language"] = {
 "TRAIN-R": "training evidence only; no scientific claim",
 "SELECT-R": "predictor-family evidence conditional on the frozen layout population F1-F10",
 "CL-DEV-R": "development evidence only; never confirmatory",
 "MAIN-R": "closed-loop confirmatory evidence conditional on the frozen layout "
           "population F1-F10, at identity-disjoint instances",
 "MECH-R": "mechanism evidence conditional on the frozen layout population F1-F10",
 "PROTECTED-R": "generalization to unseen layout instances within the known families "
                "F1-F10 at a held-out generator offset",
 "rule": "no broader generalization claim may be inferred merely from identity "
         "disjointness",
}

# ------------------------------------------- interpretation rule consequences ---
v2["interpretation_claim_mapping"] = list(v1["interpretation_claim_mapping"]) + [
 {"if": "H-CL1 benefit passes but H-CL2 safety non-inferiority fails",
  "then": "THE CENTRAL CLOSED-LOOP CLAIM FAILS; a progress gain paid for in safety is "
          "not a partial success"},
 {"if": "full RVT benefit passes but the capacity-matched A3 contrast fails",
  "then": "no message-passing-specific causal claim may be made; the system benefit may "
          "still stand"},
 {"if": "protected instances pass within families F1-F10",
  "then": "do not claim unseen-FAMILY generalization; claim only unseen layout INSTANCES "
          "within known families"},
 {"if": "a genuine held-out family test is never run",
  "then": "no broad family-level generalization claim may be made at all"},
]
v2["closed_loop_hypotheses"]["exact_endpoints_and_effect_definitions_resolved_before"] = (
 "SAFETY endpoints, margins and the pass/fail rule are FROZEN at CR-0R. The H-CL1 "
 "benefit endpoint effect size remains to be fixed before CR-8.")

# ------------------------------------------------------------ engine + suite ---
v2["orchestration_authority"]["clean_room_engine"] = {
 p: h(f"rvt_swarm/cleanroom/{p}") for p in
 ("__init__.py","universe.py","family_statistic.py","selection.py",
  "calibration_contract.py","safety_contract.py","a3_control.py")}
v2["adversarial_qualification"]["engine_suite_at_CR0"] = {
 **v1["adversarial_qualification"]["engine_suite_at_CR0"],
 "sha256": h("tests/test_cleanroom_engine.py")}
v2["adversarial_qualification"]["cr0r_suite"] = {
 "path": "tests/test_cleanroom_cr0r.py", "sha256": h("tests/test_cleanroom_cr0r.py"),
 "tests": 16, "result": "16 passed",
 "covers": ["four primary safety endpoints fully specified","frozen margin values",
   "strictness at exactly the margin","absolute floor can fail a non-inferior result",
   "direction of harm","secondary endpoint has no pass rule",
   "intersection-union requires every endpoint","missing verdict fails closed",
   "progress without safety fails the central claim","A3 capacity match within tolerance",
   "A3 width is the closest achievable","A3 sees topology identity",
   "A3 contains no message-passing primitive"]}
v2["adversarial_qualification"]["total_tests_passing_at_CR0R"] = 45

sealed = attach_canonical_hash(v2, "rvt_swarm_clean_room_global_contract_root")
out = R / "rvt_swarm_clean_room_global_contract_v2.json"
out.write_text(json.dumps(sealed, indent=1, sort_keys=True) + "\n", encoding="ascii")

# --------------------------------------------------- machine-readable diff ---
def flat(o, p=""):
    if isinstance(o, dict):
        for k in sorted(o):
            yield from flat(o[k], f"{p}.{k}")
    elif isinstance(o, list):
        yield p, json.dumps(o, sort_keys=True)
    else:
        yield p, o
a = dict(flat({k: v for k, v in v1.items() if k != "rvt_swarm_clean_room_global_contract_root"}))
b = dict(flat({k: v for k, v in sealed.items() if k != "rvt_swarm_clean_room_global_contract_root"}))
added = sorted(set(b) - set(a)); removed = sorted(set(a) - set(b))
changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
ALLOWED = ("safety_contract", "a3_mechanism_control", "protected_generalization",
           "dataset_role_claim_language", "interpretation_claim_mapping",
           "baselines_and_ablations.A3_capacity_matched_non_message_passing",
           "closed_loop_hypotheses.exact_endpoints_and_effect_definitions_resolved_before",
           "disjointness_contract.layout_offset_assignment.declared_limitation",
           "orchestration_authority.clean_room_engine", "adversarial_qualification",
           "amendment", "schema_version", "name", "stage", "cr0_source_commit")
def allowed(k): return any(k.lstrip(".").startswith(x) for x in ALLOWED)
off_scope = [k for k in added + removed + changed if not allowed(k)]
diff = {
 "schema_version": "rvt-swarm-clean-room-contract-diff/v1",
 "from_root": V1_ROOT, "to_root": sealed["rvt_swarm_clean_room_global_contract_root"],
 "closures": ["confirmatory safety margins", "exact A3 mechanism-control definition",
              "protected-layout generalization semantics",
              "interpretation-rule consequences of the above"],
 "added_paths": added, "removed_paths": removed, "changed_paths": changed,
 "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
 "out_of_scope_changes": off_scope,
 "all_unrelated_v1_decisions_preserved": not off_scope,
}
diff = attach_canonical_hash(diff, "clean_room_contract_v1_to_v2_diff_root")
(R / "rvt_swarm_clean_room_contract_v1_to_v2_diff.json").write_text(
    json.dumps(diff, indent=1, sort_keys=True) + "\n", encoding="ascii")
print("V2_ROOT", sealed["rvt_swarm_clean_room_global_contract_root"])
print("V2_file_sha256", hashlib.sha256(out.read_bytes()).hexdigest())
print("DIFF_ROOT", diff["clean_room_contract_v1_to_v2_diff_root"])
print(f"added={len(added)} removed={len(removed)} changed={len(changed)}")
print("OUT_OF_SCOPE_CHANGES:", off_scope if off_scope else "NONE")
