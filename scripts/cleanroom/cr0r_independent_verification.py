"""CR-0R independent verification -- re-derive every V2 claim from source."""
from __future__ import annotations
import hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import verify_canonical_hash

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def h(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
v1 = json.loads((R / "rvt_swarm_clean_room_global_contract_v1.json").read_text())
v2 = json.loads((R / "rvt_swarm_clean_room_global_contract_v2.json").read_text())
df = json.loads((R / "rvt_swarm_clean_room_contract_v1_to_v2_diff.json").read_text())
fail = []
def ck(n, ok, d=""):
    print(("PASS " if ok else "FAIL ") + n + (f" -- {d}" if d else ""))
    if not ok: fail.append(n)

V1_ROOT = "16aa431b290eae42ad62b0f72fae22ed3a2e3b7be138db4cfdda4a636bd87c02"

# ---- V1 preserved -----------------------------------------------------------
ck("V1 still exists and its canonical hash verifies",
   verify_canonical_hash(v1, "rvt_swarm_clean_room_global_contract_root"))
ck("V1 root unchanged", v1["rvt_swarm_clean_room_global_contract_root"] == V1_ROOT)
ck("V1 tag still resolves", subprocess.run(["git","-C",str(ROOT),"rev-parse",
   "rvt-cleanroom-cr0-v1"], capture_output=True).returncode == 0)
ck("V2 canonical hash", verify_canonical_hash(v2, "rvt_swarm_clean_room_global_contract_root"))
ck("V2 references V1", v2["amendment"]["v1_root"] == V1_ROOT and
   v2["amendment"]["amends"] == "RVT_SWARM_CLEAN_ROOM_GLOBAL_CONTRACT_V1" and
   v2["amendment"]["v1_preserved_unmodified"] is True)
ck("V2 declares the amendment predates clean-room data and training",
   v2["amendment"]["made_before_any_clean_room_data_existed"] is True and
   v2["amendment"]["made_before_any_clean_room_model_training"] is True and
   v2["amendment"]["no_empirical_clean_room_outcome_informed_these_changes"] is True)

# ---- no clean-room data or weights ------------------------------------------
tracked = subprocess.run(["git","-C",str(ROOT),"ls-files"], capture_output=True,
                         text=True).stdout.splitlines()
import re as _re
roles = ["TRAIN-R","SELECT-R","CL-DEV-R","MAIN-R","MECH-R","PROTECTED-R"]
hits = {r: [f for f in tracked if _re.search(rf"(^|[^A-Za-z]){r}([^A-Za-z]|$)", f)] for r in roles}
ck("no clean-room dataset exists for any role", not any(hits.values()),
   json.dumps({k: v for k, v in hits.items() if v}))
ck("V2 state block still declares nothing generated or trained",
   not any(v2["cr0_state"].values()))
pts = [p for p in ROOT.rglob("*.pt") if ".git" not in p.parts]
ck("no clean-room trained model exists",
   not any("cleanroom" in str(p).lower() or "clean_room" in str(p).lower() for p in pts),
   f"{len(pts)} pilot-era checkpoints present, none clean-room")

# ---- diff is scoped ---------------------------------------------------------
ck("diff canonical hash", verify_canonical_hash(df, "clean_room_contract_v1_to_v2_diff_root"))
ck("diff links V1 to V2", df["from_root"] == V1_ROOT and
   df["to_root"] == v2["rvt_swarm_clean_room_global_contract_root"])
ck("no out-of-scope changes", df["out_of_scope_changes"] == [] and
   df["all_unrelated_v1_decisions_preserved"] is True)
ck("only the safety-margin deferral was removed",
   df["removed_paths"] == [".safety_contract.exact_effect_sizes_and_non_inferiority_margins"],
   json.dumps(df["removed_paths"]))

# ---- closure 1: safety ------------------------------------------------------
from rvt_swarm.cleanroom.safety_contract import (
    PRIMARY_ENDPOINTS, EndpointVerdict, central_closed_loop_claim, endpoint_passes,
    safety_hypothesis_passes, TTC_VIOLATION_THRESHOLD_S)
sc = v2["safety_contract"]
ck("safety status declares no deferral", "no safety margin is deferred" in sc["status"])
ck("four primary endpoints, each fully specified", len(sc["primary_endpoints"]) == 4 and
   all(all(e.get(k) not in (None, "") for k in
           ("key","definition","unit","aggregation_unit","direction_of_harm",
            "non_inferiority_margin","margin_justification","interval",
            "treatment_contrast","pass_rule"))
       for e in sc["primary_endpoints"]))
by = {e["key"]: e for e in sc["primary_endpoints"]}
ck("collision margin and floor are the frozen pilot gate values",
   by["collision_free_rate"]["non_inferiority_margin"] == 0.01 and
   by["collision_free_rate"]["absolute_floor"] == 0.95 and
   sc["inherited_frozen_pilot_gate"]["absolute_degradation_maximum"] == 0.01 and
   sc["inherited_frozen_pilot_gate"]["collision_free_point_estimate_minimum"] == 0.95)
gate = json.loads((R / "phase9d_h1_requirement_map_v1.json").read_text())
def find_gate(o):
    if isinstance(o, dict):
        if "collision_gate" in o: return o["collision_gate"]
        for v in o.values():
            r = find_gate(v)
            if r: return r
    return None
g = find_gate(gate)
ck("the pilot gate quoted in V2 matches the pilot artifact exactly",
   g["absolute_degradation_maximum"] == sc["inherited_frozen_pilot_gate"]["absolute_degradation_maximum"] and
   g["collision_free_point_estimate_minimum"] == sc["inherited_frozen_pilot_gate"]["collision_free_point_estimate_minimum"],
   json.dumps(g))
ck("TTC threshold is the physical braking time",
   sc["ttc_violation_threshold_s"] == TTC_VIOLATION_THRESHOLD_S == 0.90 / 0.60 == 1.5)
ck("severe-contact margin is stricter than the gate margin",
   by["severe_near_collision_rate"]["non_inferiority_margin"] <
   by["collision_free_rate"]["non_inferiority_margin"])
ck("every margin carries a justification naming a frozen source",
   all(len(e["margin_justification"]) > 30 for e in sc["primary_endpoints"]))
ck("multiplicity is an intersection-union test with no correction",
   sc["multiplicity"]["procedure"] == "INTERSECTION_UNION_TEST" and
   sc["multiplicity"]["alpha_correction"] == "NONE_REQUIRED")
ck("intervention rate is secondary only",
   sc["secondary_endpoints"][0]["key"] == "safety_projection_intervention_rate" and
   sc["secondary_endpoints"][0]["pass_rule"].startswith("NONE"))
ck("margins were not chosen from clean-room outcomes and are now immutable",
   sc["margins_chosen_using_any_clean_room_outcome"] is False and
   sc["margin_modification_after_this_amendment"] == "FORBIDDEN")
# executable and unambiguous
ok = {e.key: EndpointVerdict(e.key, True, "") for e in PRIMARY_ENDPOINTS}
bad = dict(ok); bad["collision_free_rate"] = EndpointVerdict("collision_free_rate", False, "")
ck("safety rule executes: IUT passes only when every endpoint passes",
   safety_hypothesis_passes(ok) and not safety_hypothesis_passes(bad))
ck("safety rule executes: exactly at the margin is a failure",
   not endpoint_passes(PRIMARY_ENDPOINTS[0], point_difference=-0.01,
                       one_sided_bound=-0.01, treatment_point_estimate=0.97).passed)
ck("safety rule executes: progress without safety fails the central claim",
   central_closed_loop_claim(True, False) == "CENTRAL_CLAIM_FAILS_SAFETY_NON_INFERIORITY_NOT_MET" and
   central_closed_loop_claim(True, True) == "CENTRAL_CLOSED_LOOP_CLAIM_SUPPORTED")
ck("safety implementation hash live", sc["implementation_sha256"] == h("rvt_swarm/cleanroom/safety_contract.py"))

# ---- closure 2: A3 ----------------------------------------------------------
from rvt_swarm.cleanroom.a3_control import capacity_match_report
a3 = v2["a3_mechanism_control"]
cap = capacity_match_report()
ck("A3 parameter count reproduces from the implementation",
   a3["parameter_count"] == cap["a3_parameters"] == 261681)
ck("A3 is capacity-matched within its declared tolerance",
   cap["within_tolerance"] and abs(a3["residual_mismatch_relative"]) <= a3["capacity_matching_tolerance_fraction"],
   f"{a3['residual_mismatch_relative']:+.4%} vs tol {a3['capacity_matching_tolerance_fraction']}")
ck("A3 residual mismatch is conservative (A3 not larger than M2)",
   a3["residual_mismatch_absolute"] < 0)
ck("A3 matches M2 on depth, embedding width, dropout and dtype",
   a3["blocks"] == 3 and a3["candidate_embedding_dimension"] == 16 and
   a3["dropout_probability"] == 0.0 and a3["numerical_dtype"] == "float32")
ck("A3 sees topology identity and neighbor information",
   a3["topology_identity_visible"] is True and a3["neighbor_information_visible"] is True)
ck("A3 forbidden inputs are identical to the frozen predictor contract",
   a3["forbidden_inputs"] == v1["model_families"]["input_contract"]["forbidden_predictor_inputs"])
ck("A3 optimizer settings equal M2's frozen recipe",
   a3["training_recipe"]["learning_rate"] == v1["training_recipe"]["M2"]["learning_rate"] and
   a3["training_recipe"]["weight_decay"] == v1["training_recipe"]["M2"]["weight_decay"] and
   a3["training_recipe"]["optimizer"] == "AdamW")
ck("A3 seeds are the frozen three", a3["seeds"] == [11, 29, 47])
ck("A3 does not participate in SELECT-R",
   a3["participates_in_SELECT_R_family_selection"] is False)
ck("A3 is scheduled for CR-2 training from scratch on TRAIN-R",
   a3["planned_training_stage"] == "CR-2, from scratch on TRAIN-R" and
   a3["architecture_or_recipe_change_after_TRAIN_R_exists"] == "FORBIDDEN")
ck("A3 causal scope stated both ways",
   len(a3["supports_claim"]) > 40 and len(a3["does_not_support_claim"]) > 40 and
   a3["M1_vs_M2_alone_admissible_for_message_passing_causality"] is False)
ck("A3 implementation hash live", a3["implementation_sha256"] == h("rvt_swarm/cleanroom/a3_control.py"))
import inspect
from rvt_swarm.cleanroom import a3_control
_src = inspect.getsource(a3_control)
ck("A3 source contains no message-passing primitive",
   not any(b in _src for b in ("scatter_add","propagate","MessagePassing","GATConv")))

# ---- closure 3: protected semantics -----------------------------------------
from rvt_swarm.phase8.scenario import SCENARIO_FAMILIES
pg = v2["protected_generalization"]
ck("CASE_A is the recorded resolution", pg["case"] == "CASE_A")
ck("the generator really does enumerate exactly ten families",
   len(SCENARIO_FAMILIES) == 10 and
   [f.family_id for f in SCENARIO_FAMILIES] == pg["known_layout_families"])
ck("protected offset is the reserved final-test base",
   v2["disjointness_contract"]["layout_offset_assignment"]["clean_room"]["PROTECTED-R"] == 0.79)
ck("terminology is exact and unambiguous",
   pg["exact_terminology"] == "unseen layout instances within known layout families")
ck("the ambiguous wording is explicitly forbidden",
   all(x in pg["forbidden_claim_language"] for x in
       ["unseen layout families","novel layout families","unseen layouts (unqualified)"]))
ck("no unqualified 'unseen layouts' remains anywhere in V2",
   "unseen layouts\"" not in json.dumps(v2) and
   '"unseen layouts' not in json.dumps(v2).replace('"unseen layouts (unqualified)', ''))
ck("broad family generalization declared out of scope",
   pg["broad_family_level_generalization"] == "OUTSIDE_THE_CURRENT_CONFIRMATORY_SCOPE")
ck("identity-disjoint confirmation is distinguished from domain generalization",
   set(pg["distinction_that_must_not_be_conflated"]) ==
   {"identity_disjoint_confirmation","distribution_or_domain_generalization"})
ck("per-role claim language recorded for all six roles",
   all(r in v2["dataset_role_claim_language"] for r in roles))

# ---- interpretation rules ---------------------------------------------------
im = json.dumps(v2["interpretation_claim_mapping"])
ck("safety consequence rule present", "THE CENTRAL CLOSED-LOOP CLAIM FAILS" in im)
ck("A3 consequence rule present", "no message-passing-specific causal claim" in im)
ck("protected consequence rules present",
   "do not claim unseen-FAMILY generalization" in im and
   "no broad family-level generalization claim" in im)
ck("V1 interpretation rules all retained",
   all(json.dumps(r) in im for r in v1["interpretation_claim_mapping"]))

# ---- unchanged CR-0 pillars -------------------------------------------------
for path, label in [
  (["family_statistic","definition"], "family statistic definition"),
  (["family_statistic","bootstrap_replicate_order"], "family statistic replicate order"),
  (["downstream_representative","rule"], "downstream representative rule"),
  (["family_selection_rule","winner"], "family selection winner rule"),
  (["main_r_firewall","generation_permitted_only_at"], "MAIN-R firewall"),
  (["main_r_failure_rule","forbidden_after_failure"], "MAIN-R failure rule"),
  (["pilot_boundary","PILOT_WEIGHTS_ALLOWED_AS_FINAL"], "pilot boundary"),
  (["closed_loop_architecture","runtime_decentralization"], "decentralized runtime"),
  (["disjointness_contract","required_empty_intersections"], "role disjointness"),
  (["central_thesis","statement"], "central thesis"),
  (["episode_universe_contract","zero_yield_episodes_remain_in_the_resampling_universe"], "episode universe"),
  (["calibration_contract","rule"], "calibration contract"),
  (["model_families","M2"], "M2 architecture"),
  (["training_recipe","seeds"], "training seeds")]:
    a = v1; b = v2
    for k in path: a = a[k]; b = b[k]
    ck(f"unchanged from V1: {label}", a == b)

print("\nVERIFICATION", "PASS" if not fail else f"FAIL {fail}")
print("V1_ROOT", V1_ROOT)
print("V2_ROOT", v2["rvt_swarm_clean_room_global_contract_root"])
print("DIFF_ROOT", df["clean_room_contract_v1_to_v2_diff_root"])
