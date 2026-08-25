"""Stage 5E -- post-reveal integrity adjudication + novelty checkpoint 1."""
from __future__ import annotations
import hashlib, json, pathlib, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import attach_canonical_hash

R = pathlib.Path("/Users/udy/rvt/results/rvt_fd24")
def fh(p): return hashlib.sha256((R / p).read_bytes()).hexdigest()
man = json.loads((R / "open_loop_v3_validation_evaluation_manifest_v1.json").read_text())
sel = json.loads((R / "open_loop_v3_validation_selection_v1.json").read_text())
res = json.loads((R / "validation_evaluation_result_v1.json").read_text())
rule = json.loads((R / "open_loop_v3_family_selection_rule_v1.json").read_text())

body = {
 "schema_version": "rvt-open-loop-v3-novelty-checkpoint/v1",
 "name": "OPEN_LOOP_V3_NOVELTY_CHECKPOINT_1",
 "stage": "STAGE_5E",
 "status": "POST_REVEAL_AUTHORITY_FAILURE_ADJUDICATED",
 "verdict": "C_POST_REVEAL_AUTHORITY_OR_PROVENANCE_FAILURE",
 "advance_to_closed_loop_authorized": False,

 "immutable_facts_not_altered_by_this_stage": {
  "validation_reveal_occurred": True,
  "validation_reveal_timestamp_utc": res["validation_reveal_timestamp_utc"],
  "validation_status": "SPENT_MODEL_SELECTION_SET",
  "family_winner_as_executed": "M2",
  "frozen_model_as_executed": "M2-seed47",
  "validation_can_be_reblinded": False,
 },

 "authority": {
  "open_loop_v3_recoverability_predictor_preregistration_v1_sha256":
      "8619ac4c8a60740209d826910d9002d12d63f825886b4869e08c883024e7dbf6",
  "open_loop_v3_family_selection_rule_v1_sha256":
      "f65e60fee5b5c0e7249b3594a25d4cb54bf826c19be2cf3aad75df5f1b72f1f5",
  "open_loop_v3_validation_evaluation_manifest_v1_sha256":
      man["open_loop_v3_validation_evaluation_manifest_v1_sha256"],
  "open_loop_v3_validation_selection_root": sel["open_loop_v3_validation_selection_root"],
  "open_loop_v3_train_model_development_root":
      "1ed37294a787f6eb232e5fc0ccbba88ec2d36d3ba974bb17233d0d5a5ca76f33",
  "official_v3_validation_seal_root":
      "770957243df01a4077ef331e55b1e6ee892b64f2c410112e656ed38832fd8d84",
  "official_v3_validation_content_root":
      "fa12acba2e8fffc0ba85a992fca9d18654d9e14d0efef1bca366a760ca390283",
  "frozen_m2_checkpoint_sha256":
      "84ec5025a270f97e0a2aab2d5f4fb7a47d23897141c315b1802cf3860abf0a46",
  "all_authority_items_exact": True,
 },

 "finding_1_seed_family_statistic": {
  "classification": "FROZEN_SPECIFICATION_NOT_EXECUTED",
  "severity": "DISQUALIFYING_FOR_THIS_SELECTION",
  "frozen_requirement": rule["family_statistic"],
  "what_was_executed": "a single checkpoint per learned family, training_seed 47, "
                       "evaluated once on VALIDATION",
  "checkpoints_that_existed_at_reveal_time": [
      "M1-seed11.pt", "M1-seed29.pt", "M1-seed47.pt",
      "M2-seed11.pt", "M2-seed29.pt", "M2-seed47.pt"],
  "why_r18_does_not_authorise_it": [
   "R18 designates a MEDIAN of a TRAIN-only cross-validation NLL; the rule "
   "requires a MEAN of the VALIDATION NLL -- different statistic, different split",
   "R18's later_use is 'this checkpoint may be used for closed-loop integration "
   "if its family wins', which presupposes a winner already chosen by the rule",
   "R18 imposes 'all three seeds remain reported for stability'; no per-seed "
   "VALIDATION number exists in any Stage-5D artifact",
  ],
  "no_amendment_exists": {
   "preregistration_supersedes": None,
   "manifest_declares_itself_bound_by_the_rule": True,
   "deviation_declared_anywhere": False,
  },
  "collateral_effect": "R19 falsification condition SEED_INSTABILITY ('the effect "
                       "size is not robust relative to across-seed variation') is "
                       "structurally unevaluable from a single seed",
  "selection_record_assertion_rule_modified_false": "TEXTUALLY TRUE, CONFORMANCE FALSE: "
      "the rule document was not edited, but the executed statistic is not the one it defines",
  "independent_adjudication": {"verdict": "VIOLATES_FROZEN_SPEC", "confidence": "high",
                               "adversarial_refuters": 4, "refuted": 0},
 },

 "finding_2_bootstrap_pool": {
  "classification_294": "NONAUTHORITATIVE_EXECUTION_DEFECT",
  "classification_300": "EXECUTION_CORRECTION_TO_FROZEN_SPECIFICATION",
  "frozen_requirement": "within each VALIDATION layout, resample that layout's source "
                        "episodes with replacement preserving that layout's original "
                        "episode count",
  "frozen_zero_yield_clause": "an episode with M = 0 contributes no events and that is "
                              "correct; a replicate yielding zero events overall would FAIL CLOSED",
  "original_source_episodes": 300,
  "contributing_episodes": 294,
  "zero_yield_episodes": 6,
  "zero_yield_location": "all six sit in layout F4, cell F4/N16 (M_zero 6, selected_events 0)",
  "concrete_defect": "every layout has 30 original source episodes; the 294-pool made "
                     "layout F4 draw 24 from 24 instead of the required 30 from 30. "
                     "The other nine layouts were unaffected.",
  "scientific_specification_changed_after_reveal": False,
  "held_fixed_across_both_passes": ["bootstrap seed", "replicate count", "cluster unit",
      "layout stratification", "metric", "prediction artifacts", "family candidates",
      "winner rule"],
  "winner_changed_by_the_correction": False,
  "independent_adjudication": {"verdict": "CONFORMS_TO_FROZEN_SPEC", "confidence": "high",
                               "adversarial_refuters": 2, "refuted": 1,
                               "surviving_criticism": "the superset-pool code path was "
      "never exercised by the Stage-5B qualification suite and ran for the first time "
      "post-reveal; the reveal globs stage_a records without hash-checking them against "
      "stage_a_root and without asserting the pool size equals 300"},
 },

 "finding_3_m0_calibration": {
  "mathematics": {
   "distinct_logits": 1,
   "intercept_identifiable": False,
   "slope_identifiable": False,
   "reason": "the frozen objective depends on (a,b) only through a + b z0; with z "
             "constant the argmin is an entire line in R^2 and the 2x2 Hessian is "
             "exactly rank deficient. The minimum VALUE exists; the argmin PAIR does not.",
   "identified_functional": "u* = a + b z0 = logit(mean target)",
   "verified_independently": True,
  },
  "calibration_implementation_changed": False,
  "calibration_definition_changed": False,
  "estimator_changed": False,
  "substitute_calibration_method_introduced": False,
  "new_number_fabricated": False,
  "wrapper_defects_found": [
   "the handler catches CalibrationContractError as a bare type inside the family "
   "loop; that type is raised at 11 sites in the frozen module, only one of which is "
   "non-identifiability. A data-integrity violation for any family would have been "
   "recorded as 'not identifiable' instead of failing closed, contrary to the frozen "
   "docstring 'A calibration-contract violation that must fail closed'",
   "the captured exception text is assigned to a dead variable; the serialized "
   "calibration_not_identifiable_reason is a hard-coded literal asserting a mechanism "
   "the code never verified",
   "the frozen composite entry point calibration_report() is imported but never called; "
   "it was replaced by an ad-hoc decomposition emitting a record shape the frozen "
   "CalibrationReport dataclass cannot represent (its intercept and slope are non-Optional)",
   "three reported fields absent from R14 and from the manifest schema were added to "
   "the sealed result: calibration_identifiable, calibration_not_identifiable_reason, "
   "distinct_logits",
  ],
  "realized_harm_in_this_run": "none: M1 and M2 both returned identifiable calibration, "
      "so no data-integrity abort was actually suppressed, and M0's recorded mechanism "
      "is independently confirmed true (distinct_logits == 1). The harm is a weakened "
      "guard and an unverified assertion, not a wrong reported number.",
  "effect_on_primary_metric_or_winner": "none; calibration enters no selection",
  "adjudication": "NOT_PURELY_DIAGNOSTIC_UNDEFINED_HANDLING -- the estimand handling is "
      "correct but the wrapper altered a frozen fail-closed contract and added "
      "post-freeze reported fields",
  "independent_adjudication": {"verdict_initial": "CONFORMS_TO_FROZEN_SPEC",
                               "adversarial_refuters": 2, "refuted": 2,
                               "survives": False},
 },

 "prediction_immutability": {
  "M0_sha256": sel["prediction_artifacts"]["M0"]["artifact_sha256"],
  "M1_sha256": sel["prediction_artifacts"]["M1"]["artifact_sha256"],
  "M2_sha256": sel["prediction_artifacts"]["M2"]["artifact_sha256"],
  "bit_identical_across_all_passes": True,
  "model_rerun_with_changed_parameters": False,
  "prediction_filtering": False, "event_membership_changed": False,
  "checkpoint_changed": False, "seed_changed": False,
  "coverage": {f: sel["prediction_artifacts"][f]["coverage"] for f in ("M0","M1","M2")},
 },

 "authoritative_300_pool_artifacts": {
  "validation_evaluation_result_v1_root": res["validation_evaluation_result_v1_sha256"],
  "validation_evaluation_result_v1_file_sha256": fh("validation_evaluation_result_v1.json"),
  "open_loop_v3_validation_selection_root": sel["open_loop_v3_validation_selection_root"],
  "open_loop_v3_validation_selection_file_sha256": fh("open_loop_v3_validation_selection_v1.json"),
 },
 "defective_294_pool_artifacts": {
  "preservation_status": "HASHES_PRESERVED_FILE_NOT_RECOVERABLE_AT_THIS_TIME",
  "validation_evaluation_result_v1_root":
      "08a595939d7259425f067cb028290df45cf4d662187ca149b42fc114a08c39f2",
  "validation_evaluation_result_v1_file_sha256":
      "6c8707d51a5c9ad4add685b0fed228d6431ecfb2f0c7e97aafbbd19e0b7cb4c4",
  "deltas": {
   "delta_10": {"ci_lower_95": -0.3178322136677876, "ci_upper_95": -0.2788109250656001},
   "delta_20": {"ci_lower_95": -0.3769675099126452, "ci_upper_95": -0.3267360605209061},
   "delta_21": {"ci_lower_95": -0.06637992043994827, "ci_upper_95": -0.040374116822821195}},
  "note": "the defective result file was overwritten in place by the corrected pass "
          "before the preservation instruction existed; its roots and intervals survive "
          "in the execution record and are bound here. Byte-level reconstruction is "
          "pending compute-host availability and must never be treated as authoritative.",
  "deleted_deliberately": False,
 },

 "authoritative_metrics_as_executed": {
  f: {"validation_nll": res["aggregate_metrics"][f]["validation_nll"],
      "validation_brier": res["aggregate_metrics"][f]["validation_brier"],
      "expected_calibration_error": res["aggregate_metrics"][f]["expected_calibration_error"],
      "calibration_intercept": res["aggregate_metrics"][f]["calibration_intercept"],
      "calibration_slope": res["aggregate_metrics"][f]["calibration_slope"]}
  for f in ("M0", "M1", "M2")},
 "authoritative_bootstrap_as_executed": res["paired_bootstrap"]["deltas"],
 "winner_re_derivation": {
  "reproduced_with_frozen_select_family": True,
  "m1_eligible": True, "m2_eligible": True, "case": 4, "winner": "M2",
  "rule_document_modified": False,
  "caveat": "re-derivation confirms the recorded numbers follow from the recorded "
            "intervals; it does NOT cure finding_1, because the inputs are single-seed "
            "statistics rather than the frozen three-seed means",
 },

 "evidence_ledger": {
  "H1_learned_recoverability_signal": {
   "status": "SUSPENDED_PENDING_FROZEN_STATISTIC",
   "note": "the single-seed margins are very large (upper95 -0.279 and -0.327 against "
           "M0), so the learnability direction is unlikely to be seed-fragile, but the "
           "frozen statistic was not computed and the claim cannot be certified"},
  "H2_graph_family_predictive_advantage": {
   "status": "SUSPENDED_PENDING_FROZEN_STATISTIC",
   "note": "d21 upper95 is -0.0403 -- the narrowest margin and the branch most exposed "
           "to across-seed variation, which is exactly what the frozen three-seed mean "
           "and R19 SEED_INSTABILITY exist to test"},
  "H3_causal_graph_structure_advantage": {"status": "NOT_YET_ESTABLISHED",
   "note": "M1 and M2 differ in capacity and architecture as well as message passing; "
           "H2 must never be converted into H3"},
  "H4_calibrated_probability_quality": {"status": "IMPERFECT_CALIBRATION_NOT_FATAL",
   "m2_intercept": 0.25591843208612364, "m2_slope": 0.79436463626813,
   "m2_ece": 0.031536231394961554,
   "note": "slope below 1 indicates over-confidence under the frozen diagnostic; the "
           "predictor is NOT perfectly calibrated. Temperature scaling remains forbidden"},
  "H5_counterfactual_topology_decision_benefit": {"status": "NOT_YET_ESTABLISHED",
   "note": "no direct evidence; requires closed-loop experiments"},
  "H6_progress_recovery_liveness_benefit": {"status": "NOT_YET_ESTABLISHED",
   "note": "requires closed-loop experiments"},
  "H7_safety_preservation": {"status": "NOT_YET_ESTABLISHED",
   "note": "requires closed-loop safety metrics and projection evaluation"},
  "H8_protected_domain_generalization": {"status": "NOT_YET_ESTABLISHED",
   "note": "protected domains remain untouched and must stay so"},
 },

 "paper_safe_claim_boundary": {
  "allowed_now": [
   "Under the preregistered open-loop protocol, a single preregistered VALIDATION "
   "reveal was executed and is spent.",
   "All frozen dataset seals, authority roots and metric implementations verify exact.",
  ],
  "suspended_pending_resolution": [
   "the graph-based predictor M2 achieved lower event-equal grouped Bernoulli NLL than "
   "the constant baseline and than M1 on the frozen model-selection set",
   "the result supports a graph-family predictive advantage",
  ],
  "not_allowed": [
   "graph message passing causes the gain",
   "RVT improves topology selection", "RVT improves closed-loop recovery",
   "RVT improves safety", "RVT generalizes", "RVT is state of the art",
   "the predictor is well calibrated",
  ]},

 "novelty_thesis_status": {
  "thesis": "probabilistic recoverability can serve as a predictive decision variable "
            "for counterfactual topology adaptation in decentralized swarm control",
  "status": "HOLD_PENDING_SELECTION_STATISTIC_RESOLUTION",
  "predictor_premise": "DIRECTIONALLY_INDICATED_BUT_NOT_CERTIFIED",
  "topology_control_premise": "NOT_YET_TESTED",
  "novelty_proven": False},

 "frozen_closed_loop_questions": {
  "Q1": "Does using frozen recoverability estimates in topology selection improve task "
        "progress, recovery and liveness relative to a controller without recoverability "
        "reasoning?",
  "Q2": "Does it preserve safety rather than trading collisions and near-collisions for "
        "progress?",
  "Q3": "Is any benefit specifically due to counterfactual topology-conditioned "
        "recoverability rather than simply extra model capacity?",
  "Q4": "Does probabilistic reasoning outperform a deterministic or binary recoverability "
        "variant where scientifically valid?",
  "Q5": "Where does the F9 local-observability limitation cause failure?",
  "outcomes_designed_before_protected_data": True},

 "protected_domains": {
  "n24_reserve_accessed": False,
  "final_generalization_reserve_accessed": False,
  "closed_loop_final_test_reserve_accessed": False,
  "protected_outcomes_accessed": 0,
  "protected_domain_contact": "NONE"},

 "this_stage_performed": {
  "training": False, "refitting": False, "recalibration": False,
  "seed_reselection": False, "checkpoint_change": False,
  "new_validation_analysis": False, "closed_loop_experiments": False,
  "artifacts_rewritten_to_repair_authority": False},
}
sealed = attach_canonical_hash(body, "open_loop_v3_novelty_checkpoint_1_root")
out = R / "open_loop_v3_novelty_checkpoint_1_v1.json"
out.write_text(json.dumps(sealed, indent=1, sort_keys=True) + "\n", encoding="ascii")
print("NOVELTY_CHECKPOINT_1_ROOT", sealed["open_loop_v3_novelty_checkpoint_1_root"])
print("file_sha256", hashlib.sha256(out.read_bytes()).hexdigest())
print("bytes", out.stat().st_size)
