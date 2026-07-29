# Layout Split Protocol

Implementation: `rvt_swarm/layouts.py` · Tests: `tests/test_layout_split_disjointness.py`

## 1. The defect this replaces

Under Evaluation Protocol V2 the three splits owned **disjoint seed namespaces**
but **shared the four scenario generators**. Only layout *instances* differed. So
the protocol prevented episode leakage but could not demonstrate generalization,
and `DATA_SPLIT_AND_CHECKPOINT_PROTOCOL.md` §5 listed that as a known limitation.
The Method Audit's recovery pilot then failed its own title condition for exactly
this reason: there were held-out *seeds*, never held-out *layouts*.

## 2. What replaces it

Every layout is a **named, hashable geometry** with an explicit ID:

```
train_keep_open_001   val_line_corridor_002   test_split_around_001
{split}_{family}_{index}
```

45 layouts: 3 splits × 7 families × 2–3 instances.

### Disjointness is by construction, not by inspection

Each split draws from **disjoint discrete parameter sets**. Nothing is sampled;
the generator is deterministic, so two splits cannot coincide by chance.

| Parameter | train | val | test |
|---|---|---|---|
| Gate width `W` (m) | 1.40, 1.70, 2.00 | 1.50, 1.80, 2.10 | 1.60, 1.90, 2.20 |
| Outer wall half-separation (m) | 1.55, 1.75 | 1.60, 1.80 | 1.65, 1.85 |
| Gate x-position (m) | −0.30, +0.30 | −0.20, +0.20 | −0.10, +0.10 |
| Open-field lateral offset (m) | 2.30, 3.10 | 2.45, 3.25 | 2.60, 3.40 |

Every value is unique to its split, so **no obstacle coordinate set can recur**
across splits. All three splits keep the same start centre and goal, because the
*task* must be constant for the comparison to mean anything; the **geometry** is
what differs.

## 3. Geometry hash

`Layout.geometry_hash()` = SHA-256 over

- obstacle coordinates, rounded to 1e-6 and **lexicographically sorted** (so a
  reordering of the same obstacles hashes identically — same geometry, same hash);
- the goal;
- the start centre.

Truncated to 24 hex characters. Measured: **45 layouts → 45 unique hashes, zero
shared across splits.**

## 4. Enforcement

`tests/test_layout_split_disjointness.py` fails if:

| Test | Catches |
|---|---|
| `test_no_geometry_hash_is_shared_across_splits` | the same geometry in two splits |
| `test_no_shared_fixed_obstacle_coordinates_across_splits` | reused obstacle sets, independent of hashing |
| `test_layouts_differ_by_geometry_not_only_by_start_randomisation` | a split that is another split's maps with a different start |
| `test_geometry_hashes_are_unique_within_each_split` | accidental duplicates inside one split |
| `test_geometry_hash_is_sensitive_to_geometry` | a hash blind to coordinates, which would make the others vacuous |
| `test_geometry_hash_is_order_invariant` | a hash that treats reordering as new geometry |
| `test_layouts_are_loadable_and_produce_valid_initial_states` | spawn collisions, out-of-bounds starts, spawns inside obstacles |

## 5. Usage rules

| Split | Used for | Never used for |
|---|---|---|
| **train** | model training, dataset generation | any selection or reporting |
| **val** | checkpoint selection, threshold choice, architecture choice, **scenario qualification** | reporting final results |
| **test** | reported results only, after the checkpoint is frozen | scenario design, scenario tuning, threshold choice, architecture choice, any inspection during method design |

**Final-test layouts have not been loaded, measured, or examined during this
task.** Scenario qualification (Task 5) reads `build_layouts("val")` only.

## 6. Interaction with Evaluation Protocol V2

Unchanged: the seed namespaces, the leakage guards in `rollout_validation_summary`,
and all metric semantics. Layouts are an **additional, orthogonal** axis of
separation — episodes are now disjoint in *both* seed and geometry.

`SwarmFormationEnv.reset(..., layout=...)` is additive: with `layout=None` the
procedural generators behave exactly as before, so every Protocol V2 result
remains reproducible.

## 7. Limitations

- Start centre and goal are common to all splits by design; only obstacle geometry
  varies. A stricter protocol would also vary the goal.
- 2–3 instances per family per split is small. Instance count, not geometry
  diversity, is the current limit on statistical power.
- The families are hand-designed from clearance algebra. They are not a random
  sample of any natural distribution, and no claim of representativeness is made.
