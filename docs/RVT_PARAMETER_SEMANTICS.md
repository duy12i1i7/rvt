# RVT Parameter Semantics

## 1. Conventions

All physical source values use SI units. Step and round counts use ceiling
conversion so configured physical time is not shortened. Derived values are
versioned by `rvt-runtime-derivations/v1`.

For any time `T >= 0` and positive period `P`:

```text
steps(T, P) = ceil(T / P).
```

Floating-point equality near an exact period boundary uses a fixed `1e-12`
ceiling tolerance. Negative/nonfinite time and nonpositive/nonfinite periods
are invalid.

## 2. Time-domain derivations

| Quantity | Exact meaning | Formula | Source parameters and units | Validity assumptions | Valid range/boundary behavior |
|---|---|---|---|---|---|
| `recovery_dwell_steps` | Consecutive control samples required for KEEP recovery | `ceil(recovery_dwell_seconds / control_period_seconds)` | s / s | Control clock follows declared period | Integer `>=0`; zero duration gives zero; nominal `3.0/0.15=20` |
| `commitment_steps` | Control samples for which a committed mode remains locked | `ceil(commitment_seconds / control_period_seconds)` | s / s | Lock is updated once per control period | Integer `>=0`; nominal `1.5/0.15=10` |
| `evidence_persistence_steps` | Control samples of continuous local evidence | `ceil(evidence_persistence_seconds / control_period_seconds)` | s / s | Evidence predicate runs once per control sample | Integer `>=0`; nominal `0.45/0.15=3` |
| `event_collection_rounds` | Communication rounds allocated to event collection | `ceil(event_collection_seconds / communication_period_seconds)` | s / s | Collection is communication-clocked | Integer `>=0`; nominal zero remains zero |
| `message_stale_rounds` | Maximum age represented on the communication clock | `ceil(maximum_message_age_seconds / communication_period_seconds)` | s / s | Message timestamps advance by communication rounds | Integer `>=0`; nominal `3`; changing only control frequency has no effect |
| `message_delay_bound_rounds` | Upper bound on accepted delivery delay | `ceil(maximum_message_delay_seconds / communication_period_seconds)` | s / s | Delay is bounded as declared | Integer `>=0`; nominal zero |
| `rearm_inactive_steps` | Inactive control samples before a completed event may rearm | `ceil(rearm_inactive_seconds / control_period_seconds)` | s / s | Latch checked once per control sample | Integer `>=0`; nominal `3.75/0.15=25` |
| `decision_reference_steps` | Physical reference horizon used for lifecycle feature normalization | `ceil(decision_reference_seconds / control_period_seconds)` | s / s | Not a centralized forced cadence | Integer `>=0`; nominal `25` |
| `progress_window_steps` | Own-odometry history used for local progress | `ceil(progress_window_seconds / control_period_seconds)` | s / s | Own history sampled on control clock | Integer `>=1` by config validation; nominal `0.75/0.15=5` |

The repaired message-age formula intentionally uses communication period. The
old implementation used control period and was correct only while both periods
were equal.

## 3. Formation and clearance derivations

| Quantity | Exact meaning | Formula | Source parameters and units | Validity assumptions | Valid range/boundary behavior |
|---|---|---|---|---|---|
| `formation_tolerance_meters` | Metric V3 and local diagnostic tolerance at configured spacing | `formation_tolerance_ratio * nominal_spacing_meters` | dimensionless * m | Ratio semantics remain fixed | `>0`; nominal `(11/18)*0.9=0.55 m` |
| `robot_obstacle_required_clearance_meters` | Required robot-center to represented obstacle-center distance | `robot_radius_meters + obstacle_clearance_margin_meters` | m + m | Margin includes represented obstacle footprint (`0.35 m`) and surface margin (`0.02 m`) | `> robot_radius`; nominal `0.18+0.37=0.55 m` |
| `robot_robot_required_clearance_meters` | Required center distance for two robots | `2*robot_radius_meters + inter_robot_safety_margin_meters` | m | Identical radius model | `>=2r`; nominal `0.36+0.04=0.40 m` |
| `minimum_formation_scale` | Smallest legacy scale whose commanded spacing clears robot clearance plus spacing margin | `clip((required_rr + spacing_margin)/nominal_spacing, 0, 1)` | m/m | Used only by preserved legacy adaptive scale | `[0,1]`; spacing below clearance is unsupported rather than made safe by clipping |

Decimal clearance sums are normalized to 12 decimal places for stable hashes;
this removes binary representation noise and does not change physical
precision.

## 4. Communication and propagation derivations

Let:

```text
D_component = declared_maximum_component_diameter_hops
              if declared,
              otherwise maximum_team_size - 1
B_delay = ceil(maximum_message_delay_seconds /
               communication_period_seconds)
D_causal = D_component * (B_delay + 1)
```

| Quantity | Exact meaning | Formula/constraint | Sources | Validity assumptions | Range/boundary behavior |
|---|---|---|---|---|---|
| `component_diameter_bound_hops` | Longest shortest path admitted by the topology contract | Explicit bound or `N_max-1` | hops/count | Connected component satisfies declared bound | `0..N_max-1`; N=1 has zero |
| `causal_propagation_round_bound` | Conservative rounds for diameter propagation under whole-round delay | `D_component*(B_delay+1)` | hops, delay rounds | Bounded delivery and per-round processing | `>=D_component`; nominal delay gives equality |
| `k_intent_rounds` | Intent/token propagation budget | derived `D_causal` or explicit value `>=D_causal` | rounds | Current trigger mechanism propagates one hop per effective round | Insufficient explicit value raises `insufficient_rounds` |
| `k_score_rounds` | Score-consensus communication budget | same validation | rounds | Phase 2 contract requires diameter coverage; this is not a finite exact-average theorem | Nominal corrected from `4` to `5` |
| `k_ready_rounds` | Future readiness propagation budget | same validation | rounds | Configuration only until Phase 7 | Never executed by current base |
| `k_confirm_rounds` | Confirmation min/max propagation budget | same validation | rounds | One-hop propagation | Nominal `5` |

Path, ring, star, and complete fixture diameters are respectively `N-1`,
`floor(N/2)`, `1 or 2`, and `1` for `N>1`. These are mechanical communication
fixtures, not Phase 3 formation topologies.

## 5. Role-specific transition observation

For robot role `i`, source topology `s`, and target topology `t`:

```text
W_i(s -> t) =
    abs(lateral(r_i^t) - lateral(r_i^s))
    + robot_obstacle_required_clearance_meters
    + transition_response_lateral_bound_meters
    + protocol_lateral_drift_bound_meters
    + transition_observation_margin_meters.
```

Meaning: the local forward sector must cover the complete prospective lateral
role displacement plus declared geometry, controller-response, protocol-drift,
and additional safety envelopes.

Sources are role-template coordinates (m), robot geometry/clearance (m),
controller response bound (m), protocol-latency lateral drift bound (m), and
transition margin (m). All terms must be finite and nonnegative except signed
role coordinates, whose difference is absolute.

The frozen current detector declares both additional response bounds as
`0.0 m`, reproducing the approved role geometry: about `0.55 m` for center and
`1.45 m` for outer N=6 roles. This is an explicit assumption, not a readiness
certificate. A configuration is unsupported when any `W_i > R_obs`; it is not
silently clipped.

## 6. Longitudinal lookahead

At local speed `v` within `[0, v_max]`:

```text
braking_distance = v^2 / (2*a_max)
protocol_time = evidence_persistence_seconds
                + event_collection_seconds
                + k_intent_rounds * communication_period_seconds
required = braking_distance
           + v * protocol_time
           + transition_observation_margin_meters
lookahead_distance = min(R_obs, required)
```

Units are meters, meters/second, meters/second squared, and seconds. Validity
assumes the declared acceleration bound is available for braking, speed does
not exceed `v_max`, communication follows its bound, and the local sensor can
only act inside `R_obs`. Negative or over-limit speed is rejected. At zero
speed the motion terms vanish. The sensor cap is reported as a cap, not proof
that every larger physical requirement is observable.

Nominal N=6 value remains `1.755 m`.

## 7. Explicit non-derived assumptions

The following remain explicit source assumptions because they cannot be
derived from geometry alone:

- maximum team size and any tighter component diameter;
- communication range, symmetry, packet-loss and delay bounds;
- temporary-disconnection policy;
- evidence, event-collection, commitment, rearm, and recovery physical times;
- confirmation margin and duplicate-sequence horizon;
- all frozen controller gains;
- transition response and protocol lateral drift bounds;
- shared frame and heading-alignment convention;
- model dimensions, attention slope, and feature schema.

Changing an assumption creates a new canonical hash and requires a new
manifest. No assumption is tuned automatically from closed-loop output.

## 8. Nominal compatibility values

| Derived quantity | Nominal result |
|---|---:|
| Formation tolerance | `0.55 m` |
| Robot-obstacle required clearance | `0.55 m` |
| Robot-robot required clearance | `0.40 m` |
| Recovery dwell | `20` control steps |
| Commitment | `10` control steps |
| Evidence persistence | `3` control steps |
| Message stale age | `3` communication rounds |
| Rearm inactive duration | `25` control steps |
| Progress window | `5` control steps |
| N=6 path diameter | `5` hops |
| `k_intent/k_score/k_ready/k_confirm` | `5/5/5/5` rounds |
| N=6 role widths | about `0.55/1.45 m` |
| N=6 lookahead | `1.755 m` |

Only `k_score` differs from the selected base default (`4 -> 5`) because the
old value violated the approved diameter contract. Unequal communication and
control periods now also produce corrected message-age semantics; nominal
equal periods are unchanged.

