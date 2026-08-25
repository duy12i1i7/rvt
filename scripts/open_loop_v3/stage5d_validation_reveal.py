"""Stage 5D -- the single preregistered VALIDATION reveal.

Evaluates exactly M0, M1 seed 47 and M2 seed 47 under the frozen metrics,
frozen bootstrap and frozen family-selection rule. No optimizer is constructed,
no gradient is taken, no parameter is fitted on VALIDATION.
"""
from __future__ import annotations
import hashlib, json, math, os, pathlib, sys, time

sys.path.insert(0, "/opt/rvt"); os.chdir("/opt/rvt")
import numpy as np
import torch

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document, verify_canonical_hash
from rvt_swarm.fd24 import loss_v3, metrics_v3
from rvt_swarm.fd24.configuration import fd24_model_config_from_source
from rvt_swarm.fd24.model import RVTFD24LocalModel, prepare_fd24_model_batch
from rvt_swarm.openloop_v3.bootstrap import (
    BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED, build_cluster_design,
    paired_difference_interval, stratified_episode_bootstrap,
)
from rvt_swarm.openloop_v3.calibration import (
    CalibrationContractError, calibration_report, reliability_and_ece,
)
from rvt_swarm.openloop_v3.driver import GraphCache, load_events
from rvt_swarm.openloop_v3.envelope import load_study_checkpoint_envelope, restore_m1
from rvt_swarm.openloop_v3.m1 import m1_feature_batch
from rvt_swarm.openloop_v3.selection import select_family
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG
from rvt_swarm.topology_registry import COMPACT, LINE

OUT = pathlib.Path("/out")          # stage-5c workspace (read-only inputs)
DEST = pathlib.Path("/selection")   # stage-5d outputs
VAL = pathlib.Path("/validation")
def digest(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

manifest = json.loads((OUT / "open_loop_v3_validation_evaluation_manifest_v1.json").read_text())
assert verify_canonical_hash(
    manifest, "open_loop_v3_validation_evaluation_manifest_v1_sha256")
assert manifest["open_loop_v3_validation_evaluation_manifest_v1_sha256"] == (
    "f13645aa178ce45586ae7ad5a6f8d18a29404174654388d2fcb7652ad6cd6d1f")
print("evaluation manifest verified", flush=True)

# ---- validation seal, still metadata only -------------------------------
vseal = json.loads((VAL / "seal" / "official_v3_validation_seal_v1.json").read_text())
assert verify_canonical_hash(vseal, "official_v3_validation_seal_root")
assert vseal["official_v3_validation_seal_root"] == (
    "770957243df01a4077ef331e55b1e6ee892b64f2c410112e656ed38832fd8d84")
assert vseal["canonical_dataset"]["canonical_validation_content_root"] == (
    "fa12acba2e8fffc0ba85a992fca9d18654d9e14d0efef1bca366a760ca390283")
print("validation seal + content root verified", flush=True)

REVEAL_TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
print("VALIDATION_REVEAL_OCCURRED YES", REVEAL_TS, flush=True)

# ================= THE REVEAL: supervision (k, R) is read here =============
groups = load_events(VAL / "staging" / "v3_recoverability", split="v3_validation")
assert len(groups) == 1270, len(groups)
cache = GraphCache()
rows_total = sum(g.row_count for g in groups)
assert rows_total == 23040, rows_total
print(f"events {len(groups)} rows {rows_total}", flush=True)

m0_p = float(json.loads(
    (OUT / "m0_fitted_train_artifact_v1.json").read_text())["p_hat"])
m0_logit = math.log(m0_p / (1.0 - m0_p))

m1_env = load_study_checkpoint_envelope(OUT / "checkpoints" / "M1-seed47.pt")
m1_model = restore_m1(m1_env); m1_model.eval()
m2_env = load_study_checkpoint_envelope(OUT / "checkpoints" / "M2-seed47.pt")
m2_payload = m2_env["family_payload"]["fd24_checkpoint"]
m2_model = RVTFD24LocalModel(
    fd24_model_config_from_source(m2_payload["model_config"]), DEFAULT_RUNTIME_CONFIG)
m2_model.load_state_dict(m2_payload["state_dict"]); m2_model.eval()

FAMILIES = ("M0", "M1", "M2")
per_event_nll = {f: [] for f in FAMILIES}
per_event_brier = {f: [] for f in FAMILIES}
predictions = {f: [] for f in FAMILIES}
cal_logits = {f: [] for f in FAMILIES}
cal_targets, cal_weights = [], []
event_episode, episode_layout = [], {}
E = len(groups)

with torch.no_grad():
    for group in groups:
        graphs = {c: cache.graphs_for(getattr(group, "compact" if c == COMPACT else "line"))
                  for c in (COMPACT, LINE)}
        candidate_of = {COMPACT: group.compact, LINE: group.line}
        identity = group.compact.rows[0]["scientific_identity"]
        event_episode.append(str(identity["episode_id"]))
        episode_layout[str(identity["episode_id"])] = str(identity["layout_sha256"])
        logits = {}
        for family in FAMILIES:
            per_candidate = {}
            for c in (COMPACT, LINE):
                n = len(graphs[c])
                if family == "M0":
                    z = torch.full((n,), m0_logit, dtype=torch.float32)
                elif family == "M1":
                    z = m1_model(m1_feature_batch(graphs[c]))
                else:
                    batch = prepare_fd24_model_batch(graphs[c])
                    z = m2_model.recoverability_head(
                        m2_model.conditioned_representation(batch))
                    order = batch.graph_batch.canonical_to_input_order
                    inverse = [0] * n
                    for canonical, original in enumerate(order):
                        inverse[original] = canonical
                    z = z[torch.tensor(inverse, dtype=torch.int64)]
                per_candidate[c] = z
            logits[family] = per_candidate
            term = {"compact_logits": per_candidate[COMPACT],
                    "compact_k": group.compact.k, "compact_R": group.compact.R,
                    "line_logits": per_candidate[LINE],
                    "line_k": group.line.k, "line_R": group.line.R}
            per_event_nll[family].append(float(loss_v3.event_loss(**term)))
            per_event_brier[family].append(float(metrics_v3.brier_event(
                compact_probabilities=torch.sigmoid(per_candidate[COMPACT]),
                compact_k=group.compact.k, compact_R=group.compact.R,
                line_probabilities=torch.sigmoid(per_candidate[LINE]),
                line_k=group.line.k, line_R=group.line.R)))
            for c in (COMPACT, LINE):
                probs = torch.sigmoid(per_candidate[c])
                for row, p in zip(candidate_of[c].rows, probs.tolist()):
                    predictions[family].append(
                        [str(row["scientific_row_id"]), float(p)])
                cal_logits[family].extend(per_candidate[c].tolist())
        weight = 1.0 / (2.0 * group.team_size * E)
        for c in (COMPACT, LINE):
            target = float(candidate_of[c].k) / float(candidate_of[c].R)
            cal_targets.extend([target] * group.team_size)
            cal_weights.extend([weight] * group.team_size)

coverage = {}
for family in FAMILIES:
    predictions[family].sort()
    ids = [row for row, _ in predictions[family]]
    assert len(ids) == 23040 and len(set(ids)) == 23040
    artifact = {"schema_version": "rvt-open-loop-v3-validation-predictions/v1",
                "family": family, "rows": len(ids),
                "predictions": predictions[family]}
    path = DEST / f"validation_predictions_{family}.json"
    path.write_text(json.dumps(artifact, indent=1, sort_keys=True) + "\n")
    coverage[family] = {"rows": len(ids), "coverage": 1.0,
                        "artifact_sha256": digest(path),
                        "predictions_root": sha256_document(predictions[family])}
    print(f"{family} predictions {len(ids)} rows sha={coverage[family]['artifact_sha256'][:16]}",
          flush=True)

aggregate = {}
for family in FAMILIES:
    nll = float(np.mean(per_event_nll[family]))
    brier = float(np.mean(per_event_brier[family]))
    logits_t = torch.tensor(cal_logits[family], dtype=torch.float32)
    targets_t = torch.tensor(cal_targets, dtype=torch.float32)
    weights_t = torch.tensor(cal_weights, dtype=torch.float32)
    # The reliability diagram and ECE need no regression and are always defined.
    bins, ece, empty = reliability_and_ece(
        torch.sigmoid(logits_t), targets_t, weights_t)
    # The intercept/slope regression needs spread in the logit. A CONSTANT
    # predictor has none, so its slope is not identifiable -- there is nothing to
    # regress against. That is a property of M0, not a failure of the metric, and
    # calibration is DIAGNOSTIC_ONLY and participates in no selection. It is
    # reported as not identifiable rather than replaced by another estimator.
    identifiable = True
    intercept = slope = None
    try:
        intercept, slope = __import__(
            "rvt_swarm.openloop_v3.calibration", fromlist=["x"]
        ).calibration_intercept_slope(logits_t, targets_t, weights_t)
    except CalibrationContractError as exc:
        identifiable = False
        reason = str(exc)
    aggregate[family] = {
        "validation_nll": nll, "validation_brier": brier,
        "calibration_intercept": intercept,
        "calibration_slope": slope,
        "calibration_identifiable": identifiable,
        "calibration_not_identifiable_reason": (
            None if identifiable else
            "a constant predictor has zero logit spread, so the calibration "
            "slope is not identifiable; the reliability diagram and ECE below "
            "are unaffected"),
        "distinct_logits": int(torch.unique(logits_t).numel()),
        "expected_calibration_error": ece,
        "empty_bins": empty,
        "reliability_bins": [
            {"index": b.index, "lower": b.lower, "upper": b.upper,
             "right_closed": b.right_closed, "weight": b.weight,
             "mean_probability": None if b.empty else b.mean_probability,
             "mean_target": None if b.empty else b.mean_target, "empty": b.empty}
            for b in bins]}
    shown = (f"a={intercept:.6f} b={slope:.6f}" if identifiable
             else "a=NOT_IDENTIFIABLE b=NOT_IDENTIFIABLE")
    print(f"{family}: NLL={nll!r} Brier={brier!r} {shown} "
          f"ECE={ece:.6f} empty_bins={empty} "
          f"distinct_logits={aggregate[family]['distinct_logits']}", flush=True)

# The frozen bootstrap resamples "that layout's source episodes ... preserving
# that layout's original episode count", and the preregistration states that an
# M = 0 episode contributes no events and that this is correct. The pool must
# therefore be ALL of the split's source episodes, not only the ones that
# yielded events: a zero-yield episode is a legitimate draw that contributes
# nothing. Enumerating the full pool from the acquisition records rather than
# from the observed events is what makes the design match the frozen rule.
full_pool = dict(episode_layout)
for record_path in sorted((VAL / "stage_a").glob("*.json")):
    record = json.loads(record_path.read_text())
    full_pool.setdefault(str(record["episode_id"]), str(record["layout_sha256"]))
print(f"episode pool: contributing={len(episode_layout)} "
      f"total_source_episodes={len(full_pool)} "
      f"zero_yield={len(full_pool) - len(episode_layout)}", flush=True)
design = build_cluster_design(event_episode, full_pool)
print(f"bootstrap design: layouts={len(design.layout_ids)} "
      f"episodes={sum(len(v) for v in design.episode_ids_by_layout.values())} "
      f"events={design.event_count}", flush=True)
replicates = stratified_episode_bootstrap(
    {f: per_event_nll[f] for f in FAMILIES}, design,
    replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED)

deltas = {}
for label, a, b in (("delta_10", "M1", "M0"), ("delta_20", "M2", "M0"),
                    ("delta_21", "M2", "M1")):
    lower, upper = paired_difference_interval(replicates[a], replicates[b])
    point = aggregate[a]["validation_nll"] - aggregate[b]["validation_nll"]
    deltas[label] = {"comparison": f"NLL({a}) - NLL({b})", "point_estimate": point,
                     "ci_lower_95": lower, "ci_upper_95": upper}
    print(f"{label} = {a}-{b}: point={point!r} CI=[{lower!r}, {upper!r}]", flush=True)

outcome = select_family(upper_ci_delta_10=deltas["delta_10"]["ci_upper_95"],
                        upper_ci_delta_20=deltas["delta_20"]["ci_upper_95"],
                        upper_ci_delta_21=deltas["delta_21"]["ci_upper_95"])
print(f"FAMILY_WINNER {outcome.winner} case={outcome.case} "
      f"m1_eligible={outcome.m1_eligible} m2_eligible={outcome.m2_eligible} "
      f"learnability={outcome.learnability_supported}", flush=True)
print("rationale:", outcome.rationale, flush=True)

result = {
 "schema_version": "rvt-open-loop-v3-validation-evaluation-result/v1",
 "open_loop_v3_validation_evaluation_manifest_v1_sha256":
     manifest["open_loop_v3_validation_evaluation_manifest_v1_sha256"],
 "validation_reveal_occurred": True,
 "validation_reveal_timestamp_utc": REVEAL_TS,
 "validation_status_after_reveal": "SPENT_MODEL_SELECTION_SET",
 "official_v3_validation_seal_root": vseal["official_v3_validation_seal_root"],
 "official_v3_validation_content_root":
     vseal["canonical_dataset"]["canonical_validation_content_root"],
 "events": len(groups), "rows": rows_total,
 "coverage": coverage,
 "aggregate_metrics": aggregate,
 "paired_bootstrap": {
  "resampling_unit": "SOURCE_EPISODE", "stratification": "VALIDATION_LAYOUT",
  "replicates": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED,
  "interval": "95 percent percentile", "paired": True,
  "layouts": len(design.layout_ids),
  "episodes": sum(len(v) for v in design.episode_ids_by_layout.values()),
  "episode_pool": "all source episodes of the split, including zero-yield",
  "contributing_episodes": len(episode_layout),
  "zero_yield_episodes_in_pool": len(full_pool) - len(episode_layout),
  "deltas": deltas},
 "family_selection": {
  "rule_root": manifest["family_selection_rule_root"],
  "m1_eligible_vs_m0": outcome.m1_eligible,
  "m2_eligible_vs_m0": outcome.m2_eligible,
  "case": outcome.case, "winner": outcome.winner,
  "learnability_supported": outcome.learnability_supported,
  "rationale": outcome.rationale, "rule_modified": False},
 "temperature_scaling_activated": False,
 "parameters_fitted_on_validation": 0,
 "optimizer_steps": 0, "gradient_updates": 0,
 "protected_domain_access": 0,
}
sealed = attach_canonical_hash(result, "validation_evaluation_result_v1_sha256")
path = DEST / "validation_evaluation_result_v1.json"
path.write_text(json.dumps(sealed, indent=1, sort_keys=True) + "\n", encoding="ascii")
print("RESULT_ROOT", sealed["validation_evaluation_result_v1_sha256"], flush=True)
print("REVEAL_DONE", flush=True)
