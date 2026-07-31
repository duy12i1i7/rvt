# Task 4 — Invalid Evaluation Notice

Status of `docs/LOCAL_CONTROLLER_RECONFIGURATION_QUALIFICATION.md` and
`results/local_controller_reconfiguration_qualification/`.

**Nothing is deleted.** Both are preserved as-is for provenance.

---

## 1. The controller-recovery conclusion is withdrawn

> ### INCONCLUSIVE — INVALID FORMATION METRIC AND QUALIFICATION GEOMETRY

The Task 4 report reached verdict **B** ("LINE → KEEP recovery does not
complete"). That conclusion is **withdrawn**. It is not evidence that recovery
is mechanically unsuccessful, because the evaluation could not have produced a
success for any policy.

Three independent defects, each sufficient on its own:

1. **Incommensurable tolerance.** The recovery metric used max-over-*pairwise*
   errors against `epsilon_form = 0.55 m`, a tolerance calibrated for
   *per-robot* formation error. A pairwise error accumulates two robots'
   deviations, so the criterion was roughly twice as strict as intended. On the
   same open-field episode the controller sat at median 0.861 m pairwise but
   median 0.435 m per-robot — inside the tube under the established convention,
   outside it under the one used.
2. **Invalid initial condition.** The swarm did not start inside the nominal
   KEEP tube: `E_keep = 3.018 m` at step 0, `initial_keep_valid = 0.0`. Failure
   to reach a formation the episode never started in was being counted as a
   recovery failure.
3. **Unsuitable qualification geometry.** The old validation layouts were never
   designed with a downstream recovery region large enough for the N = 6 KEEP
   template (`W_req ≈ 3.26 m`). A negative recovery result on geometry that
   cannot host the formation is not evidence about the controller.

## 2. What is invalid, and what survives

**INVALID for scientific interpretation — must be recomputed:**

| quantity | where |
|---|---|
| `keep_recovered` | every arm, every probe |
| `recovery_dwell_complete` | every arm, every probe |
| `full_reconfiguration_success` | every arm, every probe |
| `initial_keep_valid` | every arm, every probe |
| `formation_rms_before` / `_inside` / `_after` | every arm, every probe |
| verdict **B** | report §1 |

Every one of these depends on the pairwise metric, the invalid initial
condition, or both.

**Remains valid as diagnostic** (independent of the formation metric):

| quantity | value | why it survives |
|---|---|---|
| bottleneck / exit-plane crossing | e.g. always-line 0.889, scripted K→L→K 1.000 | purely geometric, from positions vs the exit plane |
| goal reaching | always-line 1.000 | environment-scored |
| collision-free rate | always-line 1.000, always-keep 0.972 | episode-wide, formation-independent |
| deadlock | all arms | environment-scored |
| transition count and timing | all arms | from the mode trace |
| time in line | all arms | from the mode trace |
| communication accounting | beacon 3600/176 400 B, trigger 1208/25 368 B, score 1208/24 160 B, confirm 1208/19 328 B | counted at the send site from real serialized messages |
| runtime integration evidence | Task 3 | unaffected |

The separation of navigation from reconfiguration still holds as a *design*
observation — always-line navigates best (goal 1.000, collision-free 1.000) —
but the claim that it therefore fails reconfiguration cannot be made from these
numbers, because no arm could pass.

## 3. Also withdrawn: the N = 4 arm

Recomputing disjointness under the V3 metric (Task 4R-2) shows the KEEP and
LINE templates are **not sufficiently separated at N = 4**. All N = 4 results in
the preserved run are therefore invalid for reconfiguration purposes regardless
of the metric repair. See `docs/KEEP_LINE_DISJOINTNESS_V3.md`.

## 4. Order of repair

This notice is committed **before** the metric is changed, so the invalid state
is recorded in history rather than overwritten. Repairs follow in
4R-1 … 4R-7, and `epsilon_form = 0.55 m` is **not** adjusted at any point.
