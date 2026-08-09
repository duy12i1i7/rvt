# Phase 9C-RB17 — Generation Identity, Schema Binding and Contract Versioning

**Result: the generation contract is fully versioned and bound. Verdict C.**

RB-17 separates three identities that were previously one, freezes what happens
when the expert legitimately produces nothing, proves the repaired model's frame
context survives serialization, and versions the budget and manifest — all
without authorizing a single scientific row.

| artifact | hash |
|---|---|
| scientific row identity V2 | `f77cc03653a0982ff3c79a1d2772e6193bc26d34df750e29b342d479a918cc20` |
| candidate evaluation identity V2 | `d334260157831f157cd5817cc5ae1e266eec59d69c9c6d5bf8cec6dc7301f6ef` |
| execution attempt identity V1 | `edf1f71ea74ebb1bea144f7f754f647969c59af165b82ae6bf40134cf759b923` |
| generation disposition contract V1 | `a89da469367d0e5c0a25c2026a0f2a69481640c76f90e262ac61e61d44989cf6` |
| residual supervision row schema V2 | `ecf9ebbd0f8f350df0a2daa44f0d3096874b20b5d7952734b43377abde423a30` |
| generation budget V2 | `fbdf3b5e8c7607e9381337295d598244fb76e8b1dc855566c7bb23b00809d3f3` |
| residual job manifest V2 | `878a81c9a83fa0a390ac8c5f508baeb53b4964398575624066c5d1fb72fff10b` |
| **RB-17 generation-contract composite** | `bba1aee0430bc540f20d010b923696b5b1c51d4bfb1d92d2fa21daf2e6242da8` |

## Three identities

**Scientific row** — `study, split, family, layout_sha256, team_size, episode_id,
timestep, robot_id, topology_id, graph_fingerprint, residual_expert_spec_sha256`.
The first five are the frozen residual cell, the next five the frozen dense-row
canonical order, the last the label contract. **Candidate index is absent**, and
passing one raises rather than being ignored — the nine candidates are *how* the
expert decides, not nine observations.

**Candidate evaluation** — the row id plus `candidate_index`, `replica_index` and
`matched_stream_identity_sha256`. Nine candidates → nine distinct ids, verified
on a real producer run.

**Execution attempt** — `chunk_id, worker_id, attempt_index, task_range`. Purely
operational, and disjoint from both scientific keys. **Scientific identity is
independent of execution chunking**: the same three decision states, evaluated in
two different partitions, produced identical row ids, candidate ids, matched
streams and targets after canonical sort, while the execution ids differed.

**Retry.** Semantic retries 0, infrastructure retries ≤ 1, denominator delta 0,
randomness never resampled. A simulated retry reproduced the row id, all nine
candidate ids, the matched streams and the target; only the attempt id moved.

## No-eligible is a disposition, not a failure

`LABELED` · `NO_ELIGIBLE_ACTION` · `EXECUTION_INVALID` · `INFRASTRUCTURE_FAILURE`
— four categories, hard-separated. No separate "valid method failure" category
was invented: a valid task failure is already a legitimate negative *label* under
the frozen invalid-record contract.

`NO_ELIGIBLE_ACTION` emits **zero** target rows and **still counts** in the
attempted-state denominator. It is never converted into a zero, clipped, rotated,
base-action or fallback target — the row builder refuses to construct a row for
any non-`LABELED` disposition. Re-run against the qualified RB-15 state where all
nine candidates are safety-infeasible: disposition `NO_ELIGIBLE_ACTION`, target
rows 0, attempted 1, no-eligible 1, execution-invalid 0, infrastructure 0.

Because infrastructure failures are retried rather than scientific outcomes, they
are excluded from the denominator. So the eventual dataset row count is allowed
to be *smaller* than the number of attempted decision states, and the difference
is visible rather than silent.

## Model V2 serialization — the hard gate

The frozen `DenseActionSample` references its features only by `feature_sha256`
and carries no frame context, so **it alone cannot rebuild a model V2 input**.
The additive binding `rvt-residual-supervision-row/v2` adds exactly two things
and no scientific information: `mission_orientation_cos_sin` (shape `[2]`, from
`RobotLocalEgoGraph.mission_orientation_cos_sin`, provenance
`LOCAL_MISSION_CONFIGURATION`, never recomputed from layout ids and never read
from hidden simulator state) and the ego-graph record content hash.

Round trip through serialize → deserialize → model: orientation **exact**, record
hash stable, **residual outputs identical**, **recoverability logits identical**.
Changing only the orientation moves the residual output and leaves the
recoverability logits untouched, confirming the context reaches only the residual
head. The target field stays `residual_target_world_acceleration`, `[2]`, m/s²,
WORLD, and round-trips a non-symmetric mixed-sign vector with no swap, sign
change, rotation or scaling.

The nine `LocalActionEvaluation` records go to a **generation audit sidecar**
keyed by candidate evaluation id — not into the training row, which the model
never reads them from, and not discarded, which would lose "why this candidate
won".

## Budget and manifest

Budget V2 extends V1 without overwriting it: every V1 source count is preserved,
and V2 adds candidate count 9, compute upper bound **4,824,000 evaluations**, and
the stored cap **536,000 rows** — explicitly not the same quantity. The
historical 1800-second residual cell timeout is recorded as **not authoritative
for V2**; `RESIDUAL_V2_GENERATION_TIMEOUT = PENDING_RB21_PERFORMANCE_QUALIFICATION`
and no replacement, worker count or chunk size is chosen. The RB-15 canary
benchmark is carried as `INPUT_TO_RB21`, explicitly not promoted to a capacity
guarantee.

Manifest V2 references the full current chain and holds
`NOT_AUTHORIZED_PENDING_RB18_RB21`; the historical manifest is untouched.

## Preflight

Preflight now validates all nine V2 contracts by canonical hash and semantics —
and, more importantly, **rejects** each stale one: a mission-frame model
declaration presented as current, a schema that drops the orientation, a
MISSION target frame, a row identity that admits `candidate_index`, the 1800 s
timeout presented as authoritative, a candidate count other than nine, disabled
augmentation flipped on, an unknown disposition vocabulary, and an authorized
execution status. Eight negative cases and one missing-contract case are tested.
Parsing the contracts is not authorization.

## Isolation

Recoverability rows 0, residual rows 0, shards 0, FD24 checkpoints 0, optimizer
states 0, training operations 0, final-test accesses 0, Study A N=24 accesses 0.
Every fixture is `RUNTIME_CONFORMANCE_ONLY` and touches no official counter.
