# Topology Distinguishability Audit

## 1. Diagnostic

Templates are already centered and share persistent roles. For topology pair
`a,b` the role-aware distance is:

```text
delta_max(a,b) = max_i ||r_i^a - r_i^b||
delta_rms(a,b) = sqrt(mean_i ||r_i^a-r_i^b||^2)
normalized = delta_max / nominal_spacing.
```

This is invariant to global translation and the declared shared heading. Under
Metric V3's aligned per-role max tube, overlap is possible exactly when
`delta_max <= 2*epsilon_form`. Phase 3 preserves
`epsilon_form=0.55 m`, so the threshold is `1.10 m`.

## 2. Results

| N | Pair | Max distance | RMS distance | Normalized max | Threshold | Tube overlap | Mechanical eligibility |
|---:|---|---:|---:|---:|---:|---|---|
| 5 | KEEP / COMPACT | 1.538 | 1.018 | 1.709 | 1.100 | No | Yes |
| 5 | KEEP / LINE | 1.610 | 1.138 | 1.789 | 1.100 | No | Yes |
| 5 | COMPACT / LINE | 1.138 | 0.805 | 1.265 | 1.100 | No | Yes |
| 6 | KEEP / COMPACT | 1.423 | 0.972 | 1.581 | 1.100 | No | Yes |
| 6 | KEEP / LINE | 2.012 | 1.375 | 2.236 | 1.100 | No | Yes |
| 6 | COMPACT / LINE | 1.423 | 0.972 | 1.581 | 1.100 | No | Yes |
| 8 | KEEP / COMPACT | 1.501 | 0.886 | 1.668 | 1.100 | No | Yes |
| 8 | KEEP / LINE | 2.490 | 1.583 | 2.767 | 1.100 | No | Yes |
| 8 | COMPACT / LINE | 1.855 | 1.191 | 2.062 | 1.100 | No | Yes |
| 12 | KEEP / COMPACT | 1.622 | 1.246 | 1.803 | 1.100 | No | Yes |
| 12 | KEEP / LINE | 4.269 | 2.624 | 4.743 | 1.100 | No | Yes |
| 12 | COMPACT / LINE | 2.737 | 1.664 | 3.041 | 1.100 | No | Yes |
| 16 | KEEP / COMPACT | 2.012 | 1.423 | 2.236 | 1.100 | No | Yes |
| 16 | KEEP / LINE | 5.566 | 3.337 | 6.185 | 1.100 | No | Yes |
| 16 | COMPACT / LINE | 3.628 | 2.158 | 4.031 | 1.100 | No | Yes |
| 24 | KEEP / COMPACT | 3.468 | 2.307 | 3.853 | 1.100 | No | Yes |
| 24 | KEEP / LINE | 8.796 | 5.169 | 9.773 | 1.100 | No | Yes |
| 24 | COMPACT / LINE | 5.419 | 3.171 | 6.021 | 1.100 | No | Yes |

The narrowest margin is COMPACT/LINE at N=5:
`1.138-1.100=0.038 m`. It passes the frozen criterion without changing the
tolerance. This is a metric distinction result, not evidence that a controller
can execute the transition robustly.

## 3. Separate support claims

- **Algorithmic construction:** all 18 required N/topology cells construct.
- **Metric distinguishability:** all 18 pair cells have disjoint Metric V3 tubes.
- **Mechanical experimental eligibility:** all required cells meet clearance,
  graph, and sensor checks and may enter later forced-topology qualification.
- **Scientific validation:** none in Phase 3. COMPACT has not run closed loop.

An identical-template mutation is detected as both near-identical and
tube-overlapping. No topology pair is retained merely because it has a distinct
name.
