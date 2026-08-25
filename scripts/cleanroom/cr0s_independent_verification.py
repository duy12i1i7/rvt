"""CR-0S independent verification -- re-derive every V3 claim from source."""
from __future__ import annotations
import hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import verify_canonical_hash

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def h(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
v1 = json.loads((R / "rvt_swarm_clean_room_global_contract_v1.json").read_text())
v2 = json.loads((R / "rvt_swarm_clean_room_global_contract_v2.json").read_text())
v3 = json.loads((R / "rvt_swarm_clean_room_global_contract_v3.json").read_text())
df = json.loads((R / "rvt_swarm_clean_room_contract_v2_to_v3_diff.json").read_text())
fail = []
def ck(n, ok, d=""):
    print(("PASS " if ok else "FAIL ") + n + (f" -- {d}" if d else ""))
    if not ok: fail.append(n)

V1_ROOT = "16aa431b290eae42ad62b0f72fae22ed3a2e3b7be138db4cfdda4a636bd87c02"
V2_ROOT = "90e5d4d9ee6b4388596f3a48ce5e62e0a8f446f08c7f7020d6ceda800a082740"

# ---- lineage ----------------------------------------------------------------
ck("V1 unchanged", verify_canonical_hash(v1, "rvt_swarm_clean_room_global_contract_root")
   and v1["rvt_swarm_clean_room_global_contract_root"] == V1_ROOT)
ck("V2 unchanged", verify_canonical_hash(v2, "rvt_swarm_clean_room_global_contract_root")
   and v2["rvt_swarm_clean_room_global_contract_root"] == V2_ROOT)
ck("V3 canonical hash", verify_canonical_hash(v3, "rvt_swarm_clean_room_global_contract_root"))
ck("V3 references both V1 and V2",
   v3["amendment"]["v1_root"] == V1_ROOT and v3["amendment"]["v2_root"] == V2_ROOT and
   v3["amendment"]["lineage"] == ["RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V1",
                                  "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V2"])
ck("V3 predates all clean-room data and training",
   v3["amendment"]["made_before_any_clean_room_data_existed"] is True and
   v3["amendment"]["made_before_any_clean_room_model_training"] is True and
   v3["amendment"]["no_empirical_clean_room_outcome_informed_these_changes"] is True)
for tag in ("rvt-cleanroom-cr0-v1", "rvt-cleanroom-cr0r-v2"):
    ck(f"prior tag {tag} still resolves", subprocess.run(
       ["git","-C",str(ROOT),"rev-parse",tag], capture_output=True).returncode == 0)

# ---- no clean-room data or models -------------------------------------------
import re as _re
roles = ["TRAIN-R","SELECT-R","CL-DEV-R","MAIN-R","MECH-R","PROTECTED-R"]
files = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
hits = {r: [f for f in files if _re.search(rf"(^|[^A-Za-z]){r}([^A-Za-z]|$)", f)] for r in roles}
ck("zero clean-room data for every role", not any(hits.values()),
   json.dumps({k: v for k, v in hits.items() if v}))
ck("zero clean-room trained models",
   not any("clean" in str(p).lower() for p in ROOT.rglob("*.pt") if ".git" not in p.parts))
ck("V3 state block still declares nothing generated or trained", not any(v3["cr0_state"].values()))

# ---- scoped diff ------------------------------------------------------------
ck("diff canonical hash", verify_canonical_hash(df, "clean_room_contract_v2_to_v3_diff_root"))
ck("diff links V2 to V3", df["from_root"] == V2_ROOT and
   df["to_root"] == v3["rvt_swarm_clean_room_global_contract_root"])
ck("no out-of-scope scientific change", df["out_of_scope_changes"] == [] and
   df["all_unrelated_v2_decisions_preserved"] is True)
ck("V2 safety contract byte-unchanged in V3",
   df["v2_safety_contract_unchanged"] is True and v3["safety_contract"] == v2["safety_contract"])

# ---- closure 1: H-CL1 -------------------------------------------------------
from rvt_swarm.cleanroom.benefit_contract import (
    COMPARATOR_ARM, PRACTICAL_BENEFIT_THRESHOLD, PRIMARY, SEQUENCE, TREATMENT_ARM,
    EndpointResult, fixed_sequence_verdicts, impute_invalid, permitted_benefit_language,
    primary_passes)
b = v3["h_cl1_benefit_contract"]
ck("H-CL1 declares no remaining metric choice", "no future benefit-metric choice" in b["status"])
ck("primary endpoint is the pilot H1 endpoint",
   b["primary_endpoint"]["key"] == PRIMARY.key == "episode_task_success_rate" and
   b["primary_endpoint"]["metric_key"] == "success")
gate = json.loads((R / "phase9d_h1_requirement_map_v1.json").read_text())
ck("the 0.08 threshold really is the pilot's frozen H1 margin",
   "0.08 absolute" in json.dumps(gate) and
   b["primary_endpoint"]["practical_benefit_threshold"] == PRACTICAL_BENEFIT_THRESHOLD == 0.08)
ck("primary endpoint fully specified",
   all(b["primary_endpoint"].get(k) not in (None, "") for k in
       ("key","definition","unit","aggregation_unit","direction_of_benefit","estimator",
        "interval","practical_benefit_threshold","pass_rule")))
ck("treatment contrast frozen and substitution forbidden",
   b["treatment_arm"] == TREATMENT_ARM and b["comparator_arm"] == COMPARATOR_ARM and
   b["comparator_substitution_after_MAIN_R"].startswith("FORBIDDEN"))
ck("recovery, progress and liveness are each covered by a named endpoint",
   set(b["scientific_concepts_covered"]) == {"task progress","recovery","liveness / deadlock"})
ck("multiplicity is fixed-sequence gatekeeping with no correction",
   b["multiplicity"]["procedure"] == "FIXED_SEQUENCE_GATEKEEPING" and
   b["multiplicity"]["alpha_correction"] == "NONE_REQUIRED")
ck("H-CL1 rests on the primary endpoint alone",
   b["h_cl1_pass_rule"].startswith("H-CL1 passes if and only if the PRIMARY"))
# executable
ck("primary rule executes and is strict at the threshold",
   primary_passes(EndpointResult(PRIMARY.key, 0.12, 0.0801, 0.2)) and
   not primary_passes(EndpointResult(PRIMARY.key, 0.12, 0.08, 0.2)))
res = {"episode_task_success_rate": EndpointResult("episode_task_success_rate", .12, .09, .15),
       "deadlock_rate": EndpointResult("deadlock_rate", -.05, -.08, -.02),
       "irreversible_collapse_rate": EndpointResult("irreversible_collapse_rate", -.04, -.07, -.01),
       "goal_reached_rate": EndpointResult("goal_reached_rate", .10, .06, .14)}
vd, h1 = fixed_sequence_verdicts(res)
ck("fixed sequence executes and passes when all endpoints hold", h1 and all(x.passed for x in vd.values()))
res2 = dict(res); res2["deadlock_rate"] = EndpointResult("deadlock_rate", .05, .02, .08)
vd2, _ = fixed_sequence_verdicts(res2)
ck("fixed sequence stops testing at the first failure",
   vd2["deadlock_rate"].tested and not vd2["goal_reached_rate"].tested)
ck("worst-case imputation executes",
   impute_invalid(PRIMARY, [1.0, None]) == [1.0, 0.0] and
   impute_invalid(SEQUENCE[1], [0.0, None]) == [0.0, 1.0])
ck("claim language is gated by the primary rule",
   permitted_benefit_language(EndpointResult(PRIMARY.key, .12, .09, .15)) ==
   ("improves", "substantially improves") and
   permitted_benefit_language(EndpointResult(PRIMARY.key, .05, .02, .09)) == ())
ck("H-CL1 implementation hash live",
   b["implementation_sha256"] == h("rvt_swarm/cleanroom/benefit_contract.py"))

# ---- closure 2: oracle ------------------------------------------------------
from rvt_swarm.cleanroom.oracle_contract import (
    ORACLE_HEADROOM_FAIL, ORACLE_HEADROOM_PASS, ORACLE_PRACTICAL_THRESHOLD,
    PREMISE_AT_RISK, oracle_headroom)
o = v3["oracle_ceiling"]["decision_rule"]
ck("the word 'materially' is retired", "retired" in o["status"])
ck("oracle rule fully specified",
   o["comparator"] == COMPARATOR_ARM and o["endpoint"] == PRIMARY.key and
   o["practical_threshold"] == ORACLE_PRACTICAL_THRESHOLD == 0.08 and
   o["uses_statistical_uncertainty"] is True and o["required_effect_direction"] == "increase")
ck("oracle conjunction executes: all three conditions required",
   oracle_headroom(EndpointResult(PRIMARY.key, .12, .05, .19), oracle_safety_passes=True).outcome == ORACLE_HEADROOM_PASS and
   oracle_headroom(EndpointResult(PRIMARY.key, .12, .05, .19), oracle_safety_passes=False).outcome == ORACLE_HEADROOM_FAIL and
   oracle_headroom(EndpointResult(PRIMARY.key, .03, .01, .05), oracle_safety_passes=True).outcome == ORACLE_HEADROOM_FAIL and
   oracle_headroom(EndpointResult(PRIMARY.key, .12, -.01, .25), oracle_safety_passes=True).outcome == ORACLE_HEADROOM_FAIL)
ck("oracle failure blocks automatic progression to MAIN-R",
   v3["oracle_ceiling"]["on_fail"]["may_proceed_automatically_to_main_r"] is False and
   v3["oracle_ceiling"]["on_fail"]["premise_status"] == PREMISE_AT_RISK)
ck("oracle stays development-only and cannot be reinterpreted later",
   v3["oracle_ceiling"]["development_only"] is True and
   v3["oracle_ceiling"]["post_cl_dev_reinterpretation_of_oracle_success"] == "FORBIDDEN")
ck("oracle implementation hash live",
   v3["oracle_ceiling"]["implementation_sha256"] == h("rvt_swarm/cleanroom/oracle_contract.py"))

# ---- closure 3: CL-DEV ------------------------------------------------------
from rvt_swarm.cleanroom.development_selection import (
    MAXIMUM_EVALUATED_CONFIGURATIONS, NO_ADMISSIBLE_CONFIGURATION, ConfigurationRecord,
    DevelopmentSelectionError, select_final_configuration)
s = v3["closed_loop_development_space"]["final_configuration_selection"]
ck("selection rule declares no subjective choice remains", "EXACT" in s["status"])
ck("selection rule fully specified",
   all(s.get(k) for k in ("eligibility","safety_feasibility_gate","primary_objective",
                          "tie_breakers_in_strict_order","tie_strictness","stopping_rule",
                          "failed_simulations","invalid_episodes",
                          "no_admissible_configuration_outcome")))
ck("progress-with-failed-safety is inadmissible, not a trade",
   "INADMISSIBLE" in s["safety_feasibility_gate"])
ck("six ordered tie-breakers ending in a total criterion",
   len(s["tie_breakers_in_strict_order"]) == 6 and
   "lowest ledger index" in s["tie_breakers_in_strict_order"][5])
ck("40-configuration budget and append-only ledger preserved from V1",
   v3["closed_loop_development_space"]["development_budget"]["maximum_evaluated_configurations"]
   == v1["closed_loop_development_space"]["development_budget"]["maximum_evaluated_configurations"]
   == MAXIMUM_EVALUATED_CONFIGURATIONS == 40 and
   "append-only" in v3["closed_loop_development_space"]["development_budget"]["ledger"])
def cfg(i, d, **o):
    base = dict(ledger_index=i, registered_before_execution=True, run_completed=True,
                invalid_episode_fraction_acceptable=True, safety_gate_passes=True,
                delta_success_point=d, delta_success_ci_lower=d-0.03, deadlock_rate=0.1,
                irreversible_collapse_rate=0.1, minimum_clearance_m=0.5,
                topology_switches_per_episode=1.0); base.update(o)
    return ConfigurationRecord(**base)
ck("selection executes: safety gate excludes a higher-scoring configuration",
   select_final_configuration([cfg(0,0.05), cfg(1,0.30,safety_gate_passes=False),
                               cfg(2,0.09)]).ledger_index == 2)
ck("selection executes: no admissible configuration is reported, not worked around",
   select_final_configuration([cfg(0,0.5,safety_gate_passes=False)]) == NO_ADMISSIBLE_CONFIGURATION
   == s["no_admissible_configuration_outcome"])
try:
    select_final_configuration([cfg(i,0.1) for i in range(41)]); over = False
except DevelopmentSelectionError: over = True
ck("selection executes: exceeding the budget fails closed", over)
try:
    select_final_configuration([cfg(0,0.1), cfg(1,0.2,registered_before_execution=False)]); unl = False
except DevelopmentSelectionError: unl = True
ck("selection executes: an unlogged configuration fails closed", unl)
ck("adaptivity boundary recorded",
   v3["closed_loop_development_space"]["adaptivity_boundary"]["the_method_may_be_developed_adaptively"] is True and
   v3["closed_loop_development_space"]["adaptivity_boundary"]["the_final_selection_criterion_may_not_be_adaptive"] is True)
ck("selection implementation hash live",
   s["implementation_sha256"] == h("rvt_swarm/cleanroom/development_selection.py"))

# ---- conjunction + engine ---------------------------------------------------
from rvt_swarm.cleanroom.closed_loop_engine import CLAIM_NOT_SUPPORTED, CLAIM_SUPPORTED, evaluate_closed_loop
from rvt_swarm.cleanroom.safety_contract import PRIMARY_ENDPOINTS as SEPS, EndpointVerdict as SV
cc = v3["central_claim_conjunction"]
ck("conjunction is exact and safety-preserving",
   "H-CL1 BENEFIT PASS" in cc["rule"] and "H-CL2 SAFETY PASS" in cc["rule"] and
   cc["benefit_pass_safety_fail"] == "CENTRAL_CLAIM_FAILS_SAFETY_NON_INFERIORITY_NOT_MET" and
   cc["safety_contract_unchanged_from_v2"] is True)
ids = [f"e{i}" for i in range(10)]; lay = {e: "L0" for e in ids}; ev = [e for e in ids for _ in range(2)]
kw = dict(manifest_episode_ids=ids, manifest_episode_layout=lay, observed_event_episode_ids=ev,
          expected_episode_count=10, treatment_arm=TREATMENT_ARM, comparator_arm=COMPARATOR_ARM,
          invalid_episode_count=0, bootstrap_replicates=10000, bootstrap_seed=20260901,
          confidence_level=0.95)
sok = {e.key: SV(e.key, True, "") for e in SEPS}
sbad = dict(sok); sbad["collision_free_rate"] = SV("collision_free_rate", False, "")
ck("engine executes: benefit and safety both pass is the only supported outcome",
   evaluate_closed_loop(benefit_results=res, safety_verdicts=sok, **kw).central_claim == CLAIM_SUPPORTED and
   evaluate_closed_loop(benefit_results=res, safety_verdicts=sbad, **kw).central_claim == CLAIM_NOT_SUPPORTED)
e = v3["closed_loop_analysis_engine"]
ck("engine contract forbids orchestration reinterpretation",
   e["orchestration_may_reinterpret_these_values"] is False and
   e["mathematical_contract_immutable_from"] == "CR-0S")
ck("engine implementation hash live",
   e["implementation_sha256"] == h("rvt_swarm/cleanroom/closed_loop_engine.py"))

# ---- qualification + preserved pillars --------------------------------------
q = v3["adversarial_qualification"]
ck("all fifteen closed-loop negative fixtures are covered",
   len(q["closed_loop_negative_fixtures"]) == 15 and
   all(v == "COVERED" for v in q["closed_loop_negative_fixtures"].values()))
ck("cr0s suite hash live", q["cr0s_suite"]["sha256"] == h("tests/test_cleanroom_cr0s.py"))
for name, want in q["clean_room_engine"].items() if False else v3["orchestration_authority"]["clean_room_engine"].items():
    ck(f"engine hash live: {name}", h(f"rvt_swarm/cleanroom/{name}") == want)
for path, label, src in [
  (["family_statistic","definition"], "family statistic", v1),
  (["downstream_representative","rule"], "downstream seed rule", v1),
  (["family_selection_rule","winner"], "SELECT-R winner rule", v1),
  (["main_r_firewall","generation_permitted_only_at"], "MAIN-R firewall", v1),
  (["main_r_failure_rule","forbidden_after_failure"], "MAIN-R failure rule", v1),
  (["pilot_boundary","PILOT_WEIGHTS_ALLOWED_AS_FINAL"], "pilot boundary", v1),
  (["closed_loop_architecture","runtime_decentralization"], "decentralization", v1),
  (["disjointness_contract","required_empty_intersections"], "role disjointness", v1),
  (["central_thesis","statement"], "central thesis", v1),
  (["calibration_contract","rule"], "calibration contract", v1),
  (["model_families","M2"], "M2 definition", v1),
  (["training_recipe","seeds"], "seeds", v1),
  (["safety_contract"], "V2 safety contract", v2),
  (["a3_mechanism_control"], "A3 definition", v2),
  (["protected_generalization"], "protected-layout semantics", v2)]:
    a = src; c = v3
    for k in path: a = a[k]; c = c[k]
    ck(f"preserved: {label}", a == c)

print("\nVERIFICATION", "PASS" if not fail else f"FAIL {fail}")
print("V1_ROOT", V1_ROOT); print("V2_ROOT", V2_ROOT)
print("V3_ROOT", v3["rvt_swarm_clean_room_global_contract_root"])
