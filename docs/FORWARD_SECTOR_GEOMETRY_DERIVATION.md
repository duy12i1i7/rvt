# Forward Sector Geometry Derivation (Task G2)

## 1. What the constant actually did

`forward_opening_evidence` rejects the opening when any obstacle satisfies
`ox > 0 and |oy| <= W`. So **W is the lateral band, measured across the mission
direction, in which obstacle returns ahead mean "the passage has not ended"**.

Of the candidate meanings, it is a **corridor-side-wall search width** — and
more precisely, it must cover the region the robot is about to move into.

Its old comment claimed it was "the line formation's lateral extent (0 m) plus
the robot-obstacle threshold", i.e. 0.550 m. The literal was 1.2. Neither
matched.

## 2. The derivation

```
W_i = |lateral(r_i^KEEP) − lateral(r_i^LINE)| + collision_clearance + safety_margin
```

Robot *i* expands from its LINE role to its KEEP role. The lateral component of
that displacement is exactly the band it will sweep. It must stay
`collision_clearance` from any obstacle **centre** throughout, so the band it
must observe free is the displacement plus the clearance.

Per role at N = 6 (spacing 0.9, clearance 0.55):

| role lateral offset | derived W |
|---|---|
| 0.0 (centre column) | **0.550 m** |
| 0.9 (outer columns) | **1.450 m** |

## 3. The two failure modes

- **W too small** — the robot declares an opening while wall material still lies
  in the band it is about to enter, and expands prematurely inside the passage.
  The audited 1.2 m under-covers the N = 6 outer roles by **0.25 m**. This is
  the α 0.25 premature-expansion mechanism.
- **W too large** — distant obstacles unrelated to the passage keep the sector
  occupied and the event never fires.

## 4. Observability

`0 < W_i <= R_obs` is required and checked. At N = 6 the widest role needs
1.450 m against `R_obs = 3.0 m`. When the requirement exceeds sensor range,
`forward_sector_observable` returns False and `check_team_size` reports the
configuration unsupported — it is **not** silently clipped.

Nothing in this derivation comes from a corridor width, a step number, a seed
or a closed-loop success rate.
