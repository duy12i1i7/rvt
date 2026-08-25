"""CR-0S -- amend to V3, closing the final three closed-loop degrees of freedom."""
from __future__ import annotations
import copy, hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import attach_canonical_hash, verify_canonical_hash
from rvt_swarm.cleanroom.benefit_contract import (
    BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED, COMPARATOR_ARM, CONFIDENCE_LEVEL,
    FORBIDDEN_WITHOUT_PRIMARY_PASS, MAXIMUM_INVALID_EPISODE_FRACTION,
    PERMITTED_DESCRIPTION_WHEN_SUBTHRESHOLD, PRACTICAL_BENEFIT_THRESHOLD, PRIMARY,
    SEQUENCE, TREATMENT_ARM,
)
from rvt_swarm.cleanroom.development_selection import (
    CONSECUTIVE_NON_IMPROVEMENTS_TO_STOP, MAXIMUM_EVALUATED_CONFIGURATIONS,
    NO_ADMISSIBLE_CONFIGURATION,
)
from rvt_swarm.cleanroom.oracle_contract import (
    ORACLE_ARM, ORACLE_HEADROOM_FAIL, ORACLE_HEADROOM_PASS, ORACLE_PRACTICAL_THRESHOLD,
    PREMISE_AT_RISK,
)

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def h(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
v1 = json.loads((R / "rvt_swarm_clean_room_global_contract_v1.json").read_text())
v2 = json.loads((R / "rvt_swarm_clean_room_global_contract_v2.json").read_text())
assert verify_canonical_hash(v2, "rvt_swarm_clean_room_global_contract_root")
V1_ROOT = v1["rvt_swarm_clean_room_global_contract_root"]
V2_ROOT = v2["rvt_swarm_clean_room_global_contract_root"]

v3 = copy.deepcopy(v2)
del v3["rvt_swarm_clean_room_global_contract_root"]
v3["schema_version"] = "rvt-swarm-clean-room-global-contract/v3"
v3["name"] = "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V3"
v3["stage"] = "CR-0S"
v3["cr0_source_commit"] = subprocess.run(
    ["git","-C",str(ROOT),"rev-parse","HEAD"], capture_output=True, text=True).stdout.strip()
v3["amendment"] = {
 "amends": "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V2",
 "lineage": ["RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V1",
             "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V2"],
 "v1_root": V1_ROOT, "v1_tag": "rvt-cleanroom-cr0-v1",
 "v2_root": V2_ROOT, "v2_tag": "rvt-cleanroom-cr0r-v2",
 "v1_preserved_unmodified": True, "v2_preserved_unmodified": True,
 "made_before_any_clean_room_data_existed": True,
 "made_before_any_clean_room_model_training": True,
 "no_empirical_clean_room_outcome_informed_these_changes": True,
 "scope": ["exact H-CL1 benefit endpoint and statistical success rule",
           "exact oracle-ceiling go/no-go criterion",
           "exact CL-DEV-R final-configuration selection rule",
           "the qualification requirements and interpretation rules those imply"],
 "all_other_v2_decisions": "PRESERVED",
 "final_pre_data_closure": True,
 "further_cr0_amendments": "NOT PERMITTED unless a genuine authority or runtime defect "
     "is discovered before data generation",
}

# ------------------------------------------------ closure 1: H-CL1 benefit ---
v3["h_cl1_benefit_contract"] = {
 "status": "FULLY_SPECIFIED_AT_CR0S -- no future benefit-metric choice remains",
 "metric_source": "every endpoint is already emitted by the frozen evaluator "
     "rvt_swarm/metrics.py; no new metric was invented",
 "threshold_source": "results/rvt_fd24/phase9d_h1_requirement_map_v1.json, whose frozen "
     "H1 reads: 'Recoverability selection improves episode task success by at least 0.08 "
     "absolute over both direct classification and local geometric selection, while "
     "meeting the frozen collision gate.' The 0.08 absolute margin is reused verbatim.",
 "treatment_arm": TREATMENT_ARM, "comparator_arm": COMPARATOR_ARM,
 "treatment_contrast": f"{TREATMENT_ARM} minus {COMPARATOR_ARM}",
 "comparator_substitution_after_MAIN_R": "FORBIDDEN -- no substitution with a fixed-"
     "topology arm, an easier baseline, or the best-looking comparator",
 "additional_baselines": "descriptive or secondary only; they never replace B1",
 "primary_endpoint": {
   "key": PRIMARY.key, "concept": PRIMARY.concept, "metric_key": PRIMARY.metric_key,
   "definition": PRIMARY.definition, "unit": PRIMARY.unit,
   "aggregation_unit": PRIMARY.aggregation_unit,
   "direction_of_benefit": PRIMARY.direction_of_benefit,
   "estimator": "difference in per-episode rate between the two arms",
   "interval": "paired stratified cluster bootstrap over source episodes, stratified by "
       f"layout, {BOOTSTRAP_REPLICATES} replicates, seed {BOOTSTRAP_SEED}, "
       f"{int(CONFIDENCE_LEVEL*100)} percent percentile",
   "practical_benefit_threshold": PRACTICAL_BENEFIT_THRESHOLD,
   "pass_rule": f"lower95(treatment - comparator) > {PRACTICAL_BENEFIT_THRESHOLD}, strictly",
   "why_success_includes_collision_free": "the frozen `success` predicate requires "
       "collision-freeness, so an unsafe episode cannot be credited as a benefit. The "
       "entanglement is conservative: it can only depress the benefit of an unsafe "
       "system, never inflate it, which makes the conjunction with H-CL2 doubly "
       "protective rather than circular."},
 "fixed_sequence": [
   {"rank": e.rank, "key": e.key, "concept": e.concept, "metric_key": e.metric_key,
    "definition": e.definition, "unit": e.unit, "aggregation_unit": e.aggregation_unit,
    "direction_of_benefit": e.direction_of_benefit,
    "invalid_episode_imputation": e.invalid_episode_imputation,
    "pass_rule": (f"lower95 > {PRACTICAL_BENEFIT_THRESHOLD}" if e.rank == 1
                  else "the 95 percent bound on the beneficial side is strictly beyond zero")}
   for e in SEQUENCE],
 "scientific_concepts_covered": {
   "task progress": "episode_task_success_rate (primary) and goal_reached_rate (rank 4)",
   "recovery": "irreversible_collapse_rate (rank 3)",
   "liveness / deadlock": "deadlock_rate (rank 2)"},
 "multiplicity": {
   "procedure": "FIXED_SEQUENCE_GATEKEEPING",
   "rule": "endpoints are tested in rank order; each is tested at the full level only if "
       "every preceding endpoint passed, and testing stops at the first failure",
   "alpha_correction": "NONE_REQUIRED",
   "why": "a fixed-sequence procedure controls the family-wise error rate without "
       "correction, because no endpoint is ever tested unless its predecessors were rejected"},
 "h_cl1_pass_rule": "H-CL1 passes if and only if the PRIMARY endpoint passes. The "
     "secondary sequence supports the recovery/progress/liveness wording; it cannot "
     "rescue a failed primary.",
 "tie_strictness": "strict inequality everywhere; equality never passes",
 "invalid_episode_handling": {
   "rule": "an episode that fails to simulate is imputed WORST CASE for the arm in which "
       "it occurred (success 0, deadlock 1, irreversible collapse 1, goal reached 0); "
       "invalid episodes are never silently dropped and are always reported",
   "maximum_invalid_fraction": MAXIMUM_INVALID_EPISODE_FRACTION,
   "above_the_maximum": "the analysis refuses to report and fails closed"},
 "manuscript_language": {
   "improves": f"permitted only when the primary rule passes, i.e. lower95 > {PRACTICAL_BENEFIT_THRESHOLD}",
   "substantially_or_materially_improves": "permitted on the same condition, because the "
       f"frozen margin {PRACTICAL_BENEFIT_THRESHOLD} IS the practical-effect threshold",
   "forbidden_without_a_primary_pass": list(FORBIDDEN_WITHOUT_PRIMARY_PASS),
   "permitted_description_when_positive_but_sub_threshold":
       PERMITTED_DESCRIPTION_WHEN_SUBTHRESHOLD,
   "rhetorical_upgrading_after_reveal": "FORBIDDEN"},
 "implementation": "rvt_swarm/cleanroom/benefit_contract.py",
 "implementation_sha256": h("rvt_swarm/cleanroom/benefit_contract.py"),
}

# ------------------------------------------------- closure 2: oracle rule ---
v3["oracle_ceiling"] = {
 **v2["oracle_ceiling"],
 "arm_identity": ORACLE_ARM,
 "development_only": True,
 "purpose_restated": "possibility and headroom diagnosis, never final evidence",
 "decision_rule": {
   "status": "EXACT -- the word 'materially' is retired",
   "comparator": COMPARATOR_ARM,
   "endpoint": PRIMARY.key,
   "endpoint_note": "the SAME primary endpoint as H-CL1, so headroom is asked on the "
       "same scale as the confirmatory question",
   "dataset": "CL-DEV-R",
   "required_effect_direction": "increase",
   "practical_threshold": ORACLE_PRACTICAL_THRESHOLD,
   "uses_statistical_uncertainty": True,
   "conjunction": "PASS requires ALL THREE: (a) point difference >= "
       f"{ORACLE_PRACTICAL_THRESHOLD}; (b) lower95 strictly above 0, establishing the "
       "sign even where the magnitude is not confirmatory; (c) the oracle arm itself "
       "satisfies the frozen H-CL2 safety non-inferiority rule against the same "
       "comparator, so headroom bought by degrading safety does not count",
   "pass_label": ORACLE_HEADROOM_PASS, "fail_label": ORACLE_HEADROOM_FAIL},
 "on_fail": {"premise_status": PREMISE_AT_RISK,
             "may_proceed_automatically_to_main_r": False},
 "on_pass_but_learned_system_fails": "retain the core possibility claim as a DEVELOPMENT "
     "HYPOTHESIS and diagnose the predictor, candidate ranking, selector or controller "
     "integration; this is not a refutation of the premise",
 "post_cl_dev_reinterpretation_of_oracle_success": "FORBIDDEN",
 "implementation": "rvt_swarm/cleanroom/oracle_contract.py",
 "implementation_sha256": h("rvt_swarm/cleanroom/oracle_contract.py"),
}

# --------------------------------------- closure 3: CL-DEV final selection ---
v3["closed_loop_development_space"] = {
 **v2["closed_loop_development_space"],
 "final_configuration_selection": {
   "status": "EXACT -- no subjective final choice remains",
   "eligibility": ["registered in the append-only hash-chained ledger BEFORE execution",
     "the run completed over the full CL-DEV-R episode universe",
     "the invalid-episode fraction is within the frozen maximum"],
   "safety_feasibility_gate": "the configuration must satisfy the frozen H-CL2 safety "
       "non-inferiority rule against B1 on CL-DEV-R. A configuration that improves "
       "progress while failing this gate is INADMISSIBLE; it is removed from "
       "consideration entirely rather than weighed against its progress gain.",
   "primary_objective": "maximise the point estimate of the primary-endpoint difference "
       "against B1 on CL-DEV-R, among admissible configurations",
   "tie_breakers_in_strict_order": [
     "1. higher lower95 bound on the primary difference",
     "2. lower deadlock rate", "3. lower irreversible-collapse rate",
     "4. higher minimum clearance", "5. fewer topology switches per episode",
     "6. lowest ledger index, i.e. the earliest registered configuration"],
   "tie_strictness": "strict inequality at each level; only exact equality falls through "
       "to the next, and criterion 6 is total, so the outcome is always deterministic",
   "stopping_rule": f"stop at {MAXIMUM_EVALUATED_CONFIGURATIONS} configurations, or after "
       f"{CONSECUTIVE_NON_IMPROVEMENTS_TO_STOP} consecutive configurations fail to improve "
       "the primary objective, whichever comes first",
   "failed_simulations": "a configuration whose run did not complete is inadmissible; it "
       "still consumes budget and remains in the ledger",
   "invalid_episodes": "worst-case imputation, identical to the H-CL1 rule",
   "unlogged_configuration": "a protocol violation; it may never be the final "
       "configuration and the selector fails closed if one is present",
   "no_admissible_configuration_outcome": NO_ADMISSIBLE_CONFIGURATION,
   "on_no_admissible_configuration": "DO NOT create MAIN-R",
   "forbidden": ["visual inspection followed by subjective choice",
     "choosing whichever metric looks best", "changing the objective mid-development",
     "hidden or unlogged runs"],
   "implementation": "rvt_swarm/cleanroom/development_selection.py",
   "implementation_sha256": h("rvt_swarm/cleanroom/development_selection.py")},
 "adaptivity_boundary": {
   "the_method_may_be_developed_adaptively": True,
   "the_final_selection_criterion_may_not_be_adaptive": True,
   "humans_and_agents_may": ["inspect diagnostics", "understand failure modes",
     "propose the next configuration",
     "tune only the parameters this contract already declares tunable"],
   "every_configuration_must_be": "registered before execution and entered in the ledger",
   "the_final_configuration_must": "satisfy the frozen objective and selection rule"},
}

# ------------------------------------------------------------ engine (§9) ---
v3["closed_loop_analysis_engine"] = {
 "single_qualified_entry_point": "rvt_swarm/cleanroom/closed_loop_engine.py::evaluate_closed_loop",
 "implementation_sha256": h("rvt_swarm/cleanroom/closed_loop_engine.py"),
 "consumes": ["the manifest-enumerated source episode universe", "the frozen arm ids",
   "the frozen endpoint definitions", "the frozen treatment contrast",
   "the frozen bootstrap and test parameters", "the safety-contract result"],
 "returns": ["h_cl1_pass", "h_cl2_pass",
             "central_claim: CENTRAL_CLAIM_SUPPORTED or CENTRAL_CLAIM_NOT_SUPPORTED"],
 "orchestration_may_reinterpret_these_values": False,
 "fails_closed_on": ["a swapped treatment and comparator",
   "bootstrap parameters that differ from the frozen contract",
   "an endpoint outside the frozen benefit sequence",
   "an episode universe mismatch", "a missing safety verdict",
   "an invalid-episode fraction above the frozen maximum"],
 "mathematical_contract_immutable_from": "CR-0S",
 "executable_completion": "the implementation exists and is qualified; the closed-loop "
     "data adapters that feed it are written at the stage that first needs them",
}

# ----------------------------------------------- central claim conjunction ---
v3["central_claim_conjunction"] = {
 "rule": "H-CL1 BENEFIT PASS *and* H-CL2 SAFETY PASS => CENTRAL CLOSED-LOOP CLAIM "
     "SUPPORTED. Any other combination => NOT SUPPORTED.",
 "benefit_pass_safety_fail": "CENTRAL_CLAIM_FAILS_SAFETY_NON_INFERIORITY_NOT_MET",
 "benefit_fail": "CENTRAL_CLAIM_FAILS_BENEFIT_NOT_DEMONSTRATED",
 "safety_contract_unchanged_from_v2": True,
 "implementation": "rvt_swarm/cleanroom/closed_loop_engine.py::evaluate_closed_loop",
}
v3["closed_loop_hypotheses"] = {
 **v2["closed_loop_hypotheses"],
 "exact_endpoints_and_effect_definitions_resolved_before":
   "FULLY RESOLVED. Safety endpoints, margins and rule were frozen at CR-0R; the H-CL1 "
   "benefit endpoint, estimator, threshold, multiplicity and success rule are frozen at "
   "CR-0S. No closed-loop outcome definition remains open.",
}

# ------------------------------------------------------ interpretation (§11) ---
v3["interpretation_claim_mapping"] = list(v2["interpretation_claim_mapping"]) + [
 {"if": "H-CL1 fails", "then": "no claim that RVT improves closed-loop task behaviour; "
  "the words 'improves', 'outperforms' and their intensifiers are forbidden"},
 {"if": "H-CL1 passes and H-CL2 passes",
  "then": "a system-level closed-loop benefit is supported, subject to mechanism evidence"},
 {"if": "MAIN-R passes but the MECH-R recoverability mechanism contrast fails",
  "then": "the system benefit may remain; the recoverability-specific causal mechanism "
          "claim is weakened or removed"},
 {"if": "the oracle fails the frozen headroom rule",
  "then": f"{PREMISE_AT_RISK}; do not proceed automatically to MAIN-R"},
 {"if": "no CL-DEV-R configuration is admissible",
  "then": f"{NO_ADMISSIBLE_CONFIGURATION}; do not create MAIN-R"},
 {"if": "the protected instance test fails",
  "then": "no protected-instance generalization claim"},
]

# --------------------------------------------------------- engine + suites ---
v3["orchestration_authority"]["clean_room_engine"] = {
 p: h(f"rvt_swarm/cleanroom/{p}") for p in
 ("__init__.py","universe.py","family_statistic.py","selection.py",
  "calibration_contract.py","safety_contract.py","a3_control.py",
  "benefit_contract.py","oracle_contract.py","development_selection.py",
  "closed_loop_engine.py")}
v3["adversarial_qualification"]["cr0s_suite"] = {
 "path": "tests/test_cleanroom_cr0s.py", "sha256": h("tests/test_cleanroom_cr0s.py"),
 "tests": 28, "result": "28 passed"}
v3["adversarial_qualification"]["closed_loop_negative_fixtures"] = {
 "wrong primary benefit endpoint": "COVERED", "swapped treatment/comparator": "COVERED",
 "omitted episode": "COVERED", "extra episode": "COVERED",
 "subjective alternate metric path": "COVERED", "changed benefit threshold": "COVERED",
 "wrong CI direction": "COVERED", "wrong multiplicity rule": "COVERED",
 "safety result ignored": "COVERED",
 "progress-pass/safety-fail incorrectly marked success": "COVERED",
 "oracle threshold changed": "COVERED",
 "CL-DEV final configuration selected outside frozen rule": "COVERED",
 "unlogged configuration used as final": "COVERED",
 ">40 development configurations": "COVERED", "wrong tie-breaker": "COVERED"}
v3["adversarial_qualification"]["total_tests_passing_at_CR0S"] = 73

sealed = attach_canonical_hash(v3, "rvt_swarm_clean_room_global_contract_root")
out = R / "rvt_swarm_clean_room_global_contract_v3.json"
out.write_text(json.dumps(sealed, indent=1, sort_keys=True) + "\n", encoding="ascii")

def flat(o, p=""):
    if isinstance(o, dict):
        for k in sorted(o): yield from flat(o[k], f"{p}.{k}")
    elif isinstance(o, list): yield p, json.dumps(o, sort_keys=True)
    else: yield p, o
a = dict(flat({k: v for k, v in v2.items() if k != "rvt_swarm_clean_room_global_contract_root"}))
b = dict(flat({k: v for k, v in sealed.items() if k != "rvt_swarm_clean_room_global_contract_root"}))
added = sorted(set(b) - set(a)); removed = sorted(set(a) - set(b))
changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
ALLOWED = ("h_cl1_benefit_contract", "oracle_ceiling", "closed_loop_development_space",
           "closed_loop_analysis_engine", "central_claim_conjunction",
           "closed_loop_hypotheses.exact_endpoints_and_effect_definitions_resolved_before",
           "interpretation_claim_mapping", "adversarial_qualification",
           "orchestration_authority.clean_room_engine", "amendment",
           "schema_version", "name", "stage", "cr0_source_commit")
def allowed(k): return any(k.lstrip(".").startswith(x) for x in ALLOWED)
off = [k for k in added + removed + changed if not allowed(k)]
SAFETY_UNCHANGED = all(a[k] == b[k] for k in a if k.startswith(".safety_contract"))
diff = {
 "schema_version": "rvt-swarm-clean-room-contract-diff/v1",
 "from_root": V2_ROOT, "to_root": sealed["rvt_swarm_clean_room_global_contract_root"],
 "v1_root": V1_ROOT,
 "closures": ["exact H-CL1 benefit endpoint and statistical success rule",
   "exact oracle-ceiling go/no-go criterion",
   "exact CL-DEV-R final-configuration selection rule",
   "the qualification requirements and interpretation rules those imply"],
 "added_paths": added, "removed_paths": removed, "changed_paths": changed,
 "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
 "out_of_scope_changes": off,
 "all_unrelated_v2_decisions_preserved": not off,
 "v2_safety_contract_unchanged": SAFETY_UNCHANGED,
}
diff = attach_canonical_hash(diff, "clean_room_contract_v2_to_v3_diff_root")
(R / "rvt_swarm_clean_room_contract_v2_to_v3_diff.json").write_text(
    json.dumps(diff, indent=1, sort_keys=True) + "\n", encoding="ascii")
print("V3_ROOT", sealed["rvt_swarm_clean_room_global_contract_root"])
print("V3_file_sha256", hashlib.sha256(out.read_bytes()).hexdigest())
print("DIFF_ROOT", diff["clean_room_contract_v2_to_v3_diff_root"])
print(f"added={len(added)} removed={len(removed)} changed={len(changed)}")
print("OUT_OF_SCOPE:", off if off else "NONE")
print("V2 SAFETY CONTRACT UNCHANGED:", SAFETY_UNCHANGED)
