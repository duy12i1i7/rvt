# Data Split and Checkpoint-Selection Protocol

Implementation: `rvt_swarm/splits.py`.
Tests: `tests/test_no_test_set_leakage.py`, `tests/test_seed_independence.py`.

## 1. Trace: how checkpoints were selected before

```
train_model                              (rvt_swarm/train.py)
 └─ should_run_rollout_validation        every rollout_val_interval = 10 epochs
     └─ rollout_validation_summary       runs EPISODES and computes METRICS
         ├─ rollout_validation_score  ──► early stopping (patience counter)
         ├─ rollout_validation_key    ──► "improved?" comparator, best_ckpt write
         └─ maybe_record_rollout_candidate ──► top-k candidate pool (k = 5)
 └─ recheck_rollout_candidates           re-evaluates the top-k, overwrites best_ckpt
```

Every one of those is a **model-selection** path. Under the pre-fix
configuration each of them consumed:

| Property | Pre-fix value | Also the reported test configuration? |
|---|---|---|
| scenarios | `narrow_passage`, `dynamic_obstacles` | **yes** — both are reported scenarios |
| team sizes | `8, 16, 24` | **yes** — all three are in the reported sweep |
| seeds | `cfg.train.seed + 50_000 + …` | same generator, offset by a constant |
| metrics | `success`, `goal_reached`, `collision_free`, `form_ok` | **yes** — the reported headline metrics |

So checkpoints were ranked by the reported metrics, on the reported scenario
generators, at reported team sizes, separated from the reported episodes only by
a seed offset. There was **no held-out split of any kind**. Hyperparameters were
not tuned (`hyperparameter_trials = 0`), so that channel was clean; architecture
selection was manual and is not automated here.

## 2. The three splits

| Split | Scenarios | Team sizes | Seed namespace | Used for |
|---|---|---|---|---|
| **train** | all four generators | 2, 4, …, 24 | `[10_000_000, 20_000_000)` | expert-episode generation, gradient steps |
| **validation** | `narrow_passage`, `dynamic_obstacles` | **5, 11, 21** | `[20_000_000, 30_000_000)` | early stopping, checkpoint ranking, top-k re-evaluation |
| **final test** | all four generators | 2, 4, …, 24 | `[30_000_000, 40_000_000)` | reported results only, after the checkpoint is frozen |

Two independent separations:

1. **Disjoint seed namespaces.** `episode_seed(split, …)` maps every episode into
   its split's block, and `seed_split(seed)` inverts it. A seed uniquely
   identifies its split, so leakage is detectable rather than merely discouraged.
2. **Disjoint validation team sizes.** Validation uses odd team sizes; the test
   sweep is entirely even. A validation episode therefore cannot coincide with a
   test episode even if a seed were mis-constructed.

## 3. Enforcement

`rollout_validation_summary` — the single chokepoint through which every
selection path runs — calls:

```python
assert_validation_config(scenarios, team_sizes, context=...)   # rejects test team sizes
assert_no_test_seeds(episode_seeds, context=...)               # rejects test seeds
```

Both raise `TestSetLeakageError`. The pre-fix configuration is rejected:

```
[1] pre-fix validation config (test team sizes 8/16/24) reaching checkpoint selection:
    CAUGHT -> rollout_validation_summary: team sizes [8, 16, 24] belong to the final
              test sweep [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]
```

`evaluate_method(..., split=TEST)` is the only function that touches the test
split, and it is called only after training returns a frozen checkpoint.

## 4. Requirements checklist

| Requirement | Status | Evidence |
|---|---|---|
| Validation is used for checkpoint selection | met | `rollout_validation_summary` draws `split=VALIDATION` |
| Final test never used for early stopping | met | guard raises; `test_checkpoint_selection_rejects_test_team_sizes` |
| Final test never used for checkpoint ranking | met | same chokepoint |
| Final test never used for top-k re-evaluation | met | `recheck_rollout_candidates` → same function |
| Final test never used for hyperparameter tuning | met, vacuously | `hyperparameter_trials = 0` |
| Final test never used for architecture selection | **not enforceable in code** | manual decision; see limitations |
| Final test seeds fixed and shared across methods | met | seeds depend only on `final_test_seed`; `test_all_methods_receive_identical_test_episodes` |
| Test results produced only after the checkpoint is frozen | met by construction | `evaluate_method` runs post-training |

## 5. Known limitations, stated plainly

- **The three splits share the same four scenario generators.** Only layout
  instances (and validation team sizes) differ. This protocol prevents *leakage*;
  it does not by itself establish *generalization*. Unseen scenario families and
  unseen team sizes are a separate axis — see PART 8 / E4 of the audit — and the
  headline claims must not describe these splits as a generalization result.
- **Validation uses odd team sizes that never appear in training.** This makes
  validation a mild extrapolation rather than a matched held-out sample, which
  makes it a conservative (harder) selection signal. That is a deliberate
  trade-off for guaranteed disjointness, and it should be stated in any
  methodology section.
- **Architecture selection cannot be policed by a guard.** Any architectural
  decision informed by previously observed test numbers is leakage that no test
  can detect. Every architectural choice from here must be justified on
  validation evidence and recorded.
- **Visualization helpers still use un-namespaced `seed=42`** (`run_experiments.py`
  GIF generation). These feed no selection or reported metric, but they should be
  migrated for consistency.
