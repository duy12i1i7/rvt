"""Stage 5E independent verification -- re-derive every bound claim from source."""
from __future__ import annotations
import hashlib, json, pathlib, sys
sys.path.insert(0, "/Users/udy/rvt")
from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.openloop_v3.selection import select_family

R = pathlib.Path("/Users/udy/rvt/results/rvt_fd24")
def fh(p): return hashlib.sha256((R / p).read_bytes()).hexdigest()
nc  = json.loads((R / "open_loop_v3_novelty_checkpoint_1_v1.json").read_text())
man = json.loads((R / "open_loop_v3_validation_evaluation_manifest_v1.json").read_text())
sel = json.loads((R / "open_loop_v3_validation_selection_v1.json").read_text())
res = json.loads((R / "validation_evaluation_result_v1.json").read_text())
rule= json.loads((R / "open_loop_v3_family_selection_rule_v1.json").read_text())
pre = json.loads((R / "open_loop_v3_recoverability_predictor_preregistration_v1.json").read_text())
clo = json.loads((R / "phase9g_v2a_v_official_validation_closure_v1.json").read_text())
fail = []
def ck(n, ok, d=""):
    print(("PASS " if ok else "FAIL ") + n + (f" -- {d}" if d else ""))
    if not ok: fail.append(n)

ck("checkpoint canonical hash", verify_canonical_hash(nc, "open_loop_v3_novelty_checkpoint_1_root"))
ck("checkpoint root as reported",
   nc["open_loop_v3_novelty_checkpoint_1_root"] == "d36bc4e4c43cb0062dbdfcd73b471e6683a422d391dab75ab99b1236dc0330d1")
for name, path, key, want in [
  ("preregistration","open_loop_v3_recoverability_predictor_preregistration_v1.json",
   "open_loop_v3_recoverability_predictor_preregistration_v1_sha256","8619ac4c8a60740209d826910d9002d12d63f825886b4869e08c883024e7dbf6"),
  ("winner rule","open_loop_v3_family_selection_rule_v1.json",
   "open_loop_v3_family_selection_rule_v1_sha256","f65e60fee5b5c0e7249b3594a25d4cb54bf826c19be2cf3aad75df5f1b72f1f5"),
  ("pre-reveal manifest","open_loop_v3_validation_evaluation_manifest_v1.json",
   "open_loop_v3_validation_evaluation_manifest_v1_sha256","f13645aa178ce45586ae7ad5a6f8d18a29404174654388d2fcb7652ad6cd6d1f"),
  ("selection root","open_loop_v3_validation_selection_v1.json",
   "open_loop_v3_validation_selection_root","b1110cd1f5586a0daaf76762afef81d5feb867eee9b00a6ccf3d7776c6d18eec")]:
    doc = json.loads((R / path).read_text())
    ck(f"{name} canonical + exact", verify_canonical_hash(doc, key) and doc[key] == want)
    ck(f"checkpoint binds {name}", want in json.dumps(nc))

# finding 1 -- reproduce the mismatch from source
ck("rule family_statistic quoted verbatim",
   nc["finding_1_seed_family_statistic"]["frozen_requirement"] == rule["family_statistic"])
ck("rule requires a three-seed mean",
   "mean over the three frozen training seeds {11,29,47}" in rule["family_statistic"])
ck("manifest froze exactly one seed per learned family",
   man["families"]["M1"]["training_seed"] == 47 and man["families"]["M2"]["training_seed"] == 47
   and man["families"]["M1"]["checkpoint_file"] == "M1-seed47.pt"
   and man["families"]["M2"]["checkpoint_file"] == "M2-seed47.pt")
ck("R17 binds that same rule root",
   pre["R17_family_selection_rule"]["open_loop_v3_family_selection_rule_v1_sha256"] == rule["open_loop_v3_family_selection_rule_v1_sha256"])
ck("preregistration supersedes nothing", pre["supersedes"] is None)
ck("R18 object is a TRAIN median, not a VALIDATION mean",
   "MEDIAN TRAIN-only cross-validation NLL" in pre["R18_seed_and_downstream_checkpoint"]["downstream_checkpoint_per_family"])
ck("R18 later_use is conditional on the family already winning",
   "if its family wins" in pre["R18_seed_and_downstream_checkpoint"]["later_use"])
ck("R18 requires all three seeds reported",
   pre["R18_seed_and_downstream_checkpoint"]["all_three_seeds_trained_and_reported"] is True)
ck("no per-seed VALIDATION statistic exists in any Stage-5D artifact",
   "per_seed" not in json.dumps(sel) and "per_seed" not in json.dumps(res))
ck("R19 preregisters SEED_INSTABILITY",
   any(c["id"] == "SEED_INSTABILITY" for c in pre["R19_falsification"]["conditions"]))

# finding 2 -- reproduce the pool arithmetic from the closure ledger
fam = clo["family_by_n"]
byl = {}
for k, c in fam.items():
    f = k.split("/")[0]
    a = byl.setdefault(f, {"src": 0, "mz": 0})
    a["src"] += c.get("source_episodes") or 0
    a["mz"] += c.get("M_zero") or 0
tot = sum(a["src"] for a in byl.values()); mz = sum(a["mz"] for a in byl.values())
ck("closure ledger gives 300 original / 294 contributing / 6 zero-yield",
   tot == 300 and mz == 6 and tot - mz == 294)
ck("every layout has 30 original source episodes", all(a["src"] == 30 for a in byl.values()))
off = {f: a for f, a in byl.items() if a["mz"]}
ck("exactly one layout carries all zero-yield episodes and drew the wrong size",
   len(off) == 1 and "F4" in off and off["F4"]["src"] - off["F4"]["mz"] == 24,
   f"{ {f: (a['src'], a['src']-a['mz']) for f,a in off.items()} }")
ck("R16 requires the layout's ORIGINAL episode count",
   "original episode count" in pre["R16_inference_bootstrap"]["scheme"])
ck("authoritative result used the 300 pool",
   res["paired_bootstrap"]["episodes"] == 300 and res["paired_bootstrap"]["contributing_episodes"] == 294)
ck("checkpoint records both pools", nc["finding_2_bootstrap_pool"]["classification_294"] == "NONAUTHORITATIVE_EXECUTION_DEFECT"
   and nc["finding_2_bootstrap_pool"]["classification_300"] == "EXECUTION_CORRECTION_TO_FROZEN_SPECIFICATION")
ck("defective output not deliberately deleted", nc["defective_294_pool_artifacts"]["deleted_deliberately"] is False)

# finding 3 -- reproduce the code facts
cal = pathlib.Path("/Users/udy/rvt/rvt_swarm/openloop_v3/calibration.py").read_text()
rev = pathlib.Path("/Users/udy/rvt/scripts/open_loop_v3/stage5d_validation_reveal.py").read_text()
ck("calibration.py byte-identical to the pre-reveal manifest",
   hashlib.sha256(cal.encode()).hexdigest() == man["metric_implementations"]["calibration"])
ck("CalibrationContractError declares fail-closed",
   "A calibration-contract violation that must fail closed." in cal)
ck("CalibrationReport types intercept/slope non-Optional",
   "intercept: float" in cal and "slope: float" in cal)
ck("11 raise sites for the contract error", cal.count("raise CalibrationContractError") == 11)
ck("wrapper catches the type bare", "except CalibrationContractError as exc:" in rev)
import ast as _ast
_t = _ast.parse(rev)
_st = [n.lineno for n in _ast.walk(_t) if isinstance(n, _ast.Name) and n.id == "reason" and isinstance(n.ctx, _ast.Store)]
_ld = [n.lineno for n in _ast.walk(_t) if isinstance(n, _ast.Name) and n.id == "reason" and isinstance(n.ctx, _ast.Load)]
ck("captured exception text is a dead variable (AST)", len(_st) >= 1 and len(_ld) == 0,
   f"stored at {_st}, never loaded")
ck("serialized reason is a hardcoded literal, not the raised message",
   any(isinstance(n, _ast.Constant) and isinstance(n.value, str)
       and "constant predictor has zero logit spread" in n.value for n in _ast.walk(_t)))
ck("frozen composite imported but never called",
   "calibration_report" in rev and rev.count("calibration_report(") == 0)
ck("M0 distinct logits is 1", res["aggregate_metrics"]["M0"]["distinct_logits"] == 1)
ck("M0 intercept and slope are null",
   res["aggregate_metrics"]["M0"]["calibration_intercept"] is None and
   res["aggregate_metrics"]["M0"]["calibration_slope"] is None)
ck("M1 and M2 calibration identifiable",
   all(res["aggregate_metrics"][f]["calibration_identifiable"] for f in ("M1","M2")))
ck("no data-integrity abort was actually suppressed",
   res["aggregate_metrics"]["M1"]["calibration_identifiable"] is True and
   res["aggregate_metrics"]["M2"]["calibration_identifiable"] is True)

# winner re-derivation
pb = res["paired_bootstrap"]["deltas"]
o = select_family(upper_ci_delta_10=pb["delta_10"]["ci_upper_95"],
                  upper_ci_delta_20=pb["delta_20"]["ci_upper_95"],
                  upper_ci_delta_21=pb["delta_21"]["ci_upper_95"])
w = o.winner if hasattr(o, "winner") else o["winner"]
c = o.case if hasattr(o, "case") else o["case"]
ck("frozen rule re-derives M2 case 4 from the recorded intervals", w == "M2" and c == 4)
ck("checkpoint records the caveat that re-derivation does not cure finding 1",
   "does NOT cure finding_1" in nc["winner_re_derivation"]["caveat"])

# ledger + boundaries
ck("H1 and H2 suspended, not established",
   nc["evidence_ledger"]["H1_learned_recoverability_signal"]["status"] == "SUSPENDED_PENDING_FROZEN_STATISTIC" and
   nc["evidence_ledger"]["H2_graph_family_predictive_advantage"]["status"] == "SUSPENDED_PENDING_FROZEN_STATISTIC")
ck("H3 and H5..H8 not established",
   all(nc["evidence_ledger"][k]["status"] == "NOT_YET_ESTABLISHED" for k in
       ("H3_causal_graph_structure_advantage","H5_counterfactual_topology_decision_benefit",
        "H6_progress_recovery_liveness_benefit","H7_safety_preservation",
        "H8_protected_domain_generalization")))
ck("H4 records over-confidence, not good calibration",
   nc["evidence_ledger"]["H4_calibrated_probability_quality"]["m2_slope"] < 1.0)
ck("novelty not claimed proven", nc["novelty_thesis_status"]["novelty_proven"] is False)
ck("protected contact NONE and zero outcomes",
   nc["protected_domains"]["protected_domain_contact"] == "NONE" and
   nc["protected_domains"]["protected_outcomes_accessed"] == 0 and
   man["protected_domain_access"] == 0 and sel["protected_domain_access"] == 0)
ck("this stage trained/refit/recalibrated nothing",
   not any(nc["this_stage_performed"][k] for k in nc["this_stage_performed"]))
ck("spent state unaltered",
   nc["immutable_facts_not_altered_by_this_stage"]["validation_status"] == "SPENT_MODEL_SELECTION_SET" and
   nc["immutable_facts_not_altered_by_this_stage"]["family_winner_as_executed"] == "M2")
ck("verdict is C", nc["verdict"] == "C_POST_REVEAL_AUTHORITY_OR_PROVENANCE_FAILURE" and
   nc["advance_to_closed_loop_authorized"] is False)

print("\nVERIFICATION", "PASS" if not fail else f"FAIL {fail}")
print("NOVELTY_CHECKPOINT_1_ROOT", nc["open_loop_v3_novelty_checkpoint_1_root"])
print("file_sha256", fh("open_loop_v3_novelty_checkpoint_1_v1.json"))
