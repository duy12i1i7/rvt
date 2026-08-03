# Phase 9 Dataset Deduplication Report

The planner rejects duplicate semantic IDs independently for all 3,120 source
jobs, 15,300 event jobs, 42,840 candidate-replica jobs and 340 residual-cell
jobs. The committed manifest passes those uniqueness checks.

No data record was emitted, so exact-record and semantic-record duplicate
counts are both 0 over an empty record set. This does not claim that downstream
record deduplication was exercised. Conflicting canonical record IDs remain a
loader/shard-finalization requirement for a future authorized generation run.

