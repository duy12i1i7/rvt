# Smoke Benchmark — Evaluation Protocol v2 — Report

**DIAGNOSTIC ONLY.** This run exists to verify that the corrected pipeline is
mechanically sound. It makes **no claim** of superiority, statistical
significance, scalability, robustness, generalization, decentralization,
recoverability, or publication readiness. The learned models were trained for
**6 epochs on 8 expert episodes with a single model seed** — they are not
trained models in any scientific sense, and none of their numbers should be read
as performance.

---

## 1. Exact Git commit

| | |
|---|---|
| Branch | `fix/benchmark-validity` (not merged) |
| Commit at benchmark time | **`fafafc5008dd932c27fec409716eb7547c4f3fee`** |
| Schema | `evaluation_schema_version = 2` |
| Recorded in | every checkpoint, every CSV row, `config.yaml` |

Pre-smoke state:

```
$ git log --oneline -6
05a7ee0 docs: evaluation protocol v2 specification and verification
c08a0c1 fix: evaluation protocol v2 - metric semantics, splits, seed roles, budgets
b4b448a docs: add benchmark bug verification report
7ab106f fix: correct benchmark validity defects and add verification tests
637e2e2 chore: carry over pre-existing checkpoint-resume change
3bb1c61 docs: add prescreen diagnosis and scientific redesign audit

$ pytest -q
108 passed
```

`git status --short` showed only the pre-existing manuscript/Gazebo working-tree
changes that predate this work (`latex/*`, `output/`, `ros2_ws/deploy/*`), none
of which affect the benchmark.

One correction was committed *after* that snapshot and before the final run
(§8.1), so the run itself is at the commit above.

---

## 2. Complete configuration

Full machine-readable copy: `results/smoke_protocol_v2/config.yaml`.

| Item | Value |
|---|---|
| Methods | `fixed_formation_expert`, `gnn_only`, `rvt_swarm`, `orca` (RVO2), `cbf_qp` (exact 2-D QP) |
| Proxy methods | **excluded** — no `orca_like`, `cbf_qp_like`, or `centralized_mpc` |
| Test scenarios | `open_field` (open), `narrow_passage` (constrained bottleneck) |
| Test team sizes | N ∈ {4, 8} |
| Episodes per cell | 30 → 120 per method, **600 rows total** |
| Final-test seed | 0 (namespace `[30_000_000, 40_000_000)`) |
| Model seed | 0 (single seed — deliberately not a multi-seed study) |
| Validation split | `narrow_passage`, `dynamic_obstacles` at N ∈ {5, 11} — disjoint from test |
| Determinism | **deterministic / no-noise mode** (§2.1) |

### 2.1 Seed roles declared inactive (Step 1.4, option B)

`counterfactual_rollout_seed` and `environment_noise_seed` are declared in
`SeedConfig` but consumed nowhere: rollout labelling is deterministic (one
rollout per candidate, M = 1) and **no sensor or actuation noise model exists**.
Rather than pretend they are wired, this run is explicitly declared
deterministic/no-noise. `assert_deterministic_mode()` greps the environment and
dataset sources and **fails the run** if either token ever appears there without
this declaration being updated.

> **No noise-robustness conclusion may be drawn from this benchmark.**

### 2.2 Reduced smoke budget (stated before training)

| Setting | Value | Reason |
|---|---|---|
| expert episodes | 8 (→ 800 graphs) | enough samples without a multi-hour counterfactual-labelling pass |
| epochs | 6 | loop, checkpointing, early stopping and top-k recheck all execute |
| validation interval | 2 epochs → 3 calls | exercises ranking and the candidate pool |
| top-k pool | 2 | exercises the recheck path with >1 candidate |
| patience | 3 | structural exercise only; cannot fire within 6 epochs |

Applied **identically** to `gnn_only` and `rvt_swarm`.

---

## 3. Fresh training-budget comparison

Both learned methods trained fresh into `checkpoints/smoke_protocol_v2/`. No
legacy checkpoint was loaded at any point.

| Field | gnn_only | rvt_swarm | equal |
|---|---|---|---|
| Epochs | 6 | 6 | ✓ |
| Steps/epoch | 23 | 23 | ✓ |
| Max optimizer steps | 138 | 138 | ✓ |
| Validation interval | 2 | 2 | ✓ |
| Max validation calls | 3 | 3 | ✓ |
| Checkpoints considered | 2 | 2 | ✓ |
| Early-stopping patience | 40→3 | 40→3 | ✓ |
| Selection rule | lexicographic + top-k recheck | same | ✓ |
| Hyperparameter trials | 0 | 0 | ✓ |
| Validation scenarios / N | narrow_passage, dynamic_obstacles / {5, 11} | same | ✓ |
| Model seed | 0 | 0 | ✓ |
| Training data | one shared dataset | same | ✓ |

Checkpoint provenance (recorded inside each `.pt`):

```
gnn_only   schema=2  commit=fafafc5008dd932c27fec409716eb7547c4f3fee  epoch=2  fresh=True
rvt_swarm  schema=2  commit=fafafc5008dd932c27fec409716eb7547c4f3fee  epoch=4  fresh=True
```

---

## 4. Evidence of matched episode signatures

Signatures are SHA-256 over initial positions, velocities, goal, obstacles and
obstacle velocities. Example cell (`narrow_passage`, N = 8, episode 0):

| Method | seed | signature |
|---|---|---|
| fixed_formation_expert | 30010800 | `37826b5cb94773f71f42a9d7494d9007` |
| gnn_only | 30010800 | `37826b5cb94773f71f42a9d7494d9007` |
| rvt_swarm | 30010800 | `37826b5cb94773f71f42a9d7494d9007` |
| orca | 30010800 | `37826b5cb94773f71f42a9d7494d9007` |
| cbf_qp | 30010800 | `37826b5cb94773f71f42a9d7494d9007` |

Across all **120 matched cells × 5 methods**, every cell resolves to exactly one
distinct signature (consistency check 2).

---

## 5. Consistency-check results

```
[PASS]  1. every result carries evaluation_schema_version == 2            (n=600)
[PASS]  2. episode signatures identical across methods                    (n=120)
[PASS]  3. no final-test episode used for validation / selection          (n=124)
[PASS]  4. success <= goal_reached and success <= collision_free          (n=600)
[PASS]  5. any collision step implies collision_free == 0                 (n=600)
[PASS]  6. collision_free == 1 implies both collision-step counts are zero (n=600)
[PASS]  7. episode-wide collision_free <= terminal collision_free         (n=600)
[PASS]  8. all initial states valid (no collision, in bounds, geometry)   (n=120)
[PASS]  9. no NaN or infinity in metrics or runtime values                (n=600)
[PASS] 10. runtime measurement covers exactly the control steps           (n=600)
[PASS] 11. every learned method uses a fresh schema-2 checkpoint          (n=2)
[PASS] 12. training and model-selection budgets equal across methods      (n=2)
```

All twelve pass. Check 8 **failed on the first two attempts**; see §8.1.

---

## 6. Results by method, scenario and team size

30 matched episodes per cell. `CF` = episode-wide collision-free; `CF_t` = the
old terminal-step convention; `InTube` = fraction of episode inside the formation
tube; `TSw` = topology switches; `FiltR` = safety-filter activation rate.

### open_field, N = 4
| method | Succ | Goal | CF | CF_t | FormOK | InTube | Dead | Colps | TSw | FiltR |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed_formation_expert | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.860 | 0.000 | 0.000 | 0.00 | 0.000 |
| gnn_only | 0.067 | 0.500 | 1.000 | 1.000 | 0.267 | 0.516 | 0.167 | 0.167 | 0.00 | 0.000 |
| rvt_swarm | 0.000 | 0.200 | 1.000 | 1.000 | 0.033 | 0.351 | 0.167 | 0.567 | 2.07 | 0.279 |
| orca | 0.933 | 0.967 | 1.000 | 1.000 | 0.967 | 0.780 | 0.000 | 0.000 | 0.27 | 0.000 |
| cbf_qp | 0.967 | 1.000 | 1.000 | 1.000 | 0.967 | 0.819 | 0.000 | 0.000 | 0.00 | 0.000 |

### open_field, N = 8
| method | Succ | Goal | CF | CF_t | FormOK | InTube | Dead | Colps | TSw | FiltR |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed_formation_expert | 0.767 | 0.833 | 1.000 | 1.000 | 0.867 | 0.737 | 0.000 | 0.000 | 0.00 | 0.000 |
| gnn_only | 0.000 | 0.233 | 0.900 | 1.000 | 0.000 | 0.314 | 0.067 | 0.067 | 0.00 | 0.000 |
| rvt_swarm | 0.000 | 0.100 | 0.967 | 1.000 | 0.000 | 0.087 | 0.400 | 0.733 | 1.90 | 0.363 |
| orca | 0.567 | 0.767 | 1.000 | 1.000 | 0.600 | 0.658 | 0.000 | 0.000 | 0.57 | 0.000 |
| cbf_qp | 0.767 | 0.867 | 0.967 | 1.000 | 0.800 | 0.719 | 0.000 | 0.033 | 0.00 | 0.000 |

### narrow_passage, N = 4
| method | Succ | Goal | CF | CF_t | FormOK | InTube | Dead | Colps | TSw | FiltR |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed_formation_expert | 0.133 | 0.133 | 0.767 | 0.967 | 0.367 | 0.518 | 0.267 | 0.333 | 0.00 | 0.000 |
| gnn_only | 0.033 | 0.167 | 0.500 | 1.000 | 0.533 | 0.640 | 0.133 | 0.233 | 0.00 | 0.000 |
| rvt_swarm | 0.000 | 0.000 | 0.867 | 1.000 | 0.067 | 0.256 | 0.133 | 1.000 | 12.67 | 0.883 |
| orca | 0.000 | 0.000 | 0.867 | 0.933 | 0.100 | 0.288 | 0.033 | 0.167 | 0.67 | 0.000 |
| cbf_qp | 0.200 | 0.233 | 0.733 | 1.000 | 0.433 | 0.539 | 0.333 | 0.433 | 0.00 | 0.000 |

### narrow_passage, N = 8
| method | Succ | Goal | CF | CF_t | FormOK | InTube | Dead | Colps | TSw | FiltR |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed_formation_expert | 0.000 | 0.000 | 0.333 | 0.900 | 0.033 | 0.381 | 0.267 | 0.700 | 0.00 | 0.000 |
| gnn_only | 0.000 | 0.000 | 0.233 | 0.833 | 0.033 | 0.209 | 0.033 | 0.733 | 0.00 | 0.000 |
| rvt_swarm | 0.000 | 0.000 | 0.300 | 0.900 | 0.000 | 0.143 | 0.133 | 1.000 | 14.00 | 0.918 |
| orca | 0.000 | 0.000 | 0.633 | 0.867 | 0.000 | 0.189 | 0.033 | 0.367 | 1.00 | 0.000 |
| cbf_qp | 0.000 | 0.000 | 0.333 | 1.000 | 0.067 | 0.363 | 0.400 | 0.667 | 0.00 | 0.000 |

### Metric-semantics effect, measured on fresh schema-2 data

The terminal-step convention that produced the manuscript's tables, versus the
episode-wide conjunction, on the same 120 episodes per method:

| method | CF terminal | CF episode-wide | gap |
|---|---|---|---|
| fixed_formation_expert | 0.967 | 0.775 | **+0.192** |
| gnn_only | 0.958 | 0.658 | **+0.300** |
| rvt_swarm | 0.975 | 0.783 | **+0.192** |
| orca | 0.950 | 0.875 | +0.075 |
| cbf_qp | 1.000 | 0.758 | **+0.242** |

The gap is large **and method-dependent** (0.075 to 0.300), which is the direct
empirical reason the pre-fix tables cannot be corrected post hoc: the distortion
does not act as a common offset.

### Inference latency (model preloaded, warm-up excluded)

| method | mean ms | median ms | p95 ms | p99 ms | timed steps |
|---|---|---|---|---|---|
| fixed_formation_expert | 0.363 | 0.363 | 0.401 | 0.427 | 13 009 |
| gnn_only | 0.831 | 0.820 | 0.936 | 1.003 | 13 954 |
| rvt_swarm | 1.577 | 1.565 | 1.773 | 1.884 | 14 242 |
| orca | 1.811 | 1.810 | 1.883 | 1.960 | 13 201 |
| cbf_qp | 0.533 | 0.534 | 0.626 | 0.708 | 13 069 |

CPU, single-threaded BLAS. Reported for pipeline diagnosis, not as a deployment
benchmark.

---

## 7. Trajectory diagnostics

`results/smoke_protocol_v2/figures/` — trajectory + time-series pair per category.

| Category | Episode selected |
|---|---|
| 1. successful | `fixed_formation_expert` · open_field · N=4 · seed 30000400 |
| 2. robot–robot collision | `fixed_formation_expert` · narrow_passage · N=4 · seed 30010427 |
| 3. robot–obstacle collision | `fixed_formation_expert` · narrow_passage · N=4 · seed 30010401 |
| 4. deadlock / collapse | `fixed_formation_expert` · narrow_passage · N=4 · seed 30010401 |
| 5. topology switching | `rvt_swarm` · open_field · N=4 · seed 30000401 |

Each trajectory panel carries paths, obstacle discs, the robot-radius circle, the
RR/RO collision boundaries, start markers, goal + tolerance, formation mode over
time, collision timestamps and safety-filter activation points. Each time-series
panel carries minimum clearance (with both bounds), formation RMS (with the tube),
progress, selected topology, filter activation and collision flags.

Two observations the plots make concrete:

- **Category 2** is precisely the failure mode the audit identified: a single
  robot–robot contact at step ≈54, a clean terminal step, and formation RMS above
  the tube for most of the second half. Under the old convention this episode was
  reported collision-free; under schema 2 it is not.
- **Category 5** shows the 6-epoch `rvt_swarm` model driving the team away from
  the goal with the safety filter active on 97 of 120 steps and minimum
  robot–robot clearance pinned at 0.402 m — i.e. the filter holding the team
  exactly on the constraint boundary.

---

## 8. Remaining mechanical anomalies

### 8.1 A defect this run found and fixed (consistency check 8)

Check 8 failed on the first run (5 invalid initial states) and again on the
second (9). Diagnosis, in order:

1. **First failure was my instrumentation**, not the environment: the runner
   measured `trace[0]`, the state *after* step 1, rather than the reset state.
   Fixed to use the captured `initial_obs`.
2. **Second failure was a real defect** introduced by the `spawn_jitter` fix in
   commit `7ab106f`. The `narrow_passage` spawn layout packs robots into four
   columns whose outermost offset already sits ≈9 mm inside the workspace
   boundary, so un-clamped jitter started robots up to **3 cm outside the
   12 × 12 m workspace** (max |pos| = 6.028 m against a 6.0 m bound), in 9 of 120
   resets. Fixed by clamping spawns to `world_size/2 − robot_radius`, with a
   regression test over all scenarios and N ∈ {2, 4, 8, 16, 24}.

The consistency gate worked as intended: it blocked interpretation until both
were resolved. Note that the *previous* verification pass did not catch defect 2
because `test_spawn_randomisation_never_creates_an_initial_collision` checked
clearances but not bounds, and sampled N ∈ {2, 8, 24} rather than the packed
4-column layouts.

### 8.2 Anomalies observed but not fixed

1. **`rvt_swarm` safety filter activates on 88–92 % of steps in
   `narrow_passage`** and 28–36 % in open field, versus 0 % for every other
   method. Combined with minimum clearance pinned at ≈0.402 m, the filter appears
   to be doing most of the controlling. Whether this is an artifact of a 6-epoch
   model or a property of the trigger rule (`ρ_th = 1 − v_max·Δt/d₀ = 0.85`)
   **cannot be determined from this run** and needs a trained model.
2. **`rvt_swarm` switches topology 12.7–14.0 times per 120-step episode** in
   `narrow_passage` (≈1 switch per 9 steps), while the manuscript reports a
   switch *rate* of 0.131. The metric is a count here, not a rate, and the model
   is untrained — but the churn is high enough to note.
3. **`rvt_swarm` collapse latch = 1.000** in both narrow-passage cells. Expected
   to rise under latch semantics (§EPISODE_METRIC_SPECIFICATION), but saturation
   at 1.000 makes the metric uninformative in this regime.
4. **`orca` reports non-zero topology switches** (0.27–1.00). ORCA has no
   topology mechanism; the switches come from `_heuristic_topology` supplying its
   *preferred velocity*. This is a faithful and favourable ORCA configuration but
   it must be described precisely, and the topology column is not meaningful for
   this method.
5. **`gnn_only` reaches the goal in 50 % of open-field N=4 episodes but scores
   0.067 success** — the gap is formation satisfaction, not safety. Consistent
   with 6 epochs of behaviour cloning.
6. **`ms_per_step` for `orca`** (1.81 ms) exceeds `rvt_swarm` (1.58 ms) because
   RVO2 rebuilds its simulator each step. That is an implementation property of
   the wrapper, not of ORCA.

### 8.3 Known non-anomalies

`completion_time` is NaN for censored episodes and `min_*_clearance` is infinite
for N < 2; both are exempted in check 9 by design and documented.

---

## 9. Is the benchmark ready for larger experiments?

**Mechanically, yes; scientifically, not yet.**

Working: schema stamping and gating; matched episodes across methods proven by
signature; split separation enforced at the selection chokepoint; fresh
provenance-stamped checkpoints; equal budgets; metric semantics behaving as
specified; timing isolated from I/O; twelve consistency gates that demonstrably
block interpretation when violated.

Not yet established: anything about method quality. One model seed, 6 epochs, 120
episodes per method, two scenarios, two team sizes, no confidence intervals, no
statistical test, no calibration, no generalization split, no communication
study. The learned methods are untrained by any reasonable standard.

---

## 10. Recommendation

> ### **B — Pipeline mechanically valid, but method design still requires audit.**

Not **A**: all twelve consistency checks pass, both defects surfaced during this
run were diagnosed and fixed, and 108 tests pass at the benchmark commit.

Not **C**: "ready for scientific pilot experiments" would require at minimum the
open items below. More importantly, this run leaves the *scientific* questions
from the original audit entirely untouched — centralized topology selection via
team-wide mean pooling, the absence of recovery-score calibration, and the fact
that the method's headline component showed a −0.003 success effect in the
manuscript's own ablation. A mechanically valid pipeline measuring an unaudited
method is not yet a pilot experiment.

**Before a pilot:** multiple training seeds with paired statistics; a realistic
training budget; the held-out generalization axes; a decision on whether the
safety filter's near-permanent activation is a trigger-rule defect; and the
recovery-score calibration study.

---

## 11. Compliance with the approval conditions

| Condition | Status |
|---|---|
| Remain on `fix/benchmark-validity` | ✓ |
| Do not merge into main | ✓ — not merged, no PR opened |
| Do not rewrite the manuscript | ✓ — no `latex/` file touched |
| Do not run the full benchmark | ✓ — 2 scenarios × 2 team sizes only |
| Do not use legacy checkpoints | ✓ — `checkpoints/smoke_protocol_v2/` trained fresh; check 11 enforces |
| Faithful baselines only | ✓ — RVO2 ORCA and exact-QP CBF-QP; proxies excluded |
| Timing excludes checkpoint I/O | ✓ — commit `fafafc5`, regression-tested |
| Noise seeds wired or declared inactive | ✓ — option B, asserted at runtime |
| No superiority / significance / robustness / generalization claims | ✓ |

Stopping here for approval.
