"""CR-0 -- build the clean-room global scientific + executable contract."""
from __future__ import annotations
import hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import attach_canonical_hash

ROOT = pathlib.Path("/Users/udy/rvt")
R = ROOT / "results/rvt_fd24"
def h(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
pre = json.loads((R / "open_loop_v3_recoverability_predictor_preregistration_v1.json").read_text())
reg = json.loads((R / "phase9d_v3f_l_layout_split_registry_v2.json").read_text())
commit = subprocess.run(["git","-C",str(ROOT),"rev-parse","HEAD"],
                        capture_output=True, text=True).stdout.strip()

ENGINE = {p: h(f"rvt_swarm/cleanroom/{p}") for p in
          ("__init__.py","universe.py","family_statistic.py","selection.py","calibration_contract.py")}
INHERITED = {p: h(f"rvt_swarm/{p}") for p in
             ("openloop_v3/bootstrap.py","openloop_v3/calibration.py","fd24/loss_v3.py",
              "fd24/metrics_v3.py","fd24/loader_v3.py","fd24/model.py","fd24/configuration.py",
              "openloop_v3/m1.py","openloop_v3/m0.py","openloop_v3/rehydrate.py",
              "topology_registry.py","safety.py","decentralized/local_safety_projection.py",
              "decentralized/online_topology_scope.py","decentralized/consensus.py",
              "decentralized/local_controller.py","decentralized/robot_local_controller.py",
              "phase8/scenario.py")}

body = {
 "schema_version": "rvt-swarm-clean-room-global-contract/v1",
 "name": "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V1",
 "stage": "CR-0",
 "status": "PROSPECTIVELY_FROZEN_BEFORE_ANY_CLEAN_ROOM_DATA_EXISTS",
 "cr0_source_commit": commit,

 # ------------------------------------------------------------------ 1 ----
 "pilot_boundary": {
  "PROGRAM_BEFORE_CR0": "PILOT_DEVELOPMENT_ONLY",
  "historical_terminal_finding": "POST_REVEAL_AUTHORITY_OR_PROVENANCE_FAILURE",
  "reason_preserved": "Stage-5D executed a seed47-only family evaluation while the "
      "frozen family statistic required the mean over seeds {11,29,47} of the "
      "VALIDATION NLL",
  "history_rewritten_or_repaired": False,
  "PILOT_WEIGHTS_ALLOWED_AS_FINAL": "NO",
  "PILOT_VALIDATION_USED_FOR_FINAL_INFERENCE": "NO",
  "PILOT_CONFIDENCE_INTERVALS_USED_FOR_FINAL_CLAIMS": "NO",
  "pilot_may_inform": "method design, architecture definitions, training recipe "
      "constants, and code that is re-qualified here",
  "pilot_artifacts_retained_for_provenance": {
   "novelty_checkpoint_1_root": "d36bc4e4c43cb0062dbdfcd73b471e6683a422d391dab75ab99b1236dc0330d1",
   "stage5d_validation_selection_root": "b1110cd1f5586a0daaf76762afef81d5feb867eee9b00a6ccf3d7776c6d18eec",
   "pilot_preregistration_root": "8619ac4c8a60740209d826910d9002d12d63f825886b4869e08c883024e7dbf6"},
 },

 # ------------------------------------------------------------------ 0 ----
 "central_thesis": {
  "statement": "RVT-Swarm is a decentralized swarm-control method in which each robot "
   "uses only locally available sensing and neighbor messages to estimate probabilistic "
   "future recoverability under candidate local interaction topologies, evaluates those "
   "topologies counterfactually, and adapts its local interaction topology to improve "
   "swarm recovery, task progress and liveness while preserving obstacle avoidance and "
   "safety.",
  "this_is_a_predictor_benchmark_paper": False,
  "predictor_role": "an enabling component, not the claim",
  "final_novelty_requires": "CLOSED_LOOP_EVIDENCE"},

 # ------------------------------------------------------------------ 2 ----
 "dataset_roles": {
  "TRAIN-R": {"purpose": "train the final clean-room predictive models from scratch",
    "forbidden": ["predictor-family selection","controller tuning",
                  "confirmatory inference","final generalization"],
    "internal_use_allowed": "internal folds for the frozen early-stopping and "
        "refit-step rules; this is training, not selection"},
  "SELECT-R": {"purpose": "one-shot clean predictor-family selection",
    "forbidden": ["model training","hyperparameter tuning","seed selection",
                  "controller development","final generalization"],
    "reveals": 1},
  "CL-DEV-R": {"purpose": "closed-loop controller development and diagnostics",
    "allowed": ["inspect outcomes","oracle diagnostics",
                "controller and selector tuning inside the frozen design space",
                "failure analysis"],
    "forbidden": ["main confirmatory inference"]},
  "MAIN-R": {"purpose": "one-shot main closed-loop confirmation",
    "must_not_exist_during_CR7": True,
    "generated_only_after": "CR-8 complete-system freeze",
    "tuning_after_it_exists": "NONE"},
  "MECH-R": {"purpose": "surgical mechanism confirmation only",
    "forbidden": ["controller development","any redesign after MAIN-R outcomes"],
    "generated_only_after": "the mechanism contract is frozen at CR-8"},
  "PROTECTED-R": {"purpose": "final untouched generalization evidence",
    "opened_only_after": "the clean novelty checkpoint, under the frozen protected protocol",
    "forbidden_after_reveal": ["model selection","controller tuning","threshold tuning",
                               "ablation redesign"]},
 },

 # ------------------------------------------------------------------ 3 ----
 "disjointness_contract": {
  "identity_universe_is_enumerated_not_globbed": True,
  "identity_fields": ["layout_id","layout_sha256","source_episode_id","scenario_task_id",
    "generation_seed","team_size","environment_obstacle_identity","event_id",
    "scientific_row_id","candidate_topology_id"],
  "required_empty_intersections": [
   "TRAIN-R & SELECT-R","TRAIN-R & CL-DEV-R","SELECT-R & CL-DEV-R",
   "MAIN-R & every development role","MECH-R & every development role",
   "PROTECTED-R & every previous role"],
  "overlap_test": "for each ordered pair of roles and each identity field, the "
   "intersection of the manifest-enumerated identity sets must be empty; the check is "
   "deterministic, runs on enumerated IDs only, and fails closed",
  "role_reuse": "NONE",
  "layout_offset_assignment": {
   "formula": reg["offset_formula"],
   "generator_split_offsets": reg["generator_split_offsets"],
   "consumed_by_pilot": {"TRAIN": [0.22, 0.54], "VALIDATION": [0.65]},
   "pilot_reserve_left_untouched": [0.33],
   "forbidden": [0.76, 0.87, 0.77],
   "forbidden_reason": "offsets within approximately 0.03 of, or crossing, the "
       "final-test base offset 0.79",
   "clean_room": {"TRAIN-R": 0.00, "SELECT-R": 0.11, "CL-DEV-R": 0.44,
                  "MAIN-R": 0.55, "MECH-R": 0.66, "PROTECTED-R": 0.79},
   "minimum_pairwise_offset_separation": 0.11,
   "declared_limitation": "all six roles draw from the same ten layout families f1-f10 "
    "at different generator offsets. They are disjoint by identity, but they are not "
    "independent worlds: conclusions are conditional on the f1-f10 layout family "
    "population. PROTECTED-R additionally sits in the separate final-test namespace."},
 },

 # ------------------------------------------------------------------ 4 ----
 "generation_authority": {
  "scientific_generator_change_required": False,
  "generator_authority": reg["generator_authority"],
  "generator_sha256": reg["generator_sha256"],
  "generator_unchanged": reg["generator_unchanged"],
  "frozen_v2_scenario_code_modified": reg["frozen_v2_scenario_code_modified"],
  "executable_source_commit": pre["sealed_data_authority"]["executable_source_commit"],
  "production_image_digest": pre["sealed_data_authority"]["production_image_digest"],
  "layout_execution_spec_registry_sha256":
      pre["sealed_data_authority"]["v3_layout_execution_spec_registry_v1_sha256"],
  "layout_split_registry_sha256":
      pre["sealed_data_authority"]["v3_layout_split_registry_v2_sha256"],
  "source_acquisition_protocol_sha256":
      pre["sealed_data_authority"]["source_acquisition_protocol_sha256"],
  "target_semantics_sha256": pre["sealed_data_authority"]["target_v4_contract_sha256"],
  "probabilistic_target_sha256":
      pre["sealed_data_authority"]["recoverability_probabilistic_target_v3_sha256"],
  "replica_law_sha256": pre["sealed_data_authority"]["recoverability_replica_protocol_v3_sha256"],
  "invalidity_semantics_sha256":
      pre["sealed_data_authority"]["recoverability_v3_required_replica_invalidity_contract_v1_sha256"],
  "row_event_binding_sha256":
      pre["sealed_data_authority"]["recoverability_row_binding_v3_spec_sha256"],
  "stochastic_law": "the frozen iid disturbance law of the replica protocol; the "
      "clean-room roles differ only in generator offset and generation seed",
  "operational_wrappers": "may be newly written; each must be hashed and qualified "
      "before use and bound into the stage manifest",
 },

 # ------------------------------------------------------------------ 5 ----
 "episode_universe_contract": {
  "every_manifest_must_enumerate": ["expected source episode IDs",
      "expected source episode count","expected layout membership"],
  "zero_yield_episodes_remain_in_the_resampling_universe": True,
  "driver_must_assert_before_statistics":
      "observed source episode IDs are a subset of manifest source episode IDs, the "
      "manifest count matches its own enumeration, and every declared episode carries "
      "layout membership",
  "universe_may_never_be_derived_from_event_producing_episodes_only": True,
  "implementation": "rvt_swarm/cleanroom/universe.py::assert_episode_universe",
  "implementation_sha256": ENGINE["universe.py"],
  "fixes": "the pilot Stage-5D defect in which layout F4 resampled 24 draws where the "
      "frozen rule required its original 30",
 },

 # ------------------------------------------------------------------ 6 ----
 "model_families": {
  "primary_families": 3,
  "architecture_searched": False,
  "additional_families_from_TRAIN_R_or_SELECT_R_outcomes": "FORBIDDEN",
  "clean_room_models_trained_from_scratch": True,
  "pilot_stage5c_checkpoints_are_clean_room_checkpoints": False,
  "M0": pre["R8_model_ladder"]["M0"],
  "M1": pre["R8_model_ladder"]["M1"],
  "M2": pre["R8_model_ladder"]["M2"],
  "input_contract": pre["R9_model_input_contract"],
 },

 # ------------------------------------------------------------------ 7 ----
 "training_recipe": {
  "hyperparameter_search_on_TRAIN_R": "NONE -- the configuration is frozen here as a "
      "constant, informed by pilot development. This removes the pilot's 72-fit search "
      "and every TRAIN-R-outcome-dependent hyperparameter decision.",
  "shared": {"optimizer": "AdamW", "gradient_norm_clip": 1.0, "warmup_steps": 2000,
    "lr_schedule_after_warmup": "CONSTANT", "maximum_optimizer_steps": 50000,
    "evaluation_interval_steps": 1000, "patience_scheduled_evaluations": 8,
    "improvement_rule": "STRICT_IMPROVEMENT_ONLY", "min_delta": 0.0,
    "tie_rule": "on machine-visible equality choose the EARLIER checkpoint",
    "batch": "16 decision-event groups", "precision": "float32", "device": "CPU",
    "loss": "event-equal grouped Bernoulli NLL, rvt_swarm/fd24/loss_v3.py",
    "loss_weights": pre["R12_hyperparameter_grid"]["loss_weights"],
    "weighting": pre["R11_weighting"],
    "determinism": pre["R12_hyperparameter_grid"]["determinism"],
    "initialization": "framework default under torch.manual_seed(seed) plus a per-fit "
        "generator; no custom initialization scheme"},
  "M1": {"learning_rate": 0.001, "weight_decay": 0.0},
  "M2": {"learning_rate": 0.001, "weight_decay": 0.0001},
  "checkpoint_rule": pre["R13_train_only_hp_selection"]["checkpoint_selection_within_a_run"],
  "stopping_rule": "early stopping on the held-out TRAIN-R internal fold only; "
      "VALIDATION-class data is never used for stopping",
  "refit_step_rule": pre["R13_train_only_hp_selection"]["refit_step_rule"],
  "train_internal_folds": {"folds": 2, "grouping_unit": "LAYOUT",
    "membership_authority": "the frozen clean-room TRAIN-R registry, never the layout-id string",
    "balance": "each fold contains exactly one layout per family f1-f10"},
  "seeds": [11, 29, 47],
  "seed_addition_after_clean_room_data_exists": "FORBIDDEN",
  "post_SELECT_R_retraining": "FORBIDDEN",
  "fits_per_learned_family": "3 seeds x 2 folds for step determination, then 3 refits",
 },

 # ---------------------------------------------------------------- 8, 9 ---
 "family_statistic": {
  "definition": "FamilyNLL(f) = ( NLL(f,11) + NLL(f,29) + NLL(f,47) ) / 3 on SELECT-R",
  "is_a_mean_of_per_seed_selection_NLLs": True,
  "is_not": ["best seed","median seed","seed47 only","ensemble probabilities",
             "averaged logits","checkpoint averaging"],
  "bootstrap_replicate_order": ["resample source episodes ONCE, paired across every "
      "seed and family","compute the event-equal NLL for each seed on that resample",
      "average the three per-seed NLLs","that is the replicate's family statistic"],
  "implementation": "rvt_swarm/cleanroom/family_statistic.py::family_statistic_replicates",
  "implementation_sha256": ENGINE["family_statistic.py"],
  "interpretation_left_to_orchestration": "NONE",
 },
 "downstream_representative": {
  "rule": "downstream representative seed = 47 for whichever learned family wins",
  "fixed_before_clean_room_data_exists": True,
  "selected_using_SELECT_R": False,
  "all_three_seeds_participate_in_family_selection": True,
  "role": "the predefined runtime representative AFTER family selection only",
  "implementation_sha256": ENGINE["selection.py"],
 },

 # --------------------------------------------------------------- 10, 11 ---
 "family_selection_rule": {
  "primary_metric": "event-equal grouped Bernoulli NLL",
  "M0_prior": "its TRAIN-R-fitted constant prior",
  "deltas": {"d10": "FamilyNLL(M1) - NLL(M0)", "d20": "FamilyNLL(M2) - NLL(M0)",
             "d21": "FamilyNLL(M2) - FamilyNLL(M1)"},
  "bootstrap": {"episode_universe": "the manifest-enumerated SELECT-R source episodes, "
      "zero-yield included", "resampling_unit": "SOURCE_EPISODE",
      "stratification": "SELECT-R LAYOUT", "replicates": 10000, "seed": 20260901,
      "ci_method": "95 percent percentile, paired"},
  "eligibility": ["M1 eligible iff upper95CI(d10) < 0","M2 eligible iff upper95CI(d20) < 0"],
  "winner": ["neither eligible -> M0","only one eligible -> that family",
             "both eligible -> M2 iff upper95CI(d21) < 0, else M1 by parsimony"],
  "single_executable_implementation": "rvt_swarm/cleanroom/selection.py::select_family",
  "implementation_sha256": ENGINE["selection.py"],
  "duplicated_in_orchestration": False,
 },
 "predictor_stop_rule": {
  "if_SELECT_R_does_not_support_M2": "STOP the M2-centric clean-room thesis programme",
  "do_not_inspect_MAIN_R": True,
  "do_not_redesign_using_SELECT_R": True,
  "any_redesign_becomes": "a NEW PILOT cycle requiring a future new clean-room programme",
  "if_M2_wins": "carry the newly trained M2 seed-47 checkpoint forward",
 },

 # --------------------------------------------------------------- 12, 13 ---
 "closed_loop_architecture": {
  "runtime_decentralization": "REQUIRED",
  "information_flow": ["local sensing + neighbor messages","local graph / local observations",
    "frozen predictor q_i(o_i, tau)","candidate-topology counterfactual evaluation",
    "decentralized topology selector","nominal local swarm control",
    "local obstacle/safety projection","actuation"],
  "forbidden_final_runtime_dependency": "a centralized global-state controller",
  "centralized_computation_allowed_only_for": "offline training and explicitly declared "
      "development diagnostics",
  "bound_components": {
   "candidate_topologies": "rvt_swarm/topology_registry.py -- KEEP=0, LINE=2, COMPACT=5",
   "counterfactual_chooser": "rvt_swarm/safety.py::choose_counterfactual_topology",
   "selector": "rvt_swarm/safety.py::select_topology_from_score_signal",
   "switch_readiness": "rvt_swarm/safety.py::topology_switch_readiness",
   "admissibility_scope": "rvt_swarm/decentralized/online_topology_scope.py",
   "local_safety_projection": "rvt_swarm/decentralized/local_safety_projection.py::RobotLocalSafetyProjection",
   "local_control": "rvt_swarm/decentralized/local_controller.py, robot_local_controller.py",
   "consensus_and_messaging": "rvt_swarm/decentralized/consensus.py, comms.py, transition_protocol.py",
   "ego_graph": "rvt_swarm/decentralized/ego_graph_v2.py"},
  "known_integration_gap": "select_topology_from_score_signal currently thresholds a "
   "score at >= 0.0 and carries no dwell or hysteresis parameter. Mapping a probability "
   "q in (0,1) onto that score, and any dwell or hysteresis, are integration decisions "
   "that must be developed on CL-DEV-R inside the declared design space and frozen at CR-8.",
 },
 "closed_loop_development_space": {
  "tunable_on_CL_DEV_R": ["the probability-to-score mapping and its topology-selection "
    "threshold","hysteresis","switching dwell time","consensus parameters",
    "recoverability aggregation across robots and candidates","nominal-controller gains",
    "safety-projection integration parameters"],
  "may_not_change": ["the central recoverability target","the selected predictor family",
    "the predictor trained weights","the predictor inputs (the frozen input contract)",
    "the decentralization requirement","the central scientific thesis"],
  "development_budget": {
   "maximum_evaluated_configurations": 40,
   "ledger": "an append-only hash-chained CL-DEV-R ledger; every evaluated configuration "
       "is recorded with its parameters and its development endpoints before the next is run",
   "stopping_procedure": "stop at 40 configurations, or after 3 consecutive configurations "
       "fail to improve the primary development endpoint, whichever comes first",
   "unlogged_configuration": "counts as a protocol violation"},
 },

 # ------------------------------------------------------------------ 14 ---
 "oracle_ceiling": {
  "purpose": "test whether counterfactual recoverability information could in principle "
      "improve topology decisions",
  "definition": "the learned predictor q_i(o_i, tau) is replaced by the simulator-computed "
      "recoverability probability p(x, tau) = P(Target-V4 = 1 | x, tau) under the frozen "
      "iid disturbance law, estimated by the frozen replica protocol from the TRUE full "
      "state. Every downstream stage -- counterfactual evaluation, selector, nominal "
      "control, safety projection -- is byte-identical to the learned system.",
  "privileged_information": "full state and forward rollouts, simulator-only",
  "deployable": False,
  "frozen_before_CL_DEV_R_exists": True,
  "interpretation_rule": {
   "oracle_does_not_materially_improve_the_frozen_development_endpoints_over_the_reactive_baseline":
       "CORE_RECOVERABILITY_DECISION_PREMISE_AT_RISK; do not proceed automatically to MAIN-R",
   "oracle_helps_but_learned_RVT_does_not":
       "the predictor, ranking, selector or integration remains a development problem, "
       "not a refutation of the premise"},
 },

 # ------------------------------------------------------------------ 15 ---
 "diagnostic_causal_chain": ["predictor quality","candidate-topology ranking",
   "selector decision","actual recoverability change","recovery","progress / liveness","safety"],
 "development_diagnostics": ["topology ranking regret","switch frequency",
   "unnecessary switching","delayed switching","recovery success","time-to-recovery",
   "progress","deadlock duration","mission completion","collision","minimum clearance",
   "TTC violations","safety-projection activation rate"],
 "diagnostics_guide_CR7_only": True,

 # ------------------------------------------------------------------ 16 ---
 "baselines_and_ablations": {
  "B0_fixed_topology": "fixed COMPACT and fixed LINE, no adaptation",
  "B1_reactive_adaptation": "topology adaptation from instantaneous geometry and safety "
      "only, with no recoverability estimate",
  "R1_full_rvt": "the frozen winning family at the downstream representative seed, "
      "recoverability-aware counterfactual topology adaptation",
  "A1_recoverability_removed": "the identical selector with the recoverability score "
      "replaced by a constant, isolating the selector machinery from the estimate",
  "A2_topology_blinded": "the predictor evaluated with candidate_topology_id held fixed, "
      "testing whether q(o_i, tau) is really q(o_i); maps to the TOPOLOGY_CONDITIONING_WEAKNESS "
      "falsification condition",
  "A3_capacity_matched_non_message_passing": "a non-message-passing predictor matched as "
      "closely as practical to M2 on parameter count and input processing, trained on "
      "TRAIN-R under the identical frozen recipe. This is the ONLY admissible basis for a "
      "message-passing causality claim and must be frozen at CR-8 before MECH-R exists.",
  "O1_oracle": "development-only unless separately justified",
  "M1_vs_M2_alone_may_claim_message_passing_causality": False,
 },

 # ------------------------------------------------------------------ 17 ---
 "safety_contract": {
  "safety_is_a_core_outcome": True,
  "primary_endpoints": ["collisions","minimum clearance","TTC violations",
    "severe near-collision events","safety-projection intervention rate"],
  "endpoint_implementations": "rvt_swarm/safety.py::{time_to_collision,collision_risk}, "
      "rvt_swarm/metrics.py, rvt_swarm/decentralized/local_safety_projection.py",
  "interpretation_rule": "progress or recovery improvement accompanied by unacceptable "
      "safety degradation DOES NOT support the central claim",
  "silent_safety_for_progress_trade": "FORBIDDEN",
  "exact_effect_sizes_and_non_inferiority_margins": "resolved and frozen before CR-8, "
      "never after MAIN-R exists",
 },

 # ------------------------------------------------------------------ 18 ---
 "closed_loop_hypotheses": {
  "H-CL1": "recoverability-aware decentralized topology adaptation improves recovery, "
      "task progress and liveness relative to the frozen no-recoverability reactive comparator",
  "H-CL2": "the improvement is achieved without unacceptable degradation in obstacle "
      "avoidance and safety",
  "H-CL3": "removing or blinding the recoverability-topology mechanism reduces the "
      "benefit, supporting the proposed mechanism",
  "no_predictor_NLL_result_alone_can_satisfy_these": True,
  "exact_endpoints_and_effect_definitions_resolved_before": "CR-8",
 },

 # ------------------------------------------------------------- 19, 20, 21 ---
 "main_r_firewall": {
  "MAIN_R_generated_before_system_freeze": False,
  "generation_permitted_only_at": "CR-9, after CR-8 complete-system freeze",
  "immutable_at_CR8": ["predictor","selector","controller","consensus and message logic",
    "safety projection","thresholds","baselines","ablations","seeds",
    "scenario-generation contract","metrics","bootstrap and statistics",
    "interpretation rules","orchestration code","independent verifier"],
  "enforcement": "the CR-9 generation driver refuses to run unless the CR-8 freeze root "
      "verifies and the MAIN-R role manifest does not yet exist; role manifests are "
      "enumerated, so an existing MAIN-R identity set is detectable and fails closed"},
 "main_r_failure_rule": {
  "on_failure": "the frozen clean-room system failed confirmation",
  "forbidden_after_failure": ["threshold tuning","retraining","metric substitution",
    "seed changes","inventing a new baseline from the results","outcome exclusion",
    "any rescue run on MAIN-R"],
  "a_future_improved_version_requires": ["return to development","a new system version",
    "a NEW future confirmatory set"],
  "MAIN_R_reused_for_development": False},
 "mechanism_study": {
  "uses_a_separately_generated_MECH_R": True,
  "mechanism_contrasts_frozen_at": "CR-8, before MECH-R exists",
  "redesign_after_MAIN_R_outcomes": "FORBIDDEN",
  "if_MAIN_R_passes_but_mechanism_fails": "the system-level benefit may survive, but the "
      "recoverability-specific and graph-specific causal claims must be weakened"},

 # ------------------------------------------------------------------ 22 ---
 "protected_generalization": {
  "inaccessible_until": "the clean novelty checkpoint",
  "intended_stress_dimensions": ["unseen layouts","team-size shifts",
    "environment and obstacle shifts","partial-observability stress"],
  "forbidden_after_reveal": ["model selection","controller tuning","threshold tuning",
    "ablation redesign"],
  "F9_local_observability": "preserved as a PREDECLARED analysis dimension. RobotView "
   "carries static obstacle tokens only and dynamic obstacles never enter the ego graph; "
   "this limitation is analysed, not repaired after results.",
 },

 # ------------------------------------------------------------------ 23 ---
 "generation_timing": {
  "TRAIN-R": "after CR-0", "SELECT-R": "after the model recipes are frozen and "
      "preferably after CR-2 training completes",
  "CL-DEV-R": "development only", "MAIN-R": "ONLY after CR-8",
  "MECH-R": "only after the mechanism contract freeze",
  "PROTECTED-R": "only after the required upstream freezes and checkpoints",
  "every_role_records": ["generation timestamp","generation authority","generator offset",
    "generation seed","enumerated identity sets"],
 },

 # ------------------------------------------------------------------ 24 ---
 "orchestration_authority": {
  "every_scientific_stage_binds": ["library hashes","orchestration-script hash",
    "executable manifest hash","container image digest","source commit","dependency lock"],
  "orchestration_may_reimplement_scientific_rules": False,
  "orchestration_must": "consume the executable manifest and call the qualified engine",
  "on_any_mismatch": "FAIL_CLOSED",
  "fixes": "the pilot gap in which the Stage-5D orchestration script was bound by no hash "
      "and chose a family statistic the frozen rule did not define",
  "clean_room_engine": ENGINE,
  "inherited_qualified_libraries": INHERITED,
 },

 # ------------------------------------------------------------------ 25 ---
 "adversarial_qualification": {
  "required_before_any_clean_room_reveal": True,
  "negative_fixtures_that_must_fail_closed": ["missing episode","extra episode",
    "duplicate episode","zero-yield episode omitted","wrong layout membership",
    "wrong checkpoint","wrong seed","missing seed","extra seed","wrong family statistic",
    "best-seed substitution","wrong bootstrap count","wrong bootstrap seed","wrong metric",
    "wrong event weighting","calibration integrity violation","unauthorized optimizer path",
    "unauthorized temperature scaling","unauthorized threshold tuning"],
  "engine_suite_at_CR0": {"path": "tests/test_cleanroom_engine.py",
    "sha256": h("tests/test_cleanroom_engine.py"), "tests": 29, "result": "29 passed",
    "covers": ["missing episode","extra episode","duplicate episode",
      "zero-yield episode retained","wrong layout membership","missing seed","extra seed",
      "wrong seed set","best-seed substitution","wrong family statistic",
      "ragged event counts","frozen bootstrap constants","strict eligibility at zero",
      "inverted interval","fixed downstream seed","calibration non-identifiability",
      "calibration integrity violation hard-fails","temperature scaling not activated"]},
  "still_to_qualify_at_CR1_and_beyond": ["wrong checkpoint","wrong bootstrap count",
    "wrong bootstrap seed","wrong metric","wrong event weighting",
    "unauthorized optimizer path","unauthorized threshold tuning"],
  "qualification_root_recorded_at": "each stage that runs the suite it depends on",
 },

 # ------------------------------------------------------------------ 26 ---
 "calibration_contract": {
  "role": "SECONDARY_DIAGNOSTIC",
  "participates_in_selection": False,
  "elevation_requires": "an explicit hypothesis frozen before the relevant data exists",
  "identifiability_tested_first_and_explicitly": True,
  "rule": "if the number of distinct logits < 2 then calibration_identifiable = false, "
      "intercept = null, slope = null",
  "broad_exception_catching_reinterpreted_as_non_identifiability": "FORBIDDEN",
  "all_other_calibration_contract_violations": "HARD_FAIL",
  "temperature_scaling": "NOT_ACTIVATED",
  "implementation": "rvt_swarm/cleanroom/calibration_contract.py::clean_room_calibration",
  "implementation_sha256": ENGINE["calibration_contract.py"],
  "fixes": "the pilot wrapper that caught CalibrationContractError as a bare type across "
      "all families and wrote a hard-coded, unverified explanation into a sealed record",
 },

 # ------------------------------------------------------------------ 27 ---
 "independent_verifier": {
  "required_for_every_confirmatory_stage": True,
  "source_frozen_before": "outcome reveal",
  "must_independently_reconstruct": ["dataset universe","model hashes","metric values",
    "bootstrap inputs","bootstrap results","the pass/fail decision","the artifact root"],
  "written_after_seeing_outcomes": "FORBIDDEN",
 },

 # ------------------------------------------------------------------ 28 ---
 "interpretation_claim_mapping": [
  {"if": "SELECT-R supports M2 under the frozen rule", "then": "the predictor-family premise survives"},
  {"if": "M2 does not win clean SELECT-R", "then": "stop the M2-centric clean-room programme"},
  {"if": "the oracle does not help on CL-DEV-R",
   "then": "the recoverability-as-decision-variable premise is at risk; do not proceed automatically to MAIN-R"},
  {"if": "MAIN-R improves progress but safety fails", "then": "THE CENTRAL CLAIM FAILS"},
  {"if": "MAIN-R system benefit passes but the mechanism contrast fails",
   "then": "the system benefit may be claimed; the mechanism-specific claim may NOT"},
  {"if": "protected generalization fails", "then": "do not claim broad generalization"},
  {"rule": "no result may be rhetorically upgraded after reveal"}],

 # ------------------------------------------------------------------ 31 ---
 "cr0_state": {
  "clean_room_dataset_generated": False,
  "clean_room_model_trained": False,
  "selection_run": False,
  "closed_loop_simulation_run": False,
  "TRAIN-R_exists": False, "SELECT-R_exists": False, "CL-DEV-R_exists": False,
  "MAIN-R_exists": False, "MECH-R_exists": False, "PROTECTED-R_exists": False},
}
sealed = attach_canonical_hash(body, "rvt_swarm_clean_room_global_contract_root")
out = R / "rvt_swarm_clean_room_global_contract_v1.json"
out.write_text(json.dumps(sealed, indent=1, sort_keys=True) + "\n", encoding="ascii")
print("CLEAN_ROOM_GLOBAL_CONTRACT_ROOT", sealed["rvt_swarm_clean_room_global_contract_root"])
print("file_sha256", hashlib.sha256(out.read_bytes()).hexdigest())
print("bytes", out.stat().st_size)
