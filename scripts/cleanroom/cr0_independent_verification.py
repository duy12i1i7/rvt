"""CR-0 independent verification -- re-derive every bound claim from source."""
from __future__ import annotations
import hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/Users/udy/rvt")
import numpy as np, torch
from rvt_swarm.phase8.common import verify_canonical_hash

ROOT = pathlib.Path("/Users/udy/rvt"); R = ROOT / "results/rvt_fd24"
def h(rel): return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
c = json.loads((R / "rvt_swarm_clean_room_global_contract_v1.json").read_text())
pre = json.loads((R / "open_loop_v3_recoverability_predictor_preregistration_v1.json").read_text())
reg = json.loads((R / "phase9d_v3f_l_layout_split_registry_v2.json").read_text())
fail = []
def ck(n, ok, d=""):
    print(("PASS " if ok else "FAIL ") + n + (f" -- {d}" if d else ""))
    if not ok: fail.append(n)

ck("contract canonical hash", verify_canonical_hash(c, "rvt_swarm_clean_room_global_contract_root"))
ck("contract root as reported",
   c["rvt_swarm_clean_room_global_contract_root"] == "16aa431b290eae42ad62b0f72fae22ed3a2e3b7be138db4cfdda4a636bd87c02")
ck("status is prospectively frozen",
   c["status"] == "PROSPECTIVELY_FROZEN_BEFORE_ANY_CLEAN_ROOM_DATA_EXISTS")
ck("CR-0 source commit matches the repository",
   c["cr0_source_commit"] == subprocess.run(["git","-C",str(ROOT),"rev-parse","HEAD"],
       capture_output=True, text=True).stdout.strip())

# --- pilot boundary ---
pb = c["pilot_boundary"]
ck("pilot boundary forbids final use of pilot objects",
   pb["PILOT_WEIGHTS_ALLOWED_AS_FINAL"] == "NO" and
   pb["PILOT_VALIDATION_USED_FOR_FINAL_INFERENCE"] == "NO" and
   pb["PILOT_CONFIDENCE_INTERVALS_USED_FOR_FINAL_CLAIMS"] == "NO" and
   pb["history_rewritten_or_repaired"] is False)
ck("pilot roots still resolve to the committed artifacts",
   json.loads((R/"open_loop_v3_novelty_checkpoint_1_v1.json").read_text())
     ["open_loop_v3_novelty_checkpoint_1_root"] == pb["pilot_artifacts_retained_for_provenance"]["novelty_checkpoint_1_root"])

# --- roles + disjointness ---
roles = c["dataset_roles"]
ck("exactly six roles", sorted(roles) == sorted(
   ["TRAIN-R","SELECT-R","CL-DEV-R","MAIN-R","MECH-R","PROTECTED-R"]))
d = c["disjointness_contract"]
off = d["layout_offset_assignment"]["clean_room"]
ck("offset formula quoted from the frozen registry",
   d["layout_offset_assignment"]["formula"] == reg["offset_formula"])
ck("clean-room offsets cover all six roles", sorted(off) == sorted(roles))
vals = sorted(off.values())
ck("clean-room offsets are pairwise distinct", len(set(vals)) == 6)
ck("minimum pairwise separation >= 0.11",
   min(round(b-a, 10) for a, b in zip(vals, vals[1:])) >= 0.11,
   f"offsets {vals}")
consumed = set(d["layout_offset_assignment"]["consumed_by_pilot"]["TRAIN"]) | \
           set(d["layout_offset_assignment"]["consumed_by_pilot"]["VALIDATION"]) | \
           set(d["layout_offset_assignment"]["pilot_reserve_left_untouched"])
ck("no clean-room offset collides with a pilot or reserve offset",
   not (set(off.values()) & consumed), f"pilot+reserve {sorted(consumed)}")
ck("no clean-room offset is forbidden",
   not (set(off.values()) & set(d["layout_offset_assignment"]["forbidden"])))
ck("pilot offsets match the frozen registry assignment",
   sorted(d["layout_offset_assignment"]["consumed_by_pilot"]["TRAIN"]) == sorted(reg["assignment"]["TRAIN"]["offsets"]) and
   sorted(d["layout_offset_assignment"]["consumed_by_pilot"]["VALIDATION"]) == sorted(reg["assignment"]["VALIDATION"]["offsets"]))
ck("PROTECTED-R sits on the reserved final-test base",
   off["PROTECTED-R"] == reg["generator_split_offsets"]["final_test"])
ck("the layout-family correlation limitation is declared",
   "not independent worlds" in d["layout_offset_assignment"]["declared_limitation"])

# --- generator authority ---
g = c["generation_authority"]
ck("no scientific generator change required", g["scientific_generator_change_required"] is False)
ck("generator hashes quoted from the frozen registry",
   g["generator_sha256"] == reg["generator_sha256"] and
   g["generator_authority"] == reg["generator_authority"] and
   g["generator_unchanged"] is True and g["frozen_v2_scenario_code_modified"] is False)
sda = pre["sealed_data_authority"]
for key, src in [("executable_source_commit","executable_source_commit"),
                 ("production_image_digest","production_image_digest"),
                 ("target_semantics_sha256","target_v4_contract_sha256"),
                 ("replica_law_sha256","recoverability_replica_protocol_v3_sha256"),
                 ("row_event_binding_sha256","recoverability_row_binding_v3_spec_sha256")]:
    ck(f"generation authority {key} matches the sealed authority", g[key] == sda[src])

# --- families + recipe ---
ck("M0/M1/M2 architectures quoted verbatim from the preregistration",
   c["model_families"]["M0"] == pre["R8_model_ladder"]["M0"] and
   c["model_families"]["M1"] == pre["R8_model_ladder"]["M1"] and
   c["model_families"]["M2"] == pre["R8_model_ladder"]["M2"])
ck("input contract quoted verbatim", c["model_families"]["input_contract"] == pre["R9_model_input_contract"])
ck("clean-room models trained from scratch, pilot checkpoints excluded",
   c["model_families"]["clean_room_models_trained_from_scratch"] is True and
   c["model_families"]["pilot_stage5c_checkpoints_are_clean_room_checkpoints"] is False)
tr = c["training_recipe"]
ck("no HP search on TRAIN-R", tr["hyperparameter_search_on_TRAIN_R"].startswith("NONE"))
ck("seeds are exactly 11,29,47", tr["seeds"] == [11,29,47])
ck("architecture search off", c["model_families"]["architecture_searched"] is False)
ck("post-SELECT-R retraining forbidden", tr["post_SELECT_R_retraining"] == "FORBIDDEN")
ck("refit step rule quoted from the preregistration",
   tr["refit_step_rule"] == pre["R13_train_only_hp_selection"]["refit_step_rule"])

# --- engine hashes are live ---
for name, want in c["orchestration_authority"]["clean_room_engine"].items():
    ck(f"engine hash live: {name}", h(f"rvt_swarm/cleanroom/{name}") == want)
for name, want in c["orchestration_authority"]["inherited_qualified_libraries"].items():
    ck(f"inherited hash live: {name}", h(f"rvt_swarm/{name}") == want)
ck("orchestration may not reimplement scientific rules",
   c["orchestration_authority"]["orchestration_may_reimplement_scientific_rules"] is False and
   c["orchestration_authority"]["on_any_mismatch"] == "FAIL_CLOSED")

# --- exercise the engine, do not merely hash it ---
from rvt_swarm.cleanroom.family_statistic import CLEAN_ROOM_SEEDS, family_nll, family_statistic_replicates
from rvt_swarm.cleanroom.selection import (CLEAN_ROOM_BOOTSTRAP_REPLICATES,
    CLEAN_ROOM_BOOTSTRAP_SEED, DOWNSTREAM_REPRESENTATIVE_SEED, DeltaInterval, select_family)
from rvt_swarm.cleanroom.calibration_contract import TEMPERATURE_SCALING_ACTIVATED, clean_room_calibration
from rvt_swarm.cleanroom.universe import assert_episode_universe, zero_yield_episodes
from rvt_swarm.openloop_v3.bootstrap import build_cluster_design

ck("family statistic is the three-seed mean, executed",
   family_nll({11: 0.3, 29: 0.6, 47: 0.9}) == 0.6)
ids = [f"e{i}" for i in range(8)]
lay = {e: ("L0" if i < 4 else "L1") for i, e in enumerate(ids)}
ev = [e for e in ids[:6] for _ in range(3)]
uni = assert_episode_universe(ids, lay, ev, expected_count=8)
ck("zero-yield episodes stay in the universe, executed",
   len(uni) == 8 and zero_yield_episodes(uni, ev) == ("e6","e7"))
des = build_cluster_design(ev, uni)
per_seed = {11: [0.9]*len(ev), 29: [0.9]*len(ev), 47: [0.3]*len(ev)}
out = family_statistic_replicates({"M1": per_seed}, {"M0": [0.5]*len(ev)}, des,
                                  replicates=32, seed=CLEAN_ROOM_BOOTSTRAP_SEED)
ck("family statistic is not the best seed, executed",
   np.allclose(out["M1"], 0.7) and not np.allclose(out["M1"], 0.3))
def D(l, u): return DeltaInterval("d", (l+u)/2, l, u)
ck("selection rule case 4 parsimony, executed",
   select_family(D(-0.3,-0.2), D(-0.4,-0.3), D(-0.09,0.01)).winner == "M1" and
   select_family(D(-0.3,-0.2), D(-0.4,-0.3), D(-0.09,-0.01)).winner == "M2")
ck("eligibility strict at zero, executed", select_family(D(-0.2,0.0), D(-0.2,0.0), D(-0.1,-0.05)).winner == "M0")
ck("bootstrap constants match the contract",
   CLEAN_ROOM_BOOTSTRAP_REPLICATES == c["family_selection_rule"]["bootstrap"]["replicates"] and
   CLEAN_ROOM_BOOTSTRAP_SEED == c["family_selection_rule"]["bootstrap"]["seed"] and
   tuple(CLEAN_ROOM_SEEDS) == (11,29,47))
ck("clean-room bootstrap seed differs from the pilot's", CLEAN_ROOM_BOOTSTRAP_SEED != 20260821)
ck("downstream seed fixed at 47", DOWNSTREAM_REPRESENTATIVE_SEED == 47 and
   c["downstream_representative"]["selected_using_SELECT_R"] is False)
z = torch.full((64,), 0.3); t = torch.full((64,), 0.4); w = torch.full((64,), 1/64)
r0 = clean_room_calibration(z, t, w)
ck("constant predictor declared non-identifiable, executed",
   r0.identifiable is False and r0.intercept is None and r0.distinct_logits == 1)
zz = torch.linspace(-2, 2, 64)
ck("varying predictor identifiable, executed", clean_room_calibration(zz, t, w).identifiable is True)
try:
    clean_room_calibration(zz, torch.full((64,), 5.0), w); bad = False
except Exception: bad = True
ck("calibration integrity violation hard-fails, executed", bad)
ck("temperature scaling not activated", TEMPERATURE_SCALING_ACTIVATED is False and
   c["calibration_contract"]["temperature_scaling"] == "NOT_ACTIVATED")

# --- firewalls, rules, state ---
ck("MAIN-R firewall", c["main_r_firewall"]["MAIN_R_generated_before_system_freeze"] is False and
   c["main_r_firewall"]["generation_permitted_only_at"].startswith("CR-9"))
ck("MAIN-R never reused for development", c["main_r_failure_rule"]["MAIN_R_reused_for_development"] is False)
ck("M1-vs-M2 alone cannot claim message-passing causality",
   c["baselines_and_ablations"]["M1_vs_M2_alone_may_claim_message_passing_causality"] is False)
ck("capacity-matched mechanism control is specified",
   "A3_capacity_matched_non_message_passing" in c["baselines_and_ablations"])
ck("safety is a core outcome with a binding interpretation rule",
   c["safety_contract"]["safety_is_a_core_outcome"] is True and
   "DOES NOT support the central claim" in c["safety_contract"]["interpretation_rule"])
ck("oracle frozen before CL-DEV-R with a risk rule",
   c["oracle_ceiling"]["frozen_before_CL_DEV_R_exists"] is True and
   "CORE_RECOVERABILITY_DECISION_PREMISE_AT_RISK" in json.dumps(c["oracle_ceiling"]["interpretation_rule"]))
ck("development budget is bounded", c["closed_loop_development_space"]["development_budget"]["maximum_evaluated_configurations"] == 40)
ck("decentralization required and centralized runtime forbidden",
   c["closed_loop_architecture"]["runtime_decentralization"] == "REQUIRED" and
   "centralized global-state controller" in c["closed_loop_architecture"]["forbidden_final_runtime_dependency"])
import re as _re, ast as _ast
_paths, _syms = [], []
for _spec in c["closed_loop_architecture"]["bound_components"].values():
    _found = _re.findall(r"rvt_swarm/[A-Za-z0-9_/]+\.py", _spec)
    _base = _found[0].rsplit("/", 1)[0] if _found else None
    for _e in _re.findall(r"(?<![/\w])([a-z0-9_]+\.py)", _spec):
        if _base and not any(_p.endswith("/" + _e) for _p in _found):
            _found.append(f"{_base}/{_e}")
    _paths.extend(_found)
    for _sym in _re.findall(r"::([A-Za-z_][A-Za-z0-9_]*)", _spec):
        _syms.append((_found[0], _sym))
ck("every bound closed-loop component file exists",
   all((ROOT / _p).exists() for _p in _paths), f"{len(_paths)} paths")
_missing = []
for _p, _sym in _syms:
    _tree = _ast.parse((ROOT / _p).read_text())
    _names = {n.name for n in _ast.walk(_tree)
              if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))}
    if _sym not in _names: _missing.append(f"{_p}::{_sym}")
ck("every bound closed-loop symbol is defined", not _missing,
   f"{len(_syms)} symbols checked" + (f", missing {_missing}" if _missing else ""))
ck("F9 limitation predeclared, not repaired", "predeclared" in c["protected_generalization"]["F9_local_observability"].lower())
st = c["cr0_state"]
ck("no clean-room data exists and no model trained", not any(st.values()))
ck("qualification suite hash live and result recorded",
   c["adversarial_qualification"]["engine_suite_at_CR0"]["sha256"] == h("tests/test_cleanroom_engine.py") and
   c["adversarial_qualification"]["engine_suite_at_CR0"]["result"] == "29 passed")

print("\nVERIFICATION", "PASS" if not fail else f"FAIL {fail}")
print("CLEAN_ROOM_GLOBAL_CONTRACT_ROOT", c["rvt_swarm_clean_room_global_contract_root"])
