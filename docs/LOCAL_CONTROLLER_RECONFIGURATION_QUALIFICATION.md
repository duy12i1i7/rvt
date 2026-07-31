# Local Controller Reconfiguration Qualification (Task 4)

No learned selector anywhere in this run. Robot-local controller with scripted
and geometric mode policies only. Validation layouts, **no final-test access**.

Results: `results/local_controller_reconfiguration_qualification/qualification.json`
Runtime: `docs/DECENTRALIZED_RUNTIME_INTEGRATION_AUDIT.md`,
`docs/DECENTRALIZED_RECONFIGURATION_STATE_MACHINE.md`

---

## 1. Verdict

> ### **B — Runtime integration is valid; LINE → KEEP recovery does not complete. But the recovery measurement is confounded by a defect in my own Task-2 metric, which must be repaired before the mechanical question can be answered.**

Not A: integration is demonstrably real (§2).
Not C: no arm achieved full reconfiguration success, so nothing is qualified.

## 2. Runtime integration — the Task 3 questions

| # | question | answer |
|---|---|---|
| 1 | Are `epoch.py` and `comm_cost.py` executed by the real runtime? | **Yes.** Spies on the authoritative functions fire during real episodes: `local_trigger`, `simulate_trigger_consensus`, `simulate_confirm_consensus`, `commit_or_retain`. |
| 2 | Has the inline periodic path been removed? | **Yes.** Only `legacy_periodic_epoch_baseline` remains, and it raises `CentralizedAccessError` under strict mode. Regression tests forbid `% decision_interval` and the lockstep `e + 1 for e in epoch_ids`. |
| 3 | Does confirmation prevent partial commitment? | **Yes.** Delay beyond `Delta_stale` drops confirmation traffic and every robot retains; `test_09` asserts one mode across the team. |
| 10 | Are bytes measured from actual runtime messages? | **Yes**, at the send site from the real serialized object. |

One corridor episode, N=6:

| category | messages | bytes | wire |
|---|---|---|---|
| beacon | 3600 | 176 400 | 49 B |
| trigger | 1208 | 25 368 | 21 B |
| score consensus | 1208 | 24 160 | 20 B |
| mode confirmation | 1208 | 19 328 | 16 B |

11 event-triggered epochs, `n_keep_to_line = 6`, full agreement 0.909.

## 3. Controller capability — questions 4–8

| # | question | answer | evidence |
|---|---|---|---|
| 4 | Can the controller execute KEEP? | **Yes** | crossing 0.833, collision-free 0.972, goal 0.833 |
| 5 | Can it execute LINE? | **Yes** | crossing 0.889, collision-free **1.000**, goal **1.000** |
| 6 | Can it execute KEEP → LINE? | **Yes** | scripted arm crosses 1.000; geometric arm 0.972 with a real epoch |
| 7 | Can it execute LINE → KEEP? | **Commanded yes, achieved no** | see §4 |
| 8 | Can it complete KEEP → LINE → KEEP? | **No** | `keep_recovered = 0.000` in every arm |

## 4. All five arms (validation, 36 episodes each)

| arm | full success | crossed | **recovered** | goal | collision-free | time in line |
|---|---|---|---|---|---|---|
| 1 always keep | 0.000 | 0.833 | **0.000** | 0.833 | 0.972 | 0.00 |
| 2 always line | 0.000 | 0.889 | **0.000** | 1.000 | 1.000 | 1.00 |
| 3 scripted K→L→K | 0.000 | **1.000** | **0.000** | 0.917 | 0.972 | 0.46 |
| 4 scripted K→L, no recovery | 0.000 | 0.889 | **0.000** | 0.944 | 0.972 | 0.69 |
| 5 geometric event-triggered | 0.000 | 0.972 | **0.000** | 0.917 | 0.944 | 0.28 |

Navigation is clearly separated from formation reconfiguration, as Task 4A
requires: **always-line navigates best of all** (goal 1.000, collision-free
1.000) and still scores 0.000 on full reconfiguration. That part of the V2
design works exactly as intended — line gets you through and does not finish
the mission.

## 5. The metric defect (Task 4A)

`keep_recovered = 0.000` for **always-keep**, which never leaves keep. A policy
that is in the nominal formation for the entire episode cannot fail to recover
it. That is a metric failure, not a controller failure, and it invalidates the
recovery column for every arm.

Measured on an open field, N=6, always-keep:

| criterion | at spawn | min | median | tolerance |
|---|---|---|---|---|
| `E_keep` max-over-pairs (my Task-2 definition) | **3.018** | 0.435 | **0.861** | 0.55 |
| max per-robot error vs centroid template (established convention) | — | 0.228 | **0.435** | 0.55 |

Two distinct problems:

1. **The tolerance is not commensurable.** A pairwise error accumulates two
   robots' deviations, so max-over-pairs at 0.55 m is roughly twice as strict as
   the per-robot convention `formation_tolerance = 0.55` was calibrated for.
   Under the established convention the controller **is** in the keep tube
   (median 0.435 < 0.55); under mine it is not (median 0.861).
2. **The swarm does not spawn in the role template.** `E_keep = 3.018 m` at
   step 0, and `initial_keep_valid = 0.0`. The scenario's initial formation and
   `RoleAssignment`'s keep template are different configurations, so "return to
   nominal" is being scored against a formation the episode never started in.

**I am not fixing this by raising the tolerance.** Doubling it to `2·ε_form`
would break the disjointness proof that the whole task rests on: `𝒦 ∩ ℒ = ∅`
requires `max‖d_keep − d_line‖ > 2·tol_pairwise`, and at N=4 the measured
2.012 m would fail a 2.20 m threshold. The keep and line sets would overlap and
always-line could satisfy the mission by accident — reintroducing exactly the
vacuity that V2 exists to remove. Any repair must keep the disjointness proof
intact, and must be made **before** the arms are re-run, not after seeing which
tolerance favours which policy.

## 6. Forced transition probes (Task 4B)

Corridor families only, 20 episodes each.

| probe | full | crossed | recovered | collision-free | RMS after crossing |
|---|---|---|---|---|---|
| A keep from start | 0.000 | 0.700 | 0.000 | 0.950 | 1.162 |
| B line from start | 0.000 | **1.000** | 0.000 | **1.000** | 3.857 |
| C K→L at valid entry | 0.000 | **1.000** | 0.000 | 0.950 | 3.691 |
| D L→K after exit | 0.000 | **1.000** | 0.000 | 0.950 | **2.684** |
| E K→L too late | 0.000 | 0.750 | 0.000 | 1.000 | 2.014 |
| F L→K too early | 0.000 | 0.600 | 0.000 | 0.950 | 1.790 |

What the probes localise:

- **Not physical infeasibility.** C and D cross 1.000 of the time.
- **Not communication disagreement.** These are scripted probes with no epoch.
- **Timing matters and behaves sensibly.** E (switch too late) drops crossing to
  0.750; F (recover too early) drops it to 0.600 — recovering inside the
  corridor makes the team too wide to finish passing. Both degrade in the
  direction the task predicts, which is evidence the state machine's timing
  requirements are real.
- **D is the informative one.** Commanded back to KEEP after the exit plane, the
  team's post-crossing keep error settles at **2.684 m** versus always-keep's
  1.162 m. So the controller does pull back toward keep (3.857 → 2.684 from
  probe B) but converges to roughly twice the error it holds when it never left.
  Whether the residual is a controller convergence limit or the un-calibrated
  metric cannot be separated until §5 is repaired.

## 7. Answers to questions 9

**Is final keep recovery physically achievable?** *Not yet demonstrated, and not
yet refuted.* Probe D shows partial convergence toward keep after the exit, and
the recovery region in the current validation layouts was never designed to the
`W_req^keep(N) = 3.26 m` requirement of TASK_V2 §3 — these are the *old*
layouts, reused because Task 4 forbids building the new families. A negative
result on layouts that were not built for the task is weak evidence.

## 8. Required before Task 5

1. **Repair the formation-set definition** in TASK_V2 §2, preserving the
   disjointness proof. State the corrected criterion and its tolerance before
   re-running any arm.
2. **Reconcile the spawn formation with the keep template**, or define the
   nominal set relative to the achievable steady state rather than the raw
   template.
3. Re-run Task 4 on the repaired metric. Only then is the "is recovery
   mechanically achievable" question answerable.
4. The scenario families of Task 5 must include a downstream recovery region
   sized to `W_req^keep(N)`, which no current validation layout guarantees.

## 9. Scope

Seed 0 equivalent, 36 episodes per arm, 20 per probe, validation only. No
learned selector was trained, loaded, or evaluated. No final-test layout was
accessed. No robustness or superiority claim is made.
