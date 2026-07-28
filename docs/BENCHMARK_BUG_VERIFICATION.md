# Benchmark Bug Verification

Empirical verification of the five critical software findings asserted in
[`PRESCREEN_REDESIGN_AUDIT.md`](PRESCREEN_REDESIGN_AUDIT.md), by reproducible
unit test rather than by code inspection.

**Scope.** Verification and minimal correction only. No benchmark was run, no
manuscript text was changed, and no model architecture was touched.

**Environment.** macOS (darwin), Python 3.9.6, pytest 8.4.2, repo at branch
`docs/prescreen-redesign-audit`. Run everything below with:

```bash
.venv/bin/python -m pytest tests/ -v
```

## Result summary

| # | Finding | Reproduced? | Test file | Fix |
|---|---|---|---|---|
| 1 | `CollisionFree` is a terminal-step, not episode-wide, quantity | **Yes** | `tests/test_episode_metrics.py` | `evaluate.py` accumulator |
| 2 | Collision resolution leaves bodies inside the collision threshold | **Yes** | `tests/test_collision_geometry.py` | `environment.py` resolution targets |
| 3 | Minimum commanded spacing equals the collision threshold | **Yes (equal, not smaller)** | `tests/test_collision_geometry.py` | shared `min_formation_scale` + margin |
| 4 | Different evaluation seeds produce identical initial states | **Yes (starts and goal; obstacles do vary)** | `tests/test_randomization.py` | seeded spawn jitter |
| 5 | Unequal training / validation / checkpoint-selection budgets | **Yes (2.50×)** | `tests/test_training_budget.py` | equal epoch budgets |

All five reproduced. One sub-claim is **corrected** and one framing is
**refined** in [§7](#7-corrections-and-retractions); nothing is retracted.

### Before

```
$ .venv/bin/python -m pytest tests/ -q --tb=no
..FFFFFF...FFFFFF.F...F.F...FFF.F                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_collision_geometry.py::test_robot_robot_resolution_clears_the_collision_threshold
FAILED tests/test_collision_geometry.py::test_robot_obstacle_resolution_clears_the_collision_threshold
FAILED tests/test_collision_geometry.py::test_state_is_collision_free_immediately_after_resolution
FAILED tests/test_collision_geometry.py::test_minimum_commanded_spacing_exceeds_collision_threshold
FAILED tests/test_collision_geometry.py::test_expert_controller_uses_the_same_spacing_floor
FAILED tests/test_collision_geometry.py::test_desired_offsets_at_minimum_scale_are_mutually_feasible
FAILED tests/test_episode_metrics.py::test_reported_collision_free_is_episode_wide
FAILED tests/test_episode_metrics.py::test_reported_success_uses_episode_wide_collision_free
FAILED tests/test_episode_metrics.py::test_terminal_values_are_still_available_for_comparison
FAILED tests/test_episode_metrics.py::test_reported_metrics_match_per_step_conjunction[adaptive_formation-open_field-4-45]
FAILED tests/test_episode_metrics.py::test_reported_metrics_match_per_step_conjunction[adaptive_formation-open_field-4-52]
FAILED tests/test_episode_metrics.py::test_reported_metrics_match_per_step_conjunction[adaptive_formation-cluttered-6-43]
FAILED tests/test_episode_metrics.py::test_reported_metrics_match_per_step_conjunction[cbf_qp-open_field-4-45]
FAILED tests/test_randomization.py::test_different_seeds_give_different_start_positions
FAILED tests/test_randomization.py::test_start_positions_vary_across_a_seed_sweep
FAILED tests/test_training_budget.py::test_training_epoch_budgets_are_equal
FAILED tests/test_training_budget.py::test_rollout_validation_budgets_are_equal
FAILED tests/test_training_budget.py::test_proposed_method_has_no_selection_advantage_over_the_gnn_baseline
FAILED tests/test_training_budget.py::test_validation_protocol_is_identical_across_methods
19 failed, 14 passed in 1.19s
```

### After

```
$ .venv/bin/python -m pytest tests/ -q --tb=no
.................................                                        [100%]
33 passed in 1.17s
```

The 6 pre-existing tests (`test_cbf_qp_baseline`, `test_centralized_mpc_baseline`,
`test_dataset_runtime_compat`, `test_multiseed_aggregation`, `test_orca_baseline`)
pass unchanged before and after. No regressions.

---

## 1. `CollisionFree` reports only the final timestep

### Files and lines

| Location | Role |
|---|---|
| `rvt_swarm/evaluate.py:32-66` | episode loop: `last_info = info` each step, then `return last_info` |
| `rvt_swarm/environment.py:522-560` | `compute_metrics()` evaluates the *current* positions; carries no history |
| `latex/access.tex:1047-1051` | the manuscript defines `CollisionFree` as "zero ... collisions over the episode" |

### Minimal reproducible example

```python
from rvt_swarm.config import Config
from rvt_swarm.environment import SwarmFormationEnv
from rvt_swarm.baselines import historical_baseline

cfg = Config()
env = SwarmFormationEnv(cfg)
obs = env.reset(4, "open_field", seed=45)
done, per_step, last = False, [], None
while not done:
    a, t = historical_baseline("adaptive_formation", obs, cfg)
    obs, _, done, last = env.step(a, t)
    per_step.append(last["collision_free"])

print("dirty steps        :", sum(c < 0.5 for c in per_step), "/", len(per_step))  # 10 / 97
print("episode-wide       :", float(all(c > 0.5 for c in per_step)))               # 0.0
print("reported (terminal):", last["collision_free"], "success:", last["success"]) # 1.0, 1.0
```

Ten collisions; reported collision-free **and** a full conjunctive success.

### Prevalence (640 baseline episodes, N ∈ {2,4,6,8} × 4 scenarios × seeds 42–61)

| Quantity | Count | Share |
|---|---|---|
| Reported collision-free despite a mid-episode collision | 363 / 640 | **56.7 %** |
| Reported as `Success` despite a mid-episode collision | 286 / 640 | **44.7 %** |

### Test design note

The natural reproducers are properties of the *dynamics*, so the geometry
corrections in §2–§3 legitimately dissolve some of them — the seed-45 episode
stops colliding entirely once the geometry is fixed. Tying the test to one seed
would therefore make it pass **vacuously** after the fix. The tests instead assert
the accumulator *semantics*, which are dynamics-independent:

* `_ScriptedCollisionEnv` pins the pattern exactly (collisions at steps 2–3, clean
  terminal step, goal reached, formation in tolerance), so the episode is
  guaranteed dirty-middle / clean-end regardless of config or controller;
* a 5-case sweep asserts `reported == per-step conjunction` on real episodes,
  which holds whether or not they happen to collide.

Both are red before the fix and green after, and neither can pass vacuously.

### Output before

```
tests/test_episode_metrics.py:120: AssertionError: reported collision_free=1.0 but the
  episode-wide value is 0.0 (41/120 steps had a collision)
tests/test_episode_metrics.py:140: AssertionError: the pre-fix terminal-step value should
  remain available for auditing
```

### Smallest safe correction — `rvt_swarm/evaluate.py`

Accumulate safety inside the existing loop; recompute the conjunctive success from
it; keep the old values under explicit names.

```python
episode_collision_free = 1.0            # before the loop
...
episode_collision_free = min(episode_collision_free, float(info["collision_free"]))
rr_collision_max = max(rr_collision_max, float(info["rr_collision"]))
ro_collision_max = max(ro_collision_max, float(info["ro_collision"]))
...
last_info["collision_free_terminal"] = float(last_info["collision_free"])
last_info["success_terminal"]        = float(last_info["success"])
last_info["collision_free"]          = float(episode_collision_free)
last_info["success"] = float(last_info["goal_reached"] > 0.5
                             and episode_collision_free > 0.5
                             and last_info["form_ok"] > 0.5)
```

### Output after

All 10 tests in `tests/test_episode_metrics.py` pass.

### Side effects

* **Every reported `collision_free` and `success` value changes.** This is the
  intended effect; it also means no published table can be corrected post hoc.
* `rollout_validation_score` and `rollout_validation_key` (`evaluate.py:177-205`)
  consume `success` and `collision_free`, so **checkpoint selection changes**.
  Existing checkpoints were selected under the old criterion and are no longer
  comparable to newly trained ones.
* `summarize()` uses an explicit key list, so the new keys are ignored unless
  added deliberately — no downstream breakage. Add `collision_free_terminal` /
  `success_terminal` there if you want both conventions in the reports.
* `deadlock`, `form_ok`, `form_rms`, and `irreversible_collapse` remain
  terminal-step quantities. Only the safety terms were corrected, deliberately, to
  keep the change minimal. **These should be revisited before publication** —
  `form_ok` in particular is arguably also an episode property.

---

## 2. Collision resolution leaves bodies inside the collision threshold

### Files and lines

| Location | Role |
|---|---|
| `rvt_swarm/environment.py:413-461` | `_resolve_collisions()` separation targets |
| `rvt_swarm/config.py:16-19` | `robot_radius=0.18`, `obstacle_radius=0.35`, `min_rr_distance=0.40`, `min_ro_distance=0.55` |
| `rvt_swarm/environment.py:529-534` | thresholds applied in `compute_metrics()` |

The resolver targeted **physical contact** (`2r = 0.36`, `r+R = 0.53`) while the
metric scores against a **safety margin** (`0.40`, `0.55`). Post-resolution
separations were `0.38` and `0.54` — both inside the threshold.

### Minimal reproducible example

```python
env = SwarmFormationEnv(Config())
env.reset(2, "open_field", seed=0)
env.state.positions = np.array([[0.0, 0.0], [0.10, 0.0]], dtype=np.float32)
env._resolve_collisions()
print(np.linalg.norm(env.state.positions[0] - env.state.positions[1]))  # 0.38 < 0.40
print(env.compute_metrics()["collision_free"])                          # 0.0
```

### Output before

```
tests/test_collision_geometry.py: AssertionError: resolver left robots 0.3800 m apart,
  inside the 0.4000 m robot-robot collision threshold
tests/test_collision_geometry.py: AssertionError: resolver left the robot 0.5400 m from
  the obstacle, inside the 0.5500 m robot-obstacle collision threshold
tests/test_collision_geometry.py: AssertionError: a state the simulator has just declared
  resolved is still scored as a collision
```

### Smallest safe correction — `rvt_swarm/environment.py`

```python
min_d = max(2 * r_robot, self.ec.min_rr_distance)        # robot-robot
min_d = max(r_robot + r_obs, self.ec.min_ro_distance)    # robot-obstacle
```

Separation now settles at `0.42` and `0.56`, above both thresholds.

### Output after — all 6 geometry tests pass.

### Side effects

* **Contact dynamics change.** The resolver now activates at 0.40 m rather than
  0.36 m and pushes slightly harder, so trajectories differ from all previously
  recorded runs.
* Collision *events* become genuinely rare rather than persistent: previously a
  single contact left the pair permanently flagged for as long as they stayed
  under 0.40 m.
* **Alternative not taken:** lowering `min_rr_distance` to `2r` would also remove
  the inconsistency, but it redefines "collision" as physical overlap and discards
  the safety margin. Raising the resolution target preserves the metric's meaning.
  If you prefer the other direction, invert the change and re-run these tests.

---

## 3. Minimum commanded spacing equals the collision threshold

### Files and lines

| Location | Role |
|---|---|
| `rvt_swarm/environment.py:255` (pre-fix) | `min_scale = clip01(min_rr_distance / nominal_spacing)` |
| `rvt_swarm/controllers.py:28` (pre-fix) | the same expression, **duplicated** |
| `rvt_swarm/environment.py:157-198` | `desired_offsets()` uses `nominal_spacing * scale` |

`min_scale = 0.40 / 0.9 = 0.4444` ⇒ commanded spacing `0.9 × 0.4444 = 0.400 m`,
**exactly** `min_rr_distance`. The controller's own set-point sat on the failure
boundary, so any tracking error registered as a collision.

### Minimal reproducible example

```python
cfg = Config()
min_scale = cfg.env.min_rr_distance / cfg.env.nominal_spacing
print(cfg.env.nominal_spacing * min_scale, cfg.env.min_rr_distance)   # 0.4 0.4
```

### Output before

```
AssertionError: fully compressed formation commands 0.4000 m spacing, which is not above
  the 0.4000 m robot-robot collision threshold
AssertionError: assert 0.4 > 0.4
AssertionError: template mode=2 at scale=0.4444 commands a closest pair of 0.4000 m,
  at or inside the 0.4000 m threshold
```

### Smallest safe correction

A single shared accessor replaces the duplicated expression, with an explicit
margin (`rvt_swarm/config.py`):

```python
spacing_margin: float = 0.05

@property
def min_formation_scale(self) -> float:
    margin = float(getattr(self, "spacing_margin", 0.0))
    floor = (self.min_rr_distance + margin) / max(self.nominal_spacing, 1e-6)
    return float(min(max(floor, 0.0), 1.0))
```

`min_scale` now `0.5000` ⇒ commanded spacing `0.450 m > 0.400 m`. Both call sites
(`environment.py`, `controllers.py`) use the shared property, so they cannot drift
apart again — the test `test_expert_controller_uses_the_same_spacing_floor` pins
this.

### Output after — all 6 geometry tests pass, including the keep/line/split template check.

### Side effects

* **Teams compress less.** Minimum spacing rises from 0.40 m to 0.45 m, so the
  most constrained passages become harder. The `narrow_passage` gap is 1.5 m, which
  still admits a single file at 0.45 m spacing, but bottleneck behaviour will change.
* Verified consequence on a matched sample: see §6 — this fix (with §2) raises
  episode-wide collision-free from **0.175 → 0.863**.
* `spacing_margin = 0.05` is a **new free parameter** and must be reported in the
  experimental-settings table. It is not tuned; it is the smallest round value that
  makes the inequality strict.

---

## 4. Different evaluation seeds produce identical initial states

### Files and lines

| Location | Role |
|---|---|
| `rvt_swarm/environment.py:80-92` | `_spawn_agents()` — pure function of `(n_agents, scenario)`, consumes no randomness |
| `rvt_swarm/environment.py:50` | `goal = [world_size * 0.38, 0.0]` — a constant |
| `rvt_swarm/environment.py:94-122` | `_spawn_obstacles()` — correctly seeded |
| `latex/access.tex:1036-1037` | claims the seed rule gives "matched random starts" |

### Minimal reproducible example

```python
a = SwarmFormationEnv(Config()).reset(8, "narrow_passage", seed=1)
b = SwarmFormationEnv(Config()).reset(8, "narrow_passage", seed=99_999)
print(np.allclose(a["positions"], b["positions"]))   # True   <- identical starts
print(np.allclose(a["goal"],      b["goal"]))        # True   <- identical goal
print(np.allclose(a["obstacles"], b["obstacles"]))   # False  <- obstacles DO vary
```

### Output before

```
AssertionError: two different evaluation seeds produced byte-identical start positions;
  episodes are not independently initialised
AssertionError: only 0/19 seeds produced a distinct start configuration
```

### Smallest safe correction — `rvt_swarm/environment.py`

```python
spawn_jitter: float = 0.12                      # config.py
...
jitter = float(getattr(self.ec, "spawn_jitter", 0.0))
if jitter > 0.0:
    starts = starts + self.rng.uniform(-jitter, jitter, size=starts.shape).astype(np.float32)
```

Bounded well below `nominal_spacing = 0.9`: worst-case approach between adjacent
robots is 0.24 m, leaving ≥ 0.66 m. `test_spawn_randomisation_never_creates_an_initial_collision`
verifies this across all 4 scenarios × N ∈ {2,8,24} × 5 seeds.

### Output after — all 6 randomization tests pass, including same-seed reproducibility.

### Side effects

* **Every scenario layout changes.** `_spawn_agents` now draws from `self.rng`
  before `_spawn_obstacles`, so the obstacle stream shifts. All previously recorded
  episodes are superseded — acceptable, since §1–§3 already require a full re-run.
* Determinism is preserved: same seed ⇒ same episode
  (`test_same_seed_is_still_reproducible`).
* `spawn_jitter = 0.12` is a **new free parameter** and must be reported.
  Setting it to `0.0` exactly reproduces the old deterministic lattice.

### Remaining limitation, deliberately not fixed

**The goal is still constant at `(4.56, 0)` for every episode**, so all 1 200
evaluation episodes drive between the same two regions of the workspace.
Randomising it is a benchmark-design change, not a bug fix, and is out of scope
here. `test_goal_is_currently_fixed_documented_limitation` records the current
behaviour so that it fails loudly — prompting an update to this document — the
moment anyone changes it.

---

## 5. Unequal training and checkpoint-selection budgets

### Files and lines

| Location | Role |
|---|---|
| `rvt_swarm/config.py:44-47` | `epochs_gnn_only=120`, `epochs_instant_cert=120`, `epochs_rvt_swarm=300` |
| `rvt_swarm/train.py:18-25` | `epochs_for_model` |
| `rvt_swarm/train.py:210-217` | `should_run_rollout_validation` — fires every `rollout_val_interval=10` epochs |
| `rvt_swarm/train.py:224-250` | `maybe_record_rollout_candidate` — maintains the top-k pool |
| `rvt_swarm/train.py:516-536` | final top-k recheck, then `best_ckpt` is overwritten |

The epoch budget also sets the **model-selection** budget, because the best
checkpoint is chosen from the interval-gated validations.

### Minimal reproducible example

```python
from rvt_swarm.config import Config
from rvt_swarm.train import epochs_for_model, should_run_rollout_validation

cfg = Config()
for m in ("rvt_swarm", "gnn_only", "instant_cert"):
    n = epochs_for_model(cfg, m)
    events = sum(1 for e in range(1, n + 1) if should_run_rollout_validation(cfg, m, e, 0))
    print(f"{m:14s} epochs={n:3d}  validation events={events}")
# rvt_swarm      epochs=300  validation events=30
# gnn_only       epochs=120  validation events=12
# instant_cert   epochs=120  validation events=12
```

### Output before

```
AssertionError: unequal training budgets across learned methods:
  {'rvt_swarm': 300, 'gnn_only': 120, 'instant_cert': 120}
AssertionError: unequal checkpoint-selection budgets across learned methods:
  {'rvt_swarm': 30, 'gnn_only': 12, 'instant_cert': 12}
AssertionError: rvt_swarm gets 30 checkpoint-selection evaluations vs 12 for gnn_only
  (2.50x advantage)
AssertionError: learned methods are validated on different epoch schedules
```

**2.50× more checkpoint-selection opportunities for the proposed method**, against
a reported success margin over `gnn_only` of 0.005 (0.315 vs 0.310).

### Smallest safe correction — `rvt_swarm/config.py`

```python
epochs_gnn_only:     int = 300
epochs_instant_cert: int = 300
epochs_rvt_swarm:    int = 300
```

### Output after — all 5 budget tests pass; all three methods get 300 epochs and 30 validation events on an identical schedule.

### Side effects

* **Baseline training cost rises ~2.5×.** Early stopping (`patience = 40`) still
  terminates runs that stop improving, so 300 is a ceiling, not a mandate.
* The alternative — lowering `rvt_swarm` to 120 — would equalise more cheaply but
  handicaps the proposed method. Levelling *up* means no method is disadvantaged.
* **This does not address the deeper problem.** Checkpoints are still selected by
  rollout validation on `narrow_passage` + `dynamic_obstacles` at N ∈ {8,16,24}
  (`config.py:63-67`) — the *test* scenario generators and *test* team sizes, with
  only a seed offset separating them. Equalising the budget removes the asymmetry;
  it does not create a held-out split. See PART 8 / E4 of the audit.

---

## 6. Measured impact of the corrections

Matched grid, **80 episodes per method**: 2 baselines × 4 scenarios × N ∈ {4,8} ×
seeds 42–51. Configuration **B** disables spawn jitter so its layouts are identical
to **A**, isolating the geometry fixes from the randomisation fix.

| Config | `adaptive_formation` CF (terminal) | CF (episode-wide) | Success (terminal) | Success (episode-wide) |
|---|---|---|---|---|
| **A** pre-fix | 0.688 | 0.175 | 0.588 | 0.175 |
| **B** + geometry fixes (§2,§3), jitter off | 0.988 | 0.863 | 0.575 | 0.575 |
| **C** + spawn jitter (§4) | 0.988 | 0.788 | 0.675 | 0.650 |

| Config | `cbf_qp` CF (terminal) | CF (episode-wide) | Success (terminal) | Success (episode-wide) |
|---|---|---|---|---|
| **A** pre-fix | 0.700 | 0.175 | 0.513 | 0.150 |
| **B** | 0.988 | 0.863 | 0.500 | 0.488 |
| **C** | 0.975 | 0.838 | 0.500 | 0.500 |

> **These are not replacements for the paper's numbers.** The grid covers only
> N ∈ {4,8} and two non-learned baselines; the manuscript aggregates N = 2…24,
> where large teams are markedly harder. The table shows the *direction and
> magnitude of the distortions*, nothing more.

**The single most important observation.** The two errors act in **opposite
directions** on the same reported column:

* terminal-step sampling **inflates** it (0.175 → 0.688 episode-wide vs reported, config A);
* the geometry artifact **deflates** it (0.688 → 0.988 reported, A → B).

In the pre-fix code they partially cancel, and the cancellation is
method-dependent and scenario-dependent. **No post-hoc correction of the published
tables is possible, and the reported ranking between methods is not recoverable.**
The benchmark must be re-run.

---

## 7. Corrections and retractions

Per the instruction to retract or correct anything that failed to reproduce:

**Nothing is retracted. All five findings reproduced.** Two adjustments:

1. **Corrected — Finding 3 is "equal to", not "smaller than".** The audit's
   PART 1 said the commanded spacing "is exactly the collision threshold", which is
   right, but the checklist phrasing "equal to or smaller than" invited the reading
   that it could be smaller. Measured: `0.9 × (0.40/0.9) = 0.400 m` exactly, never
   below. The defect is that the inequality is not *strict* — a set-point on the
   boundary rather than inside the infeasible region. Real, and slightly milder
   than the loosest reading.

2. **Refined — the direction of the Finding 1 distortion.** The audit stated that
   the terminal-step convention invalidates the safety column but did not say which
   way it errs. Measured: it **inflates** both collision-free (0.175 → 0.688) and
   success (0.175 → 0.588) on the §6 grid, and 44.7 % of episodes scored as
   `Success` across the 640-episode scan contain a collision. The reported numbers
   are optimistic, not pessimistic. The audit's claim that the geometry artifact
   explains the low reported collision-free rates also holds (terminal CF rises
   0.688 → 0.988 when the geometry alone is fixed).

3. **Withdrawn concern, raised by me during this work.** I anticipated that adding
   fields to `EnvConfig` would break `Config` objects unpickled from existing
   checkpoints (`train.py` stores the whole config in every checkpoint). It does
   not: dataclass defaults are class attributes, so instances lacking the field in
   `__dict__` still resolve it. Verified directly. The `getattr` fallbacks were
   retained as defensive coding, not because a defect was found.

## 8. What these fixes do *not* address

Out of scope here, still open from the audit:

* Centralised topology selection via a team-wide mean pool (`models.py:270-283`).
* Baseline fidelity — the paper's `ORCA` / `CBF-QP` / `MPC` rows.
* Single training seed; `cfg.train.seed` still drives network init, dataset
  generation, **and** evaluation seeds simultaneously.
* Checkpoint selection on the test distribution (see §5 side effects).
* Absence of any held-out generalization split.
* `deadlock`, `form_ok`, and `irreversible_collapse` remain terminal-step metrics.
* The fixed goal position (§4).
