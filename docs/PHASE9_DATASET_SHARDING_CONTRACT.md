# Phase 9 Dataset Sharding Contract

No recoverability or residual shard was created because there are no valid
records. An empty shard would incorrectly imply a completed dataset unit.

The enforced reader boundary requires a shard descriptor to declare
`completion_state=COMPLETE`, the referenced file to exist and its SHA-256 to
match. Partial, missing and corrupted shards fail explicitly. Dataset loading
also fails before shard access unless the dataset manifest status is
`VALID_FROZEN`.

Current shard counts:

- recoverability: 0;
- residual action: 0;
- Study A N=24 sealed: 0.

No group crosses a split because no record or shard exists. Planned grouping is
checked separately in the authoritative job manifest.

