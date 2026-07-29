# Recovery and Headroom Gate V2 — Decision Report (Task 10)

Branch `research/recovery-event-v2`, from tag `scenario-headroom-v1-invalid-recovery-label`.
**No multi-seed pilot run. No learned model trained for comparison. Manuscript
untouched. Final-test layouts never loaded. No definition tuned against final-test
outcomes.**

Supporting: [`RECOVERY_EVENT_V2_DEFINITION.md`](RECOVERY_EVENT_V2_DEFINITION.md) ·
[`RECOVERY_EVENT_V2_SENSITIVITY_REPORT.md`](RECOVERY_EVENT_V2_SENSITIVITY_REPORT.md) ·
[`SCENARIO_HEADROOM_V2_REPORT.md`](SCENARIO_HEADROOM_V2_REPORT.md) ·
[`SPLIT_MODE_VALIDATION.md`](SPLIT_MODE_VALIDATION.md) ·
[`../results/legacy_recovery_event_v1/README.md`](../results/legacy_recovery_event_v1/README.md)

---

## 1. Does Recovery Event V2 reject provably infeasible rollouts?

**Yes, absolutely — 0.000 at all ten sensitivity grid points**, against V1's
**0.278**. In `infeasible` corridors (0.80–0.95 m, below the 1.10 m minimum for a
single robot centre) the headroom study now finds **zero qualified decision
states**, down from 35 under V1.

The rejection is geometric, not a tuned threshold: `crossed_exit` requires the
centroid past a plane beyond every obstacle of the constricting structure.

## 2. Is the event stable under reasonable parameter changes?

**Yes.** Label agreement is **0.908–0.992** (Cohen's κ 0.811–0.984) across
commitment window, horizon, tube tolerance, dwell and perturbation.

One exclusion: `T_max = 60` (agreement 0.712) is a horizon **shorter than the
task** — traversing 9.1 m at 0.135 m/step needs ≈ 68 steps at the speed limit with
no obstacles. That was derivable before the run and is not threshold-shopping.

**One gate fails and is reported as failing:** open-field false-negative rate
**0.104** against a ≤ 0.10 threshold. Neither the threshold nor the default
parameters were changed to make it pass.

## 3. Does a short-horizon surrogate predict full-horizon task recovery?

**Yes — but not the one currently in use.**

| surrogate | AUROC | Kendall τ |
|---|---|---|
| `formation_recovery` | **0.925** | **0.929** |
| `crossed_bottleneck` | 0.744 | 0.524 |
| `min_clearance` (geometric baseline) | **0.714** | 0.000 |
| **`shaped_rollout_utility`** *(current learned target)* | **0.704** | 0.357 |

**The shaped rollout utility does not beat a one-line geometric baseline.** Per
Task 7's own retention rule it **must be removed as the central target**.

This explains the Method Audit's AUROC 0.808: that was measured against the V1
label, which was itself shaped-utility-like. The score was predicting its target's
idiosyncrasies, not recovery.

## 4. Does always-keep still dominate?

**Less than V1 claimed.** Pooled keep-best share falls **0.823 → 0.690**, now
under the ≤ 0.70 criterion (**C1 passes**). In `keep_line_keep`, keep is best in
only **22.2 %** of qualified states.

## 5. Is line genuinely necessary in some families?

**Yes.** Line-best share rises **0.081 → 0.310** pooled (**C2 passes**, threshold
0.15), reaching **0.778** in `keep_line_keep` and **0.500** in `line_corridor`.
Keep-regret is **0.741** and **0.500** in those families.

Deterministic confirmation from Task 8: `line_corridor` N=6 has keep crossing the
gate but stalling (max x 1.86, goal 0.00) while line completes (4.07, goal 1.00).

## 6. Is split genuinely necessary and mechanically feasible?

**No, on both counts.**

- **Never oracle-best in any family — 0.000 everywhere**, including the two
  families built for it.
- **Never reaches the goal** in any deterministic run, at any team size.
- **Never strictly beats keep on crossing:** 0 wins, 14 losses, 14 ties.
- **The template is infeasible at its own compression floor**: lane offset
  0.450 m against a 0.55 m obstacle bound (**−0.100 m**), and only +0.100 m margin
  at nominal scale versus 0.135 m of travel per control step.
- **There is no merge behaviour** — split crosses and then stalls.

## 7. Does a per-decision oracle materially outperform always-keep?

**No, pooled: 0.033 against a ≥ 0.10 criterion (C5 fails).** In the two corridor
families it reaches **0.111** and **0.083**; it is exactly 0.000 in the other five.

## 8. Are actual mode transitions required?

**No. Switch necessity is 0.000 in every family.** V1's 0.250 in `split_around`
was an artifact of the broken label. **C7 fails.**

A *per-episode* or *per-decision* mode choice suffices; a **switching** controller
is not justified by any evidence here.

## 9. What should the final method contain?

**Keep/line only — a binary formation-mode selector, with no switching claim.**

- `split`: removed (§6).
- Discrete keep/line: retained — C1 and C2 now pass and keep-regret is 0.5–0.74 in
  the corridor families.
- Continuous formation scale: still un-ablated (the environment confound noted in
  the Method Audit is unresolved) — neither justified nor excluded.
- Topology *switching*: not justified (§8).

## 10. Is recovery ranking still the strongest scientific direction?

**Yes — but only with a different target than the one in the code.**

The gold-standard event is now sound, and there is a short-horizon surrogate that
tracks it well (`formation_recovery`, AUROC 0.925). What is *not* sound is the
quantity the model currently learns: the shaped rollout utility, which loses to
minimum clearance.

Justified claim today:

> Under a full-horizon task-recovery label that provably rejects infeasible
> geometry, a binary keep/line formation-mode decision has measurable headroom
> (line is oracle-best in 31 % of qualified decision states, 78 % in corridor
> transition layouts), and formation recovery over a short commitment window
> predicts full-horizon task recovery with AUROC 0.925.

---

## Final recommendation

> ### **C — Keep/line headroom exists. Simplify to binary formation-mode selection and proceed to a three-seed pilot** — with the three scope conditions below, which are not optional.

**Why C and not B** ("recovery meaningful but discrete headroom absent"): discrete
headroom is *not* absent. C1 (0.690 ≤ 0.70) and C2 (0.310 ≥ 0.15) both **pass**
against thresholds fixed before any of this was measured, and keep-regret is
0.741/0.500 in the corridor families. Declaring headroom absent would understate
the evidence as badly as V1 overstated split.

**Why not D**: split is removed on four independent grounds (§6).

**Why not A or F**: the event rejects infeasible geometry absolutely and is stable
at κ 0.811–0.984. Neither the event nor the simulator is the blocker any more.

**Why not E** (continuous only): line is oracle-best in 31 % of qualified states
and completes corridors where keep stalls. A continuous scale parameter has not
been shown to substitute for that, and its own ablation remains confounded.

### The three binding scope conditions

1. **The training target must change.** The shaped rollout utility fails Task 7's
   retention rule (AUROC 0.704 < 0.714 for minimum clearance). The pilot must
   train on the **binary task-recovery event** with a proper scoring rule, or on
   `formation_recovery` as its validated surrogate. Running the pilot against the
   existing target would repeat the Method Audit's error.
2. **No switching claim.** C7 fails at 0.000 — no episode requires a transition.
   The pilot evaluates a *mode chooser*, not a switching controller, and the paper
   must not describe transitions as necessary.
3. **Scope to where headroom exists.** `line_corridor` and `keep_line_keep` are the
   informative families; `keep_open` and `ambiguous` enter as controls only.
   `split_around` and `keep_split_merge` lose their purpose once split is removed
   and should be rebuilt as keep-vs-line obstacle scenarios or dropped.

### Honest statement of what still fails

**C5 (oracle advantage 0.033 pooled vs ≥ 0.10) and C7 (switch necessity 0.000)
both fail, and I am not lowering either threshold.** C5 is dominated by five
families with no headroom by design or by the removed split mechanism; in the two
families that matter it is 0.083–0.111. C7's failure is what condition 2 above
enforces.

A reviewer could reasonably read C5's pooled failure as grounds for **B** instead.
The case for C is that the criterion which most directly measures *mode-selection
headroom* — C1 and C2, the mode-diversity criteria — now pass, and they failed
under V1. The case against is that episode-level payoff remains small. Both
readings are in the data above; C is chosen because the decision-state evidence is
strong and the episode-level dilution is explained by families that were never
meant to have headroom.

### Compliance

| Condition | Status |
|---|---|
| No multi-seed pilot | ✓ |
| No learned model trained for performance comparison | ✓ — oracle-only throughout |
| Manuscript untouched | ✓ |
| Final-test layouts unchanged and never loaded | ✓ |
| No definition tuned using final-test outcomes | ✓ |
| V1 outputs preserved, not deleted | ✓ — `results/legacy_recovery_event_v1/` |
| Thresholds not lowered after seeing results | ✓ — C3, C5, C7 reported as failing |

**Stopping here for approval.**
