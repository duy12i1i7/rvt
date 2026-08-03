# RVT Data Provenance Contract

Future schemas are `rvt-recoverability-dataset/v1` and
`rvt-residual-action-dataset/v1`, wrapped by `rvt-data-provenance/v1`.

Every dataset records source commit, mechanical-scope hash, topology-registry
schema, approved online-scope hash, ego schema and feature hash, model schema,
runtime/controller/safety/protocol hashes, scenario/split manifest hashes, seed
namespace, generation command/timestamp/version, row/event/episode counts,
per-file SHA-256, aggregate SHA-256 and exact experiment-protocol SHA-256.

The primary recoverability candidate list must be exactly `(COMPACT,LINE)`.
KEEP is rejected even if a compatibility checkpoint vocabulary contains it.
Loaders reject wrong feature/scope hashes, split mismatch, missing provenance,
invalid per-file or aggregate hash, protocol mismatch and final-test rows in
training or validation. Rejection is structured and never repaired by guessing
or migration during a scientific run.

Phase 9 may generate data only when its output manifest references the exact
Phase 8 experiment-protocol hash. Regeneration under another commit or config
creates a different dataset identity and cannot overwrite the original.
