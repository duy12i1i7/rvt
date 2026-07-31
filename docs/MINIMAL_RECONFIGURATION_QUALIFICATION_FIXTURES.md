# Minimal Reconfiguration Qualification Fixtures (Task 4R-4)

`rvt_swarm/decentralized/qualification_fixtures.py`

**Controller-mechanics fixtures, not the six scientific scenario families.**
Geometry is derived from the authoritative role templates and the environment's
collision model. Nothing here was selected using any learned model.

**N = 6 only** — the sole team size certified KEEP/LINE separated
(`docs/KEEP_LINE_DISJOINTNESS_V3.md`).

---

## 1. Geometry from the environment's actual collision model

`environment.py:566` scores a robot-obstacle collision as
`distance_to_obstacle_CENTRE < min_ro_distance (0.55 m)`. So for walls whose
inner obstacle centres sit at `+/- h`, a formation of lateral extent `E` needs

```
h > E/2 + min_ro_distance
```

| formation | lateral extent | required `h` |
|---|---|---|
| KEEP (3x2 grid) | 1.80 m | **1.450 m** |
| LINE (single file) | 0.00 m | **0.550 m** |
| a single robot | — | **0.550 m** |

> **Correction.** An earlier version used
> `lateral + 2*(robot_radius + min_ro_distance)` as a required *width*, i.e.
> clearance from the obstacle SURFACE. The environment does not enforce that,
> so the fixtures were far more permissive than intended: the "line-only"
> corridor passed the KEEP formation and the "infeasible" corridor was crossed
> on 100 % of episodes. The values above are recomputed from the collision
> model, not from any report.

## 2. The three fixtures

| | A open keep | B line-only corridor | C infeasible |
|---|---|---|---|
| obstacles | none | 2 blocking walls | 2 blocking walls |
| wall half-separation `h` | — | **1.000 m** | **0.450 m** |
| KEEP passes (`h > 1.450`)? | n/a | no | no |
| LINE passes (`h > 0.550`)? | n/a | yes | **no** |
| purpose | nominal tracking | the reconfiguration test | negative control |

Corridor `h = 1.000` is the midpoint of `[h_line + 0.30, h_keep - 0.30]`, chosen
before any probe was run so it is not tuned to a policy.

Walls span from the gap to the **world boundary**, with 0.5 m point spacing
against 0.35 m obstacle radius so they overlap and have no gaps. The first
version laid short obstacle rows along the corridor only, and robots simply
drove around them through open space — which is why the infeasible fixture was
being crossed.

## 3. World size and episode budget — measured, not guessed

`FIXTURE_WORLD_SIZE = 18.0`, `FIXTURE_MAX_STEPS = 260`.

LINE → KEEP settling from the exact line template in open space takes **~54
control steps** (measured: 54, 54, 53 across three seeds; final error
0.301–0.304). With `L_recover = 20`, about **74 steps must remain after the exit
plane**, i.e. ~10 m of downstream travel at 0.135 m/step.

Measured directly, scripted K → L → K on fixture B:

| world | steps after crossing | min `E_inf^KEEP` after | longest in-tube run | recovered |
|---|---|---|---|---|
| 12.0 m (default) | ~40 | 0.466 / 0.520 / 0.653 | 5 / 2 / 0 | **no** |
| 18.0 m | ~87 | 0.192 / 0.200 / 0.270 | 51 / 48 / 38 | **yes** |

The default 12 m world cannot host a full N = 6 KEEP → LINE → KEEP mission: the
episode terminates on goal arrival before the formation can settle and dwell.
This is a property of the task and the controller, established **before** the
probe set was run, and it is a hard requirement for the Task 5 scenario
families.

## 4. Initial conditions

Every fixture starts on the KEEP role template plus bounded seeded jitter, with
`E_inf^KEEP(0) = 0.0848` against `epsilon_init = 0.25`. See
`docs/RECONFIGURATION_INITIAL_CONDITIONS.md`.

## 5. Known limitation

`always_keep` crosses fixture B on **80 %** of episodes despite `h = 1.000` being
below the KEEP requirement of 1.450. The local controller's obstacle-avoidance
term compresses the formation, so KEEP deforms enough to squeeze through and
then re-expands. The corridor is therefore line-only for the *undeformed*
template but not strictly line-forcing for the *controlled* team.

This does not affect the recovery question these fixtures were built to answer,
but the Task 5 families will need narrower corridors — or an explicit
deformation bound — if they are to force the line mode rather than merely
favour it.
