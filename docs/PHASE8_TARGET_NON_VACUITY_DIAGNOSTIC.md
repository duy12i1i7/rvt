# Phase 8 Target Non-Vacuity Diagnostic

## Frozen Budget

The diagnostic used exactly eight decision events: F1, F2, F6 and F10 from
train and validation. It executed 16 matched candidate diagnostic traces and 16
robot-local residual-target fixtures. No final-test layout, scientific dataset,
model training or DAgger state was used.

## Recoverability Result

| statistic | COMPACT | LINE |
|---|---:|---:|
| positive | 4 | 4 |
| negative | 4 | 4 |

Joint outcomes were two COMPACT-only, two LINE-only, two both-success and two
both-fail events. Invalid rollouts: 0. Unstable targets: 0. Matched-rollout
issues: 0. Average diagnostic cost was 716.75 control steps per candidate.

These traces exercise the complete V4 condition evaluator using predeclared
train/validation headroom fixtures. They verify target non-vacuity and matching,
not full closed-loop qualification of all 40 layouts and not learned
performance.

## Residual Result

Expert source was
`B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1`. All 16 targets were finite,
within the 0.15 m/s2 component bounds and safety-compatible. Twelve were
non-zero (0.75), four saturated a declared component bound (0.25), and both
candidates and committed topologies were represented 8/8. The fixture set
contained eight COMPACT-to-LINE and eight LINE-to-COMPACT local contexts. Five
persistent role IDs were represented. Maximum residual magnitude was
0.15 m/s2.

The diagnostic passes the frozen anti-vacuity gates. It does not establish H4;
that requires paired validation closed-loop value after training.

## Scope Counters

- scientific dataset generated: false;
- model training runs: 0;
- DAgger rounds: 0;
- final-test runtime accesses: 0.
