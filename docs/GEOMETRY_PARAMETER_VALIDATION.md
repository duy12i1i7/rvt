# Geometry Parameter Validation

Justification for the two parameters introduced by the benchmark-validity fixes.
Neither is accepted as an arbitrary value.

Raw data: [`../results/geometry_parameter_validation.csv`](../results/geometry_parameter_validation.csv)
(16 parameter combinations × 192 episodes = 3 072 resets; 4 scenarios × N ∈ {2,8,16,24} × 12 seeds).

**This is not a performance benchmark.** No task metric, success rate, or method
comparison was computed. Only initial-state validity and geometric feasibility.

---

## 1. `spacing_margin`

### Physical meaning

The clearance the *commanded formation set-point* keeps above the robot–robot
collision threshold. Three distances must be distinguished, and the manuscript
conflated the last two:

| Distance | Value | Meaning |
|---|---|---|
| **Physical contact** | `2·r = 0.360 m` | bodies overlap; a real collision |
| **Scored collision threshold** | `min_rr_distance = 0.400 m` | desired safety clearance; what `compute_metrics` counts as a collision |
| **Commanded minimum spacing** | `nominal_spacing · min_formation_scale` | what the formation template *asks* the robots to achieve |

Before the fix, `min_formation_scale = min_rr_distance / nominal_spacing` made the
commanded spacing **exactly** `0.400 m` — identical to the scored threshold. The
set-point sat on the failure boundary: perfect tracking scored zero collisions,
and *any* tracking error scored a collision. `spacing_margin` is the distance by
which the set-point is moved strictly into the feasible region:

```
min_formation_scale = (min_rr_distance + spacing_margin) / nominal_spacing
commanded_spacing   = min_rr_distance + spacing_margin      >  min_rr_distance
```

### Selection criteria (fixed before running the sweep)

- **C1 — strict feasibility.** `commanded_spacing > min_rr_distance` strictly, not
  merely `>=`. Rules out `spacing_margin = 0`.
- **C2 — one control step of tracking error.** A set-point should not be violated
  by a single step of tracking error. One control step of travel is
  `v_max · Δt = 0.9 × 0.15 = 0.135 m`. Requiring the margin to absorb at least a
  third of that gives `spacing_margin ≥ 0.045 m`.
- **C3 — numerical tolerance.** The margin must dominate float32 resolution at
  this scale (~1e-7 m) by many orders of magnitude. All candidates satisfy this;
  it is not discriminating.
- **C4 — minimality.** Subject to C1–C3, prefer the *smallest* value, because a
  larger margin reduces the team's achievable compression and so makes narrow
  passages harder. Choosing the largest feasible value would silently trade task
  difficulty for apparent safety.

### Sweep result

| `spacing_margin` | commanded spacing | headroom | strictly above threshold | formation feasible | narrow-passage feasible | initial collisions |
|---|---|---|---|---|---|---|
| 0.01 | 0.410 | 0.010 | yes | yes | yes | 0.000 |
| 0.03 | 0.430 | 0.030 | yes | yes | yes | 0.000 |
| **0.05** | **0.450** | **0.050** | **yes** | **yes** | **yes** | **0.000** |
| 0.08 | 0.480 | 0.080 | yes | yes | yes | 0.000 |

**All four are geometrically feasible.** The sweep does not discriminate, so the
choice rests entirely on the criteria above:

- 0.01 and 0.03 **fail C2** (`< 0.045 m`): a single control step of tracking error
  can push the commanded configuration back across the threshold.
- 0.05 and 0.08 both satisfy C1–C3; **C4 selects the smaller**.

### → **`spacing_margin = 0.05 m`**

Note that the split-lane width is unaffected across the whole range
(`lane_gap = max(nominal_spacing, spacing + min_rr) = 0.9 m` for every candidate,
giving a 1.26 m corridor footprint against the 1.5 m narrow-passage gap), so
narrow-passage feasibility does not constrain this parameter either.

---

## 2. `spawn_jitter`

### Why jitter is needed

`_spawn_agents` was a pure function of `(n_agents, scenario)` and consumed no
randomness, so **every episode with the same team size and scenario began from a
byte-identical configuration**, regardless of seed. Episode-to-episode variation
came only from obstacle layout. The manuscript nevertheless claimed "matched
random starts". Jitter restores independent initial conditions.

### Required properties

1. **Episode sets stay matched across methods.** Jitter is drawn from the
   environment's own `self.rng`, which is seeded solely by the episode seed in
   `reset()`. It is drawn *before* any method-specific computation and is
   completely independent of method identity, model weights, and `model_seed`.
   Verified by `tests/test_seed_independence.py::test_all_methods_receive_identical_test_episodes`,
   which compares SHA-256 signatures of initial states, goals, obstacles, and
   obstacle velocities.
2. **No method-specific randomness leaks in.** The policy never draws from
   `env.rng`; learned methods run under `torch.no_grad()` with no sampling. There
   is therefore no path by which a method could perturb its own episodes.
3. **Starts remain collision-free and feasible.** Measured below.
4. **The intended lattice is preserved.** Jitter is meant to de-correlate
   episodes, not to randomise the formation itself.

### Selection criteria (fixed before running the sweep)

- **C5 — non-degenerate.** `spawn_jitter > 0`, otherwise the defect is unfixed.
- **C6 — zero initial collisions.** Minimum initial robot–robot clearance must
  stay `≥ min_rr_distance` and robot–obstacle `≥ min_ro_distance`, across all
  scenarios and team sizes.
- **C7 — no resolver dependence.** The jittered lattice must be valid *before*
  `_resolve_collisions` runs. Relying on the resolver to repair spawns would
  distort the intended formation.
- **C8 — lattice preservation.** `spawn_jitter ≤ 0.15 · nominal_spacing = 0.135 m`,
  so displacement stays a perturbation of the lattice rather than a replacement
  for it.
- **C9 — maximal diversity.** Subject to C5–C8, prefer the *largest* value, since
  more jitter means more independent initial conditions.

### Sweep result

| `spawn_jitter` | as % of spacing | min initial RR clearance | initial collision rate | resolver intervention rate | out-of-bounds | invalid episodes |
|---|---|---|---|---|---|---|
| 0.00 | 0 % | 0.900 | 0.000 | 0.000 | 0.000 | 0.000 |
| 0.05 | 5.6 % | 0.806 | 0.000 | 0.000 | 0.000 | 0.000 |
| **0.12** | **13.3 %** | **0.676** | **0.000** | **0.000** | **0.000** | **0.000** |
| 0.20 | 22.2 % | 0.534 | 0.000 | 0.000 | 0.000 | 0.000 |

**All four are geometrically valid** — even 0.20 leaves 0.534 m of clearance,
well above the 0.400 m threshold, and the resolver never has to intervene. Again
the sweep does not discriminate, so:

- 0.00 **fails C5** (the defect is unfixed).
- 0.20 **fails C8** (22.2 % > 15 %): displacement becomes comparable to the
  formation structure it is perturbing.
- 0.05 and 0.12 both satisfy C5–C8; **C9 selects the larger**.

### → **`spawn_jitter = 0.12 m`**

---

## 3. Honest statement about this analysis

Both selected values coincide with the initial guesses in the previous commit.
That is a coincidence of round numbers, not a validation of the guesses: the
sweep shows **every** tested combination is feasible, so feasibility alone could
not have justified any choice. The values are justified by criteria C1–C9, which
were fixed before the sweep ran, and specifically by C2 (a control step of
tracking error) and C8 (lattice preservation) — the only two criteria that
discriminate.

Neither value was chosen by reference to any task metric, and no method
comparison was run at any point in this analysis. If either parameter is later
changed, it must be re-justified against these criteria, not against RVT-Swarm's
score.

Both parameters must be reported in the experimental-settings table of any
manuscript using this simulator.

## 4. Limitations

- The sweep covers the four existing scenario generators only. A tighter corridor
  than `narrow_passage` (gap 1.5 m) could make `spacing_margin = 0.05` binding;
  criterion C4 exists precisely to keep that headroom.
- C2's "one third of a control step" is a judgement call. It is stated so that a
  reviewer can disagree with the number rather than with an unexplained constant.
- Jitter is uniform and isotropic. Structured perturbations (rotations, formation
  scaling at spawn) would test generalization more aggressively and are not
  covered here.
