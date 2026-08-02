# Phase 3 Topology Mechanical Report

## 1. Scope and provenance

Phase 3 started from approved Phase 2 commit
`37519253f2b92bca824d39729093f7427190f106`. It implements only the generic
topology registry and static mechanical formation geometry. No scientific
closed-loop episode, learned model, training job, scenario sweep, or final-test
layout was run or accessed.

The authoritative registry schema is `rvt-topology-registry/v1`. Stable primary
IDs are KEEP `0`, COMPACT `5`, and LINE `2`; scientific order is explicit and
does not depend on mapping iteration. ID `5` prevents legacy ID `1` from being
silently reinterpreted as COMPACT.

## 2. Authoritative definitions

- **KEEP:** centered square-like grid with
  `columns=max(2,ceil(sqrt(N)))`, row-major persistent-role placement, and
  horizontal/vertical lattice edges. It preserves the selected decentralized
  KEEP pairwise and Metric V3 semantics.
- **COMPACT:** centered two-column rectangular lattice, or one column only for
  the degenerate `N=1` construction. It has width `d`, length
  `(ceil(N/2)-1)d`, ladder edges, degree at most three, and the same pairwise
  controller law as KEEP/LINE. It is a reduced-footprint mechanical candidate,
  not a closed-loop claim.
- **LINE:** centered chain along the mission direction with offset
  `((rank-(N-1)/2)d,0)` and adjacent-rank edges. It preserves the selected
  decentralized LINE semantics.

All offsets use a centered template frame: `+x` is the longitudinal mission
direction and `+y` is lateral. Translation is applied only through the world
origin; rotation is derived only from the shared mission direction. No map or
corridor coordinate participates in role generation.

The two-column rectangular COMPACT design was selected over a staggered
triangular strip because it preserves the existing axis-aligned pairwise
controller geometry, keeps exact clearance `d`, has degree bounded by three,
and remains mechanically distinct from KEEP and LINE at every required team
size. The decision used no rollout performance.

## 3. Required mechanical matrix

Default declared values are nominal spacing `d=0.90 m`, Metric V3 tolerance
`epsilon_form=0.55 m`, and obstacle sensing range `R_obs=3.00 m`. `Min sep.` is
the smallest role-aware maximum separation from either other primary topology.
`Max move` is the largest static role displacement to either other topology.
`Obs.` is the largest required lateral observation extent for a transition to
either other topology.

| N | Topology | Built / unique | Width | Length | Min clearance | Avg degree | Max degree | Diameter | Min sep. | Max move | Obs. | Round trip |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5 | KEEP | Yes / Yes | 1.800 | 0.900 | 0.900 | 2.000 | 3 | 3 | 1.538 | 1.610 | 1.990 | Yes |
| 5 | COMPACT | Yes / Yes | 0.900 | 1.800 | 0.900 | 2.000 | 3 | 3 | 1.138 | 1.538 | 1.990 | Yes |
| 5 | LINE | Yes / Yes | 0.000 | 3.600 | 0.900 | 1.600 | 2 | 4 | 1.138 | 1.610 | 1.630 | Yes |
| 6 | KEEP | Yes / Yes | 1.800 | 0.900 | 0.900 | 2.333 | 3 | 3 | 1.423 | 2.012 | 1.900 | Yes |
| 6 | COMPACT | Yes / Yes | 0.900 | 1.800 | 0.900 | 2.333 | 3 | 3 | 1.423 | 1.423 | 1.900 | Yes |
| 6 | LINE | Yes / Yes | 0.000 | 4.500 | 0.900 | 1.667 | 2 | 5 | 1.423 | 2.012 | 1.450 | Yes |
| 8 | KEEP | Yes / Yes | 1.800 | 1.800 | 0.900 | 2.500 | 4 | 4 | 1.501 | 2.490 | 2.013 | Yes |
| 8 | COMPACT | Yes / Yes | 0.900 | 2.700 | 0.900 | 2.500 | 3 | 4 | 1.501 | 1.855 | 2.013 | Yes |
| 8 | LINE | Yes / Yes | 0.000 | 6.300 | 0.900 | 1.750 | 2 | 7 | 1.855 | 2.490 | 1.562 | Yes |
| 12 | KEEP | Yes / Yes | 2.700 | 1.800 | 0.900 | 2.833 | 4 | 5 | 1.622 | 4.269 | 1.900 | Yes |
| 12 | COMPACT | Yes / Yes | 0.900 | 4.500 | 0.900 | 2.667 | 3 | 6 | 1.622 | 2.737 | 1.450 | Yes |
| 12 | LINE | Yes / Yes | 0.000 | 9.900 | 0.900 | 1.833 | 2 | 11 | 2.737 | 4.269 | 1.900 | Yes |
| 16 | KEEP | Yes / Yes | 2.700 | 2.700 | 0.900 | 3.000 | 4 | 6 | 2.012 | 5.566 | 1.900 | Yes |
| 16 | COMPACT | Yes / Yes | 0.900 | 6.300 | 0.900 | 2.750 | 3 | 8 | 2.012 | 3.628 | 1.450 | Yes |
| 16 | LINE | Yes / Yes | 0.000 | 13.500 | 0.900 | 1.875 | 2 | 15 | 3.628 | 5.566 | 1.900 | Yes |
| 24 | KEEP | Yes / Yes | 3.600 | 3.600 | 0.900 | 3.167 | 4 | 8 | 3.468 | 8.796 | 2.875 | Yes |
| 24 | COMPACT | Yes / Yes | 0.900 | 9.900 | 0.900 | 2.833 | 3 | 12 | 3.468 | 5.419 | 2.875 | Yes |
| 24 | LINE | Yes / Yes | 0.000 | 20.700 | 0.900 | 1.917 | 2 | 23 | 5.419 | 8.796 | 2.425 | Yes |

All 18 required cells are supported. There are no rejected cells in the
declared matrix and no fallback was used. Explicit out-of-contract tests reject:

- a role-set/team-size mismatch with `role_count_mismatch`;
- spacing `0.30 m` with `nominal_clearance_violation`, retaining the requested
  spacing rather than clamping it;
- a team size above the declared maximum with `team_size_exceeds_maximum`;
- an insufficient sensing envelope with `sensor_envelope_unsupported`.

The same validity path passes the required spacing variants `0.72 m` and
`1.08 m`, robot radius variants `0.16 m` and `0.22 m`, translated and rotated
frames, and permuted input robot-key orderings.

## 4. Role tables

Coordinates are meters in the centered template frame. Persistent IDs remain
unchanged when topology changes. Incomplete KEEP/COMPACT rows follow the same
deterministic row-major rule and are centered afterward; they do not create a
leader role.

### N = 5

| Role | KEEP `(x,y)` | COMPACT `(x,y)` | LINE `(x,y)` |
|---|---:|---:|---:|
| role-0000 | (-0.360, 0.720) | (-0.720, 0.360) | (-1.800, 0.000) |
| role-0001 | (-0.360, -0.180) | (-0.720, -0.540) | (-0.900, 0.000) |
| role-0002 | (-0.360, -1.080) | (0.180, 0.360) | (0.000, 0.000) |
| role-0003 | (0.540, 0.720) | (0.180, -0.540) | (0.900, 0.000) |
| role-0004 | (0.540, -0.180) | (1.080, 0.360) | (1.800, 0.000) |

### N = 6

| Role | KEEP `(x,y)` | COMPACT `(x,y)` | LINE `(x,y)` |
|---|---:|---:|---:|
| role-0000 | (-0.450, 0.900) | (-0.900, 0.450) | (-2.250, 0.000) |
| role-0001 | (-0.450, 0.000) | (-0.900, -0.450) | (-1.350, 0.000) |
| role-0002 | (-0.450, -0.900) | (0.000, 0.450) | (-0.450, 0.000) |
| role-0003 | (0.450, 0.900) | (0.000, -0.450) | (0.450, 0.000) |
| role-0004 | (0.450, 0.000) | (0.900, 0.450) | (1.350, 0.000) |
| role-0005 | (0.450, -0.900) | (0.900, -0.450) | (2.250, 0.000) |

### N = 8

| Role | KEEP `(x,y)` | COMPACT `(x,y)` | LINE `(x,y)` |
|---|---:|---:|---:|
| role-0000 | (-0.787, 0.787) | (-1.350, 0.450) | (-3.150, 0.000) |
| role-0001 | (-0.787, -0.113) | (-1.350, -0.450) | (-2.250, 0.000) |
| role-0002 | (-0.787, -1.012) | (-0.450, 0.450) | (-1.350, 0.000) |
| role-0003 | (0.113, 0.787) | (-0.450, -0.450) | (-0.450, 0.000) |
| role-0004 | (0.113, -0.113) | (0.450, 0.450) | (0.450, 0.000) |
| role-0005 | (0.113, -1.012) | (0.450, -0.450) | (1.350, 0.000) |
| role-0006 | (1.012, 0.787) | (1.350, 0.450) | (2.250, 0.000) |
| role-0007 | (1.012, -0.113) | (1.350, -0.450) | (3.150, 0.000) |

### N = 12

| Role | KEEP `(x,y)` | COMPACT `(x,y)` | LINE `(x,y)` |
|---|---:|---:|---:|
| role-0000 | (-0.900, 1.350) | (-2.250, 0.450) | (-4.950, 0.000) |
| role-0001 | (-0.900, 0.450) | (-2.250, -0.450) | (-4.050, 0.000) |
| role-0002 | (-0.900, -0.450) | (-1.350, 0.450) | (-3.150, 0.000) |
| role-0003 | (-0.900, -1.350) | (-1.350, -0.450) | (-2.250, 0.000) |
| role-0004 | (0.000, 1.350) | (-0.450, 0.450) | (-1.350, 0.000) |
| role-0005 | (0.000, 0.450) | (-0.450, -0.450) | (-0.450, 0.000) |
| role-0006 | (0.000, -0.450) | (0.450, 0.450) | (0.450, 0.000) |
| role-0007 | (0.000, -1.350) | (0.450, -0.450) | (1.350, 0.000) |
| role-0008 | (0.900, 1.350) | (1.350, 0.450) | (2.250, 0.000) |
| role-0009 | (0.900, 0.450) | (1.350, -0.450) | (3.150, 0.000) |
| role-0010 | (0.900, -0.450) | (2.250, 0.450) | (4.050, 0.000) |
| role-0011 | (0.900, -1.350) | (2.250, -0.450) | (4.950, 0.000) |

### N = 16

| Role | KEEP `(x,y)` | COMPACT `(x,y)` | LINE `(x,y)` |
|---|---:|---:|---:|
| role-0000 | (-1.350, 1.350) | (-3.150, 0.450) | (-6.750, 0.000) |
| role-0001 | (-1.350, 0.450) | (-3.150, -0.450) | (-5.850, 0.000) |
| role-0002 | (-1.350, -0.450) | (-2.250, 0.450) | (-4.950, 0.000) |
| role-0003 | (-1.350, -1.350) | (-2.250, -0.450) | (-4.050, 0.000) |
| role-0004 | (-0.450, 1.350) | (-1.350, 0.450) | (-3.150, 0.000) |
| role-0005 | (-0.450, 0.450) | (-1.350, -0.450) | (-2.250, 0.000) |
| role-0006 | (-0.450, -0.450) | (-0.450, 0.450) | (-1.350, 0.000) |
| role-0007 | (-0.450, -1.350) | (-0.450, -0.450) | (-0.450, 0.000) |
| role-0008 | (0.450, 1.350) | (0.450, 0.450) | (0.450, 0.000) |
| role-0009 | (0.450, 0.450) | (0.450, -0.450) | (1.350, 0.000) |
| role-0010 | (0.450, -0.450) | (1.350, 0.450) | (2.250, 0.000) |
| role-0011 | (0.450, -1.350) | (1.350, -0.450) | (3.150, 0.000) |
| role-0012 | (1.350, 1.350) | (2.250, 0.450) | (4.050, 0.000) |
| role-0013 | (1.350, 0.450) | (2.250, -0.450) | (4.950, 0.000) |
| role-0014 | (1.350, -0.450) | (3.150, 0.450) | (5.850, 0.000) |
| role-0015 | (1.350, -1.350) | (3.150, -0.450) | (6.750, 0.000) |

### N = 24

| Role | KEEP `(x,y)` | COMPACT `(x,y)` | LINE `(x,y)` |
|---|---:|---:|---:|
| role-0000 | (-1.725, 1.725) | (-4.950, 0.450) | (-10.350, 0.000) |
| role-0001 | (-1.725, 0.825) | (-4.950, -0.450) | (-9.450, 0.000) |
| role-0002 | (-1.725, -0.075) | (-4.050, 0.450) | (-8.550, 0.000) |
| role-0003 | (-1.725, -0.975) | (-4.050, -0.450) | (-7.650, 0.000) |
| role-0004 | (-1.725, -1.875) | (-3.150, 0.450) | (-6.750, 0.000) |
| role-0005 | (-0.825, 1.725) | (-3.150, -0.450) | (-5.850, 0.000) |
| role-0006 | (-0.825, 0.825) | (-2.250, 0.450) | (-4.950, 0.000) |
| role-0007 | (-0.825, -0.075) | (-2.250, -0.450) | (-4.050, 0.000) |
| role-0008 | (-0.825, -0.975) | (-1.350, 0.450) | (-3.150, 0.000) |
| role-0009 | (-0.825, -1.875) | (-1.350, -0.450) | (-2.250, 0.000) |
| role-0010 | (0.075, 1.725) | (-0.450, 0.450) | (-1.350, 0.000) |
| role-0011 | (0.075, 0.825) | (-0.450, -0.450) | (-0.450, 0.000) |
| role-0012 | (0.075, -0.075) | (0.450, 0.450) | (0.450, 0.000) |
| role-0013 | (0.075, -0.975) | (0.450, -0.450) | (1.350, 0.000) |
| role-0014 | (0.075, -1.875) | (1.350, 0.450) | (2.250, 0.000) |
| role-0015 | (0.975, 1.725) | (1.350, -0.450) | (3.150, 0.000) |
| role-0016 | (0.975, 0.825) | (2.250, 0.450) | (4.050, 0.000) |
| role-0017 | (0.975, -0.075) | (2.250, -0.450) | (4.950, 0.000) |
| role-0018 | (0.975, -0.975) | (3.150, 0.450) | (5.850, 0.000) |
| role-0019 | (0.975, -1.875) | (3.150, -0.450) | (6.750, 0.000) |
| role-0020 | (1.875, 1.725) | (4.050, 0.450) | (7.650, 0.000) |
| role-0021 | (1.875, 0.825) | (4.050, -0.450) | (8.550, 0.000) |
| role-0022 | (1.875, -0.075) | (4.950, 0.450) | (9.450, 0.000) |
| role-0023 | (1.875, -0.975) | (4.950, -0.450) | (10.350, 0.000) |

For complete grids/ladders, reflection and rotational grid symmetries hold. An
incomplete final row breaks geometric reflection but not deterministic role
construction, graph connectivity, permutation equivariance, or centering. LINE
is reflection-symmetric about its midpoint for all listed N.

## 5. Distinguishability

The exact Metric V3 overlap threshold is `2*epsilon_form=1.10 m`. Distances are
translation invariant, role-aware, and normalized by `d=0.90 m`.

| N | Pair | Max separation | RMS separation | Normalized max | Tube overlap |
|---:|---|---:|---:|---:|---|
| 5 | KEEP / COMPACT | 1.538 | 1.018 | 1.709 | No |
| 5 | KEEP / LINE | 1.610 | 1.138 | 1.789 | No |
| 5 | COMPACT / LINE | 1.138 | 0.805 | 1.265 | No |
| 6 | KEEP / COMPACT | 1.423 | 0.972 | 1.581 | No |
| 6 | KEEP / LINE | 2.012 | 1.375 | 2.236 | No |
| 6 | COMPACT / LINE | 1.423 | 0.972 | 1.581 | No |
| 8 | KEEP / COMPACT | 1.501 | 0.886 | 1.668 | No |
| 8 | KEEP / LINE | 2.490 | 1.583 | 2.767 | No |
| 8 | COMPACT / LINE | 1.855 | 1.191 | 2.062 | No |
| 12 | KEEP / COMPACT | 1.622 | 1.246 | 1.803 | No |
| 12 | KEEP / LINE | 4.269 | 2.624 | 4.743 | No |
| 12 | COMPACT / LINE | 2.737 | 1.664 | 3.041 | No |
| 16 | KEEP / COMPACT | 2.012 | 1.423 | 2.236 | No |
| 16 | KEEP / LINE | 5.566 | 3.337 | 6.185 | No |
| 16 | COMPACT / LINE | 3.628 | 2.158 | 4.031 | No |
| 24 | KEEP / COMPACT | 3.468 | 2.307 | 3.853 | No |
| 24 | KEEP / LINE | 8.796 | 5.169 | 9.773 | No |
| 24 | COMPACT / LINE | 5.419 | 3.171 | 6.021 | No |

The narrowest margin is COMPACT/LINE at N=5: `1.138-1.100=0.038 m`. This is
metric distinguishability only; COMPACT remains pending closed-loop forced-
topology qualification.

## 6. Shared adapters and semantic equivalence

`RoleAssignment` delegates KEEP and COMPACT construction and pairwise rotation
to the registry; LINE retains mission-setup rank assignment while using the
same registry LINE formula. The selected local controller consumes robot-local
role coordinates and pairwise offsets; it does not generate a template. Metric
V3 consumes the same `RoleAssignment` and adds a registry-backed generic tube
adapter without changing `epsilon_form`.

For N in `{5,6,8,12,16,24}`:

- LINE offsets are exactly equal to the pre-Phase-3 formula;
- KEEP offsets are exactly equal after the permitted common centering
  translation; N=6 is already exactly centered;
- KEEP/LINE pairwise offsets are equal to float tolerance;
- Metric V3 centering removes the same common translation, so KEEP/LINE tube
  decisions are unchanged;
- controller gains, runtime `MODES=(KEEP,LINE)`, protocol state, and metric
  tolerance are unchanged.

The KEEP centering is classification **A: representation-only change**. No
category B or C correction and no category D regression was found. COMPACT is
`mechanically-compatible-pending-phase6-qualification`; it was not added to the
deployed binary protocol or selector.

## 7. Persistent roles, serialization, and migration

Persistent roles are immutable records derived from canonical stable robot
keys sorted independently of input order. IDs (`role-0000`, ...) are unique,
remain fixed across topology changes, serialize under
`rvt-persistent-roles/v1`, and contain no leader designation. Runtime local
views contain only own role metadata, committed topology ID, neighbour role
IDs, and required pairwise offsets.

Templates serialize under `rvt-topology-template/v1` with strict keys,
registry/definition versions, source parameters, and SHA-256 integrity. Loading
reconstructs derived geometry and rejects unknown fields or tampering.

Legacy migration is explicit and vocabulary-versioned. Decentralized binary
IDs `0/2` map equivalently to KEEP/LINE. Centralized action IDs `1/3/4` remain
COMPRESS/SPLIT_HINT/RECOVER actions and are never reinterpreted as COMPACT.
Retired SPLIT fails as non-primary. Checkpoints require explicit vocabulary
metadata; output-head width alone is rejected as ambiguous. Historical results
remain traceable and none are invalidated by Phase 3.

## 8. Acceptance gates

| Gate | Result | Evidence |
|---|---|---|
| P3-G1 authoritative registry | Pass | One immutable versioned definition for IDs 0, 5, 2 |
| P3-G2 variable size | Pass | All required 18 cells construct; invalid configurations reject explicitly |
| P3-G3 persistent roles | Pass | Stable keyed roles, permutation-independent, no leader |
| P3-G4 physical validity | Pass | Clearance 0.90 m and connected sparse graphs in every cell |
| P3-G5 topology distinction | Pass | No Metric V3 tube overlap in any required pair |
| P3-G6 local geometry | Pass | Edge antisymmetry/cycle/rotation tests and local runtime views |
| P3-G7 shared source | Pass | Controller role adapter and Metric V3 use registry-backed geometry |
| P3-G8 legacy reproducibility | Pass | Versioned migration; ambiguous checkpoint semantics fail explicitly |
| P3-G9 decentralization | Pass | No pooling, selector, leader, or runtime global template inspection |
| P3-G10 scope control | Pass | Static geometry only; no Phase 4+ mechanism or experiment |

## 9. Verification and limitations

- Approved Phase 2 suite: **758 passed**.
- Phase 3 full working-tree suite: **1004 passed, 1 pre-existing PyTorch
  warning** (`56.54 s`).
- Strict-decentralization guard: **Pass; zero violations**.
- No-unexplained-runtime-constant guard: **Pass; zero violations**.
- Dedicated Phase 3 topology tests: **246 passed**.
- Required mechanical matrix: **18 supported, 0 rejected**.
- Scientific closed-loop experiments run in Phase 3: **0**.

Algorithmic construction and mechanical/metric eligibility are demonstrated
through N=24. Closed-loop validation remains whatever was established before
Phase 3 for KEEP/LINE; there is no COMPACT closed-loop evidence. Team membership
changes, dynamic communication connectivity, transition readiness, and learned
selection remain outside scope.

There is no mechanical blocker for Phase 4. Phase 4 must preserve registry IDs,
local-view boundaries, explicit migration, and the distinction between nominal
formation graphs and dynamic communication graphs.

## Verdict

**C. The authoritative variable-size topology registry is mechanically valid; proceed to Phase 4.**
