# Evaluation Protocol v2 — Verification Report

Second evaluation-validity audit, covering Tasks 1–7. Completed **before** any
smoke benchmark, as instructed.

**Nothing in this report is a performance claim.** No benchmark was run, no model
was retrained, no method was compared, and no old checkpoint was used for any
conclusion.

Schema: `evaluation_schema_version = 2`.
Branch: `fix/benchmark-validity`.

---

## 1. Complete test output

```
$ .venv/bin/python -m pytest tests/ -q
....................................................................... [ 72%]
............................                                            [100%]
99 passed in 1.70s
```

Breakdown by file:

| Test file | Tests | Covers |
|---|---|---|
| `test_all_episode_metrics.py` | 17 | Task 1 — semantics A–H per metric |
| `test_collision_geometry.py` | 6 | resolver / commanded-spacing geometry |
| `test_episode_metrics.py` | 10 | episode-wide safety accounting |
| `test_equal_model_selection_budget.py` | 19 | Task 5 — budget parity |
| `test_no_test_set_leakage.py` | 11 | Task 2 — split separation |
| `test_randomization.py` | 6 | seeded initial states |
| `test_result_schema_version.py` | 8 | Task 6 — schema gating |
| `test_seed_independence.py` | 9 | Task 3 — seed roles |
| `test_training_budget.py` | 5 | epoch/validation-call parity |
| pre-existing suite | 8 | baselines, dataset, aggregation — **no regressions** |

### Pre-fix condition probes

New capabilities cannot be "red before" in the usual sense — the modules did not
exist, so a pre-fix run is an import error, not a failure. Instead each defect's
**pre-fix configuration is reconstructed and shown to be rejected**:

```
[1] pre-fix validation config (test team sizes 8/16/24) reaching checkpoint selection:
    CAUGHT -> rollout_validation_summary: team sizes [8, 16, 24] belong to the final
              test sweep [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]

[2] pre-fix overloaded seed (one seed drives model init AND eval episodes):
    legacy seed 42 -> c3348c685bd5cd08 | legacy seed 43 -> 6d6f84783eb97c74
    identical: False  <-- changing the training seed changed the test episode
    schema-2 model_seed 0 -> 9ce306467f5d03e6 | model_seed 7 -> 9ce306467f5d03e6
    identical: True   <-- test set now independent of model seed

[3] pre-fix unequal epoch budgets:
    {'rvt_swarm': (300, 30), 'gnn_only': (120, 12), 'instant_cert': (120, 12)} -> equal: False
    schema-2:  {'rvt_swarm': (300, 30), 'gnn_only': (300, 30), 'instant_cert': (300, 30)} -> equal: True
```

The Task-1 metric tests *are* genuinely red-before-green-after; see
`docs/BENCHMARK_BUG_VERIFICATION.md` (19 failed → 33 passed).

---

## 2. Changed files

| File | Change |
|---|---|
| `rvt_swarm/metrics.py` | **new** — `EpisodeAccumulator`, `EVALUATION_SCHEMA_VERSION` |
| `rvt_swarm/splits.py` | **new** — split specs, seed namespaces, leakage guards, episode signatures |
| `rvt_swarm/config.py` | `SeedConfig`; validation team sizes; `hyperparameter_trials`; `seed_config()` |
| `rvt_swarm/evaluate.py` | episode aggregation; split routing; leakage guards; expanded `SUMMARY_KEYS` |
| `rvt_swarm/environment.py` | `min_rr_clearance` / `min_ro_clearance` in `compute_metrics` |
| `rvt_swarm/safety.py` | optional `stats` dict recording filter trigger / activation / Δu |
| `rvt_swarm/policy_runtime.py` | threads `safety_stats` through to the evaluator |
| `rvt_swarm/train.py` | `model_seed` for init and loaders; `training_budget_report` |
| `rvt_swarm/dataset.py` | `training_data_seed`; training seeds mapped into the train namespace |
| `run_experiments.py` | schema stamping (`save_json`), `require_schema_version`, `load_json`; multi-seed varies `model_seed` only |
| `tests/` | 5 new files (64 new tests) |
| `docs/` | 5 new documents |
| `results/legacy_pre_metric_fix/`, `checkpoints/legacy_pre_metric_fix/` | quarantine + READMEs |
| `results/geometry_parameter_validation.csv`, `results/training_budget_report.json` | machine-readable outputs |

---

## 3. Metric definitions

Full table in [`EPISODE_METRIC_SPECIFICATION.md`](EPISODE_METRIC_SPECIFICATION.md).
Summary of what each metric now is:

| Semantics | Metrics |
|---|---|
| **A** terminal | `form_ok`, `form_rms`, `rr_collision`, `ro_collision`, plus every `*_terminal` alias |
| **B** conjunction | `collision_free`, `success` |
| **C** event latch | `goal_reached`, `deadlock`, `irreversible_collapse` |
| **D** count | `robot_robot_collision_steps`, `robot_obstacle_collision_steps`, `topology_switches`, `safety_filter_activations` |
| **E** min/max | `min_rr_clearance`, `min_ro_clearance`, `form_rms_max`, `rr_collision_max`, `ro_collision_max` |
| **F** time average | `form_rms_mean`, `stall_rate` |
| **G** % of episode time | `time_in_formation_tube`, `safety_filter_activation_rate` |
| **H** first passage | `completion_time`, `first_goal_step` (+ `completion_time_censored`) |

**Three definitions changed, none silently.** `goal_reached`, `deadlock`, and
`irreversible_collapse` became latches; each keeps its old value as
`*_terminal`. Expected impact: `goal_reached` unchanged (termination fires on
first contact); **deadlock and collapse rates will rise**.

`safety_filter_activations` is entirely new — the filter's activation was
**never recorded**, so the ablation "− progress safety filter" was previously
reported without any measurement of how often the filter did anything.

---

## 4. Split definitions

| Split | Scenarios | Team sizes | Seed namespace |
|---|---|---|---|
| train | all four | 2, 4, …, 24 | `[10_000_000, 20_000_000)` |
| validation | narrow_passage, dynamic_obstacles | **5, 11, 21** (odd — disjoint from test) | `[20_000_000, 30_000_000)` |
| final test | all four | 2, 4, …, 24 | `[30_000_000, 40_000_000)` |

Checkpoint selection runs on validation only, enforced at the single chokepoint
`rollout_validation_summary`. Details and the pre-fix trace:
[`DATA_SPLIT_AND_CHECKPOINT_PROTOCOL.md`](DATA_SPLIT_AND_CHECKPOINT_PROTOCOL.md).

---

## 5. Seed behaviour

Six explicit roles (`SeedConfig`): `model_seed`, `training_data_seed`,
`validation_seed`, `final_test_seed`, `counterfactual_rollout_seed`,
`environment_noise_seed`.

Proven by SHA-256 signatures over initial states, goals, obstacles and obstacle
velocities (`splits.episode_signature`):

| Property | Test |
|---|---|
| `model_seed` does not change test episodes | `test_changing_model_seed_does_not_change_final_test_episodes` |
| `training_data_seed` does not change test episodes | `test_changing_training_data_seed_does_not_change_final_test_episodes` |
| `final_test_seed` does not change model init | `test_changing_final_test_seed_does_not_change_model_initialisation` |
| `final_test_seed` *does* re-draw the test set | `test_changing_final_test_seed_does_change_final_test_episodes` |
| all methods get identical test episodes | `test_all_methods_receive_identical_test_episodes` |
| all training seeds share one test set | `test_all_training_seeds_share_one_final_test_set` |
| validation and test never collide | `test_validation_and_test_signatures_never_collide` |
| the signature is not blind to any field | `test_signature_is_sensitive_to_every_initial_condition` |

`counterfactual_rollout_seed` and `environment_noise_seed` are **declared but not
yet consumed**: rollout labelling is currently deterministic (M = 1) and no
sensor/actuation noise model exists. They are reserved for the calibration and
robustness work and are listed as open items below rather than presented as done.

---

## 6. Final geometry parameters

| Parameter | Value | Decisive criterion |
|---|---|---|
| `spacing_margin` | **0.05 m** | C2 — must absorb ≥ ⅓ of one control step of travel (`v_max·Δt/3 = 0.045 m`); C4 selects the smallest such value |
| `spawn_jitter` | **0.12 m** | C8 — ≤ 15 % of `nominal_spacing`; C9 selects the largest such value |

**All 16 swept combinations were geometrically feasible** (3 072 resets: zero
initial collisions, zero resolver interventions, zero out-of-bounds spawns), so
the sweep did **not** discriminate. The values rest on criteria C1–C9, fixed
before the sweep ran. Neither was chosen with reference to any task metric.
Full derivation: [`GEOMETRY_PARAMETER_VALIDATION.md`](GEOMETRY_PARAMETER_VALIDATION.md);
raw data: `results/geometry_parameter_validation.csv`.

---

## 7. Training-budget equality

All learned methods: 300 epochs, 30 validation calls, top-5 checkpoint pool,
patience 40, min-delta 1e-4, identical selection rule, 0 hyperparameter trials,
identical validation configuration. Machine-readable:
`results/training_budget_report.json`. Details:
[`TRAINING_BUDGET_PROTOCOL.md`](TRAINING_BUDGET_PROTOCOL.md).

---

## 8. Legacy invalidation

`results/legacy_pre_metric_fix/` and `checkpoints/legacy_pre_metric_fix/` created
with READMEs stating why the artifacts are invalid, which commit produced them
(`fab222b` and earlier), which defects affected them, and that they must not be
mixed with corrected results. **Nothing was deleted.**

Enforcement: `save_json` stamps every result file; `require_schema_version`
raises `SchemaVersionError` on unstamped or foreign files; the multi-seed
aggregator loads through it. Legacy files carry no version field and are rejected
on that basis. Covered by 8 tests.

---

## 9. Known remaining limitations

Protocol-level, still open:

1. **Splits share scenario generators.** Leakage is prevented; generalization is
   not demonstrated. Unseen layout families and unseen team sizes remain a
   separate axis (audit E4).
2. **Validation is a mild extrapolation** (odd team sizes never seen in training),
   chosen for guaranteed disjointness. It makes selection conservative and must be
   described as such.
3. **Architecture selection cannot be guarded.** Any choice informed by
   previously seen test numbers is undetectable leakage. From here, architectural
   decisions must be justified on validation evidence and recorded.
4. **Single training seed still in force.** The 5-seed plan is declared in the
   budget report but has not been run.
5. **`counterfactual_rollout_seed` / `environment_noise_seed` are unused.**
6. **`form_ok` remains the formation term in `success`.** Deliberate: changing the
   headline criterion is an authors' scientific decision, not a bug fix.
   `time_in_formation_tube` is reported alongside it.
7. **`ms_per_step` still includes checkpoint I/O** for learned methods
   (`evaluate.py` reloads the checkpoint inside the timed loop when no model is
   passed). Runtime numbers remain unusable until this is fixed.
8. **Visualization helpers still use un-namespaced `seed=42`.** No selection or
   reported-metric impact, but inconsistent.
9. **Deadlock/collapse rates will rise** under the latch semantics. Expected and
   documented, but it means these columns are not comparable to any previously
   reported number.

Scientific issues from the original audit that this work does **not** touch:
centralized topology selection via team-wide mean pooling; baseline fidelity for
the ORCA / CBF-QP / MPC rows; absence of recovery-score calibration; and the
absence of any held-out generalization result.

---

## 10. Status

Tasks 1–7 complete. The evaluation protocol is now internally consistent, its
semantics are documented and tested, and the legacy artifacts are quarantined
rather than deleted.

**No benchmark has been run and no performance claim is made.** The corrected
protocol has not yet produced a single result table. Stopping here for approval
before running the smoke benchmark, as instructed.
