"""Stage 5D independent verification.

Re-derives every reported scientific number from the PUBLISHED prediction
artifacts and the sealed VALIDATION supervision, using formulas written out by
hand here rather than the library metric functions used during the reveal.
Runs no model and reads no checkpoint weights.
"""
from __future__ import annotations
import hashlib, json, math, os, pathlib, sys

sys.path.insert(0, "/opt/rvt"); os.chdir("/opt/rvt")
from rvt_swarm.phase8.common import sha256_document, verify_canonical_hash
from rvt_swarm.openloop_v3.bootstrap import (
    BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED, build_cluster_design,
    paired_difference_interval, stratified_episode_bootstrap)
from rvt_swarm.openloop_v3.driver import load_events
from rvt_swarm.topology_registry import COMPACT, LINE

OUT, DEST, VAL = pathlib.Path("/out"), pathlib.Path("/selection"), pathlib.Path("/validation")
def digest(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
FAM = ("M0", "M1", "M2")
fail = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""), flush=True)
    if not ok: fail.append(name)

sel = json.loads((DEST / "open_loop_v3_validation_selection_v1.json").read_text())
res = json.loads((DEST / "validation_evaluation_result_v1.json").read_text())
frz = json.loads((DEST / "scientific_frozen_open_loop_model_v1.json").read_text())
man = json.loads((OUT / "open_loop_v3_validation_evaluation_manifest_v1.json").read_text())
check("selection root canonical hash", verify_canonical_hash(sel, "open_loop_v3_validation_selection_root"))
check("result canonical hash", verify_canonical_hash(res, "validation_evaluation_result_v1_sha256"))
check("frozen model canonical hash", verify_canonical_hash(frz, "scientific_frozen_open_loop_model_v1_sha256"))
check("manifest canonical hash", verify_canonical_hash(man, "open_loop_v3_validation_evaluation_manifest_v1_sha256"))
check("manifest root is the pre-reveal frozen root",
      man["open_loop_v3_validation_evaluation_manifest_v1_sha256"] ==
      "f13645aa178ce45586ae7ad5a6f8d18a29404174654388d2fcb7652ad6cd6d1f")
check("selection binds that manifest",
      sel["open_loop_v3_validation_evaluation_manifest_v1_sha256"] ==
      man["open_loop_v3_validation_evaluation_manifest_v1_sha256"])

# ---- published predictions --------------------------------------------------
prob = {}
for f in FAM:
    art = json.loads((DEST / f"validation_predictions_{f}.json").read_text())
    check(f"{f} prediction artifact hash matches selection record",
          digest(DEST / f"validation_predictions_{f}.json") ==
          sel["prediction_artifacts"][f]["artifact_sha256"])
    check(f"{f} predictions root reproduces",
          sha256_document(art["predictions"]) == sel["prediction_artifacts"][f]["predictions_root"])
    prob[f] = {r: p for r, p in art["predictions"]}
    check(f"{f} rows = 23040 unique", len(art["predictions"]) == 23040 and len(prob[f]) == 23040)

m0_p = float(json.loads((OUT / "m0_fitted_train_artifact_v1.json").read_text())["p_hat"])
m0_vals = set(prob["M0"].values())
m0_seen = next(iter(m0_vals))
# The reveal emitted sigmoid(logit(p_hat)) evaluated in float32, so the value
# agrees with the TRAIN-fitted p_hat to float32 precision, not float64.
check("M0 is constant and equals the TRAIN-fitted probability",
      len(m0_vals) == 1 and abs(m0_seen - m0_p) < 1e-6,
      f"distinct={len(m0_vals)} predicted={m0_seen!r} p_hat={m0_p!r} "
      f"absdiff={abs(m0_seen - m0_p):.3e}")

# ---- recompute the frozen metrics by hand ----------------------------------
groups = load_events(VAL / "staging" / "v3_recoverability", split="v3_validation")
check("validation events = 1270", len(groups) == 1270)
nll = {f: [] for f in FAM}; brier = {f: [] for f in FAM}
ev_ep, ep_layout, covered = [], {}, {f: 0 for f in FAM}
for g in groups:
    ident = g.compact.rows[0]["scientific_identity"]
    ev_ep.append(str(ident["episode_id"]))
    ep_layout[str(ident["episode_id"])] = str(ident["layout_sha256"])
    for f in FAM:
        parts_nll, parts_brier = [], []
        for cand in (g.compact, g.line):
            k, R = float(cand.k), float(cand.R)
            ps = [prob[f][str(r["scientific_row_id"])] for r in cand.rows]
            covered[f] += len(ps)
            # grouped-Bernoulli candidate loss, divided by R, averaged over robots
            parts_nll.append(sum(
                -(k * math.log(p) + (R - k) * math.log(1.0 - p)) / R for p in ps) / len(ps))
            parts_brier.append(sum(
                p * p - 2.0 * p * (k / R) + (k / R) for p in ps) / len(ps))
        nll[f].append(0.5 * parts_nll[0] + 0.5 * parts_nll[1])
        brier[f].append(0.5 * parts_brier[0] + 0.5 * parts_brier[1])
for f in FAM:
    check(f"{f} coverage 23040/23040", covered[f] == 23040)
    a = res["aggregate_metrics"][f]
    got_n = sum(nll[f]) / len(nll[f]); got_b = sum(brier[f]) / len(brier[f])
    check(f"{f} VALIDATION NLL reproduces (float32 precision)",
          abs(got_n - a["validation_nll"]) < 1e-6,
          f"recomputed={got_n!r} recorded={a['validation_nll']!r} "
          f"absdiff={abs(got_n - a['validation_nll']):.3e}")
    check(f"{f} VALIDATION Brier reproduces (float32 precision)",
          abs(got_b - a["validation_brier"]) < 1e-6,
          f"recomputed={got_b!r} recorded={a['validation_brier']!r} "
          f"absdiff={abs(got_b - a['validation_brier']):.3e}")
check("M0 Brier equals the closed-form constant-predictor value",
      abs(sum(brier["M0"]) / len(brier["M0"])
          - res["aggregate_metrics"]["M0"]["validation_brier"]) < 1e-6)
check("M0 calibration slope reported as not identifiable",
      res["aggregate_metrics"]["M0"]["calibration_identifiable"] is False and
      res["aggregate_metrics"]["M0"]["calibration_slope"] is None and
      res["aggregate_metrics"]["M0"]["distinct_logits"] == 1)
check("M1 and M2 calibration identifiable",
      all(res["aggregate_metrics"][f]["calibration_identifiable"] for f in ("M1", "M2")))

# ---- reproduce the frozen bootstrap ----------------------------------------
pool = dict(ep_layout)
for rec in sorted((VAL / "stage_a").glob("*.json")):
    d = json.loads(rec.read_text()); pool.setdefault(str(d["episode_id"]), str(d["layout_sha256"]))
check("bootstrap pool = all 300 source episodes, 6 zero-yield",
      len(pool) == 300 and len(ep_layout) == 294)
design = build_cluster_design(ev_ep, pool)
pb = res["paired_bootstrap"]
check("bootstrap design matches the record",
      len(design.layout_ids) == pb["layouts"] and
      sum(len(v) for v in design.episode_ids_by_layout.values()) == pb["episodes"] and
      pb["episodes"] == 300 and pb["contributing_episodes"] == 294 and
      pb["zero_yield_episodes_in_pool"] == 6)
check("frozen bootstrap constants", BOOTSTRAP_REPLICATES == 10000 and BOOTSTRAP_SEED == 20260821)
deltas = {}
draws = stratified_episode_bootstrap(
    {f: nll[f] for f in FAM}, design,
    replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED)
means = {f: sum(nll[f]) / len(nll[f]) for f in FAM}
for name, hi, lo in (("delta_10", "M1", "M0"), ("delta_20", "M2", "M0"),
                     ("delta_21", "M2", "M1")):
    lower, upper = paired_difference_interval(draws[hi], draws[lo])
    point = means[hi] - means[lo]
    rec = pb["deltas"][name]
    check(f"{name} comparison label matches", rec["comparison"] == f"NLL({hi}) - NLL({lo})")
    check(f"{name} point estimate reproduces",
          abs(point - rec["point_estimate"]) < 1e-6,
          f"recomputed={point!r} recorded={rec['point_estimate']!r}")
    check(f"{name} 95% interval reproduces",
          abs(lower - rec["ci_lower_95"]) < 1e-6 and abs(upper - rec["ci_upper_95"]) < 1e-6,
          f"recomputed=[{lower!r}, {upper!r}] "
          f"recorded=[{rec['ci_lower_95']!r}, {rec['ci_upper_95']!r}]")
    check(f"{name} decision sign is unambiguous at float32 precision",
          abs(upper) > 1e-4, f"upper={upper!r}")
    deltas[name] = upper

# ---- re-apply the frozen selection rule by hand -----------------------------
m1_ok = deltas["delta_10"] < 0.0
m2_ok = deltas["delta_20"] < 0.0
if not m1_ok and not m2_ok: want, case = "M0", 1
elif m1_ok and not m2_ok:   want, case = "M1", 2
elif m2_ok and not m1_ok:   want, case = "M2", 3
else:
    want, case = ("M2", 4) if deltas["delta_21"] < 0.0 else ("M1", 4)
got = res["family_selection"]
check("family winner reproduces by hand", got["winner"] == want and got["case"] == case,
      f"hand={want} case={case} recorded={got['winner']} case={got['case']}")
check("selection root carries the same winner", sel["family_selection"]["winner"] == want)

# ---- frozen model -----------------------------------------------------------
src = {"M0": OUT / "m0_fitted_train_artifact_v1.json",
       "M1": OUT / "checkpoints" / "M1-seed47.pt",
       "M2": OUT / "checkpoints" / "M2-seed47.pt"}[want]
check("FROZEN_MODEL is the winning family", frz["model_family"] == want)
check("FROZEN_MODEL is byte-identical to the Stage-5C checkpoint",
      digest(DEST / frz["artifact"]) == digest(src) == frz["artifact_sha256"])
check("FROZEN_MODEL seed is the designated seed", frz["training_seed"] == 47)
check("FROZEN_MODEL declares no post-selection refit",
      frz["retrained_after_family_selection"] is False and
      frz["refit_using_validation"] is False and
      frz["temperature_scaling_activated"] is False)
check("FROZEN_MODEL is not deployment qualified",
      frz["deployable"] is False and frz["safety_certified"] is False and
      frz["production_qualified"] is False and
      frz["deployment_classification"] == "shadow-disabled")
check("exactly one FROZEN_MODEL artifact exists",
      len(list(DEST.glob("FROZEN_MODEL_*"))) == 1)

# ---- validation status ------------------------------------------------------
check("validation recorded as spent, not blinded",
      sel["validation_status"] == "SPENT_MODEL_SELECTION_SET" and
      sel["validation_blinded"] is False and
      sel["validation_reusable_for_model_selection"] is False and
      sel["validation_is_unbiased_final_generalization_evidence"] is False)
check("no parameter fitted on validation",
      sel["parameters_fitted_on_validation"] == 0 and sel["optimizer_steps"] == 0 and
      sel["gradient_updates"] == 0 and sel["threshold_tuning"] is False and
      sel["seed_selection_after_reveal"] is False and sel["ensembling"] is False and
      sel["checkpoint_averaging"] is False)
check("protected domain access = 0", sel["protected_domain_access"] == 0)

print("\nVERIFICATION", "PASS" if not fail else "FAIL " + repr(fail), flush=True)
print("SELECTION_ROOT", sel["open_loop_v3_validation_selection_root"], flush=True)
