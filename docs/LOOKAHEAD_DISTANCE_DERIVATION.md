# Lookahead Distance Derivation (Task G5)

## The defect

`2.0 * nominal_spacing` in `runtime._robot_decision` conflated a **lookahead
distance** with the **formation pitch**. The factor 2.0 had no stated meaning,
and the same threshold logic already existed with a different value in
`TriggerThresholds`.

## The requirement is temporal, not geometric

A robot must notice a constriction early enough to (a) run the distributed
protocol to a commitment and (b) stop or deform before reaching it:

```
lookahead = min( R_obs,
                 v²/(2a)                       reaction (braking) distance
               + v · T_protocol                ground covered while the epoch runs
               + safety_margin )

T_protocol = (persistence + collection + k_trigger) · control_period
```

At the frozen configuration: braking `0.9²/(2·0.6) = 0.675 m`, protocol latency
`0.9 × 8 × 0.15 = 1.08 m`, total **1.755 m**, under `R_obs = 3.0 m`.

The old value was 1.800 m — numerically close, which is exactly why it survived
unexamined. It is now a consequence of speed, acceleration, sensor range and
protocol latency, and it moves when any of those move.
