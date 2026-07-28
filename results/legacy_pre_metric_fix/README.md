# Legacy results — generated under invalid evaluation semantics

**Do not use anything in this directory, or in
`checkpoints/legacy_pre_metric_fix/`, for publication, comparison, or any
conclusion. Do not mix these files with corrected results.**

Nothing has been deleted. These artifacts are retained for provenance and for
before/after comparison only.

## What to put here

Any result table, JSON/CSV summary, figure, or checkpoint produced **before**
`evaluation_schema_version = 2`, including everything behind the numbers in the
IEEE Access submission (Access-2026-23555) and its post-rejection revision.

## Code version that generated them

Commit `fab222b` ("Fix PyTorch CUDA wheel version to 2.6.0+cu124") and earlier —
i.e. any commit before `fix/benchmark-validity`. These carry no
`evaluation_schema_version` field at all, which is how the loader identifies them.

## Why they are invalid

Five defects, each reproduced by unit test in
[`../../docs/BENCHMARK_BUG_VERIFICATION.md`](../../docs/BENCHMARK_BUG_VERIFICATION.md):

1. **Terminal-step safety accounting.** `collision_free` and `success` were the
   final timestep's values, not episode-wide. 56.7 % of episodes were reported
   collision-free despite a mid-episode collision; 44.7 % were scored `Success`
   despite one. **Inflates the reported numbers.**
2. **Collision threshold unreachable by the simulator.** Overlap resolution
   separated bodies to 0.380 m / 0.540 m while the metric scored against
   0.400 m / 0.550 m, so every resolved contact stayed flagged.
   **Deflates the reported numbers.**
3. **Commanded spacing on the failure boundary.** The fully compressed formation
   template commanded exactly 0.400 m, equal to the collision threshold.
4. **Deterministic start states.** Every seed shared one initial configuration,
   so episode-to-episode variation came only from obstacle layout.
5. **Unequal selection budgets.** 300 vs 120 epochs gave the proposed method 30
   checkpoint-selection evaluations against the baselines' 12 (2.50×), for a
   reported success margin of 0.005.

Additionally, under schema 1 the checkpoint-selection path used the **test**
scenario generators and team sizes (`narrow_passage`, `dynamic_obstacles` at
N ∈ {8,16,24}) separated from the reported episodes only by a seed offset.

## Why they cannot be corrected post hoc

Defects 1 and 2 push in **opposite directions on the same reported column**, and
the degree of cancellation depends on method, scenario, and team size. A matched
80-episode measurement is in the verification report. There is therefore no
scaling, offset, or re-derivation that recovers the corrected values — and the
**ranking between methods is not recoverable** either. The benchmark must be
re-run from scratch under schema 2.

## Enforcement

`run_experiments.py::require_schema_version` raises `SchemaVersionError` on any
result file lacking `evaluation_schema_version` or carrying a different value, so
legacy files cannot silently enter an aggregation. Covered by
`tests/test_result_schema_version.py`.
