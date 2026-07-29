# Scenario and Model Gate Report (Task 10)

Branch `research/scenario-headroom-v1`, from tag `method-audit-v2-complete`.
Evaluation Protocol V2 semantics unchanged. **No final-test layout was loaded,
measured, or examined.** No manuscript file touched. No performance-superiority
claim.

Supporting: [`SIMPLIFIED_MODEL_SPECIFICATION.md`](SIMPLIFIED_MODEL_SPECIFICATION.md) ·
[`MODE_HEADROOM_DEFINITION.md`](MODE_HEADROOM_DEFINITION.md) ·
[`SCENARIO_FAMILY_SPECIFICATION.md`](SCENARIO_FAMILY_SPECIFICATION.md) ·
[`LAYOUT_SPLIT_PROTOCOL.md`](LAYOUT_SPLIT_PROTOCOL.md) ·
[`SCENARIO_HEADROOM_REPORT.md`](SCENARIO_HEADROOM_REPORT.md) ·
[`RECOVERY_EVENT_SPECIFICATION.md`](RECOVERY_EVENT_SPECIFICATION.md) ·
[`CHECKPOINT_SELECTION_V2.md`](CHECKPOINT_SELECTION_V2.md) ·
[`BASELINE_FIDELITY_V3.md`](BASELINE_FIDELITY_V3.md)

---

## 1. Is there enough mode diversity to study mode selection?

**No, pooled — and only marginally in three families.**

`keep` is oracle-best in **82.3 %** of qualified states against a ≤ 70 % criterion.
`line` reaches 8.1 % (needs 15 %), `split` 9.6 % (needs 10 %). C1, C2 and C3 all
fail pooled.

Per family, only **`keep_line_keep`** passes C1 (keep 0.615, line 0.308).
`line_corridor` (line 0.131) and `split_around` (split 0.089) are close but under.

## 2. Does the rollout oracle materially outperform always-keep?

**No, pooled: +0.058 against a +0.10 criterion (C5 fails).**

Per family: `split_around` **+0.188** ✓, `line_corridor` **+0.125** ✓,
`keep_line_keep` +0.062 ✗, and **exactly 0.000** in `keep_open`, `ambiguous`,
`keep_split_merge` and `infeasible`.

So headroom exists in two of seven families and nowhere else.

## 3. Are line and split ever *necessary*, not merely slightly better?

**Rarely.** Pooled mode necessity — a non-keep mode turning a failing rollout into
a recovering one — is **0.174**. Concentrated in `keep_line_keep` (0.365) and
`line_corridor` (0.230); ≤ 0.133 everywhere else.

**`split` is the weaker of the two.** In `split_around`, the family built so that
only `split` is geometrically admissible, `split` is oracle-best in just **8.9 %**
of states. The measurement contradicts the geometric hypothesis, and per
`SCENARIO_FAMILY_SPECIFICATION.md` the measurement wins: the fixed 1.30 m lane gap
appears too narrow for splitting to pay, so `keep` squeezes past instead.

## 4. Are topology transitions necessary in any episode family?

**In one, weakly.** `switch_necessity` is **0.250** in `split_around` and **0.000**
in all six other families; pooled 0.033. The oracle makes 1.63 switches per
episode on average.

C7 passes on its literal wording ("> 0 in at least one family"), but one family at
0.25 is a thin basis for a paper about switching.

## 5. Is the binary recovery event stable and meaningful?

**No — it fails two of its own predeclared criteria.**

| Rule | Threshold | Measured | |
|---|---|---|---|
| S3 label stability | ≥ 0.80 | **0.749** (H 14→28) | FAIL |
| S5 infeasible sanity | ≤ 0.05 | **0.278** | FAIL |

S5 is the serious one. In corridors **0.80–0.95 m wide** — below the 1.10 m
minimum for a single robot to pass, where every policy scores **0.000 episode
success** — 27.8 % of rollouts are labelled *recovered*. The horizon-14 event asks
only for 0.02 progress and 3 consecutive in-tube steps, which a team can satisfy
while approaching a wall it will never pass.

**The event is local and does not reflect episode feasibility.** Every state-level
label in this report inherits that weakness.

## 6. Is the simplified model specification scientifically defensible?

**Yes.** Two heads, two loss terms, one argmax. 402,183 parameters (−14.0 % vs
legacy), 5 loss terms and 12 selector decision levels removed. Every removal cites
Method-Audit-v2 evidence, and 14 tests assert the removed components cannot
influence it — including that `selector_mode`, `min_dwell_steps` and
`use_uncertainty_adjustment` are all no-ops for it.

The legacy model is untouched and still available as `rvt_full_legacy`.

## 7. Is checkpoint selection stable enough for multi-seed evaluation?

**Partly.** The pathology is gone: at 40 validation episodes the criteria agree on
direction and success rises monotonically with training (0.075 → 0.600). No repeat
of epoch-5-over-epoch-60.

But **closed-loop success is still only 47 % stable** under a 400-draw bootstrap,
with 3 distinct winners. Ranking accuracy is monotone and consistent (spread
0.043) and is adopted as the primary criterion, per the task's alignment rule.

Adequate for a ranking-primary pilot. **Not** adequate if closed-loop success is
the primary criterion.

## 8. Which scenario families should enter the pilot?

| Enter | Why |
|---|---|
| `keep_line_keep` | only family passing C1; highest headroom (0.361) and necessity (0.365) |
| `line_corridor` | oracle advantage 0.125, margin 1.000, clearest single-mode signal |
| `split_around` | largest oracle advantage (0.188); only family with non-zero switch necessity |
| `keep_open` | **control only** — confirms keep-dominance is detected, never evidence |
| `ambiguous` | **control only** — confirms ties are detected |

## 9. Which should be excluded?

| Exclude | Why |
|---|---|
| `keep_split_merge` | designed to force splitting; keep dominates 0.911, oracle advantage **0.000**, margin 0.000. The blocker does not force a split |
| `infeasible` (state-level) | 27.8 % false-recovered labels. Its **episode-level** result (0.000 success for all policies) is valid and retained as a sanity check |

## 10. What central claim is now justified?

**None involving topology control, and none about recovery yet.**

What the evidence supports, stated narrowly:

> In a formation-navigation benchmark with explicitly disjoint layout splits, mode
> selection headroom is small and concentrated: a fixed `keep` policy is oracle-best
> in 82 % of qualified decision states, and a per-decision rollout oracle improves
> episode success over always-`keep` by 0.058 pooled — reaching 0.125–0.188 only in
> corridor and central-obstacle geometries.

That is a **benchmark characterisation**, not a method result. It is publishable as
methodology, not as a topology-control contribution.

---

## Final recommendation

> ### **E — The benchmark remains invalid; repair it before further work.**

This is a stronger conclusion than the alternatives, and I want to be explicit
about why the softer readings were rejected.

**Not A** ("no headroom — abandon topology selection"): headroom is small but
real. `split_around` shows +0.188 oracle advantage and 0.25 switch necessity;
`keep_line_keep` shows 0.308 line-preference and 0.361 headroom. Abandoning the
idea would overstate the evidence in the opposite direction.

**Not B** ("headroom for line or split only — narrow the claims"): tempting, since
`line` is clearly the stronger of the two. But narrowing the claims now would build
on state-level labels produced by an event that mislabels **27.8 %** of rollouts in
provably impassable corridors. The labels are not yet trustworthy enough to narrow
*toward*.

**Not C or D** ("proceed to a three-seed pilot"): both require the measurement
instrument to be sound. It is not. A pilot run now would produce numbers whose
central quantity — the recovery label — is known to fire in geometry where nothing
can recover.

**E** is the honest reading: three of seven families carry usable signal, four of
seven qualification criteria fail, and the recovery event fails two of its own
predeclared rules. The instrument must be repaired before it measures anything.

### Repairs required before re-qualification

1. **Make the recovery event non-local.** It must reflect episode feasibility.
   Options: require progress toward the goal *past the constriction*; extend H to
   cover the passage; or add a reachability precondition. Re-run the S1–S5 check
   afterwards — S5 is the acceptance test.
2. **Fix the horizon sensitivity** (S3, 0.749). H is the unstable axis; either
   justify a single H physically or report results across H.
3. **Repair or drop `keep_split_merge`.** Widen the blocker until `keep` genuinely
   cannot pass, and re-measure.
4. **Investigate the `split` template's 1.30 m lane gap.** The split-favourable
   family did not favour split. Either the template cannot express the manoeuvre or
   the geometry does not demand it — decide this on rollout evidence, never by
   tuning toward a target result.
5. **Then re-run qualification** against the *unchanged* C1–C7 thresholds.

### Compliance

| Condition | Status |
|---|---|
| Branch `research/scenario-headroom-v1` from `method-audit-v2-complete` | ✓ |
| Protocol V2 semantics unchanged | ✓ — `layout=None` reproduces prior behaviour exactly |
| No final-test results used for scenario design or architecture selection | ✓ — test layouts never loaded |
| Manuscript untouched | ✓ |
| No performance-superiority claim | ✓ — no learned model in qualification at all |
| Three-seed pilot not run | ✓ |
| Thresholds not revised after seeing results | ✓ — four criteria are reported as failing |

**Stopping here for approval.**
