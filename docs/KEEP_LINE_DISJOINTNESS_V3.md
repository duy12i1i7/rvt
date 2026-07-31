# KEEP / LINE Disjointness under the V3 Metric

Tests `tests/test_keep_line_disjointness_v3.py` (14)

---

## 1. Result

> ### N = 6 is separated. **N = 3 and N = 4 are NOT**, and must be excluded from the reconfiguration study.

```
delta_N = max_i || r_i^KEEP - r_i^LINE ||     (centred templates, shared frame)
condition:  delta_N > 2 * epsilon_form = 1.10 m
```

| N | `delta_N` | > 1.10? | per-robot gaps |
|---|---|---|---|
| 3 | **0.6708** | **NO** | 0.671, 0.671, 0.424 |
| 4 | **1.0062** | **NO** | 1.006, 0.450, 0.450, 1.006 |
| 6 | **2.0125** | **YES** | 2.012, 0.900, 0.900, 0.900, 0.900, 2.012 |

## 2. The condition is necessary and sufficient

Not merely a bound.

**(⇒)** If a configuration `X` is in both tubes, then for every `i`,
`||(p_i - c) - R r_i^K|| <= eps` and `||(p_i - c) - R r_i^L|| <= eps`. The
triangle inequality gives `||r_i^K - r_i^L|| <= 2 eps` for all `i`, hence
`delta_N <= 2 eps`.

**(⇐)** If `delta_N <= 2 eps`, the explicit **midpoint configuration**

```
p_i - c = R (r_i^K + r_i^L) / 2
```

lies in both tubes: each error is `||r_i^K - r_i^L|| / 2 <= delta_N / 2 <= eps`.
It is a legitimate configuration because both centred templates sum to zero, so
the offsets do too (asserted to 1e-9 in the tests).

So a failure is **certified by construction**, not inferred from a missed
threshold. `test_unseparated_sizes_admit_a_configuration_in_BOTH_tubes` builds
that configuration for N = 3 and N = 4 and asserts `in_keep_tube` and
`in_line_tube` are simultaneously true.

## 3. Consequence

At N = 3 and N = 4 a swarm can be in the KEEP tube and the LINE tube at the same
instant. `always_line` could therefore satisfy the nominal-recovery requirement
without ever leaving line — reintroducing exactly the vacuity that the V2 task
was designed to remove, since the whole task rests on line being unable to
finish the mission.

Per the Task 4R-2 rule, epsilon is **not** adjusted in either direction. N = 3
and N = 4 are excluded from the reconfiguration experiment, and every N = 4
result in the preserved Task 4 run is invalid for reconfiguration purposes
independently of the metric repair.

**The reconfiguration study proceeds at N = 6 only.**

## 4. Why N = 6 separates and N = 4 does not

The gap is driven by the *end* robots, which must travel furthest between the
grid and the file. At N = 4 the keep grid is 2×2 and the line is 4 long, so the
extreme role moves `(0.9, 0.45)` → 1.006 m. At N = 6 the grid is 3×2 and the
line is 6 long, so the extreme role moves 2.012 m. The separation grows with N
because the line template lengthens faster than the grid widens.

A team of 4 simply does not have to rearrange far enough for the two formations
to be distinguishable at a 0.55 m tolerance.
