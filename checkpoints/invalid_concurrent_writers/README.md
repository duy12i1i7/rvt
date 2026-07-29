# Invalid checkpoints — concurrent multi-writer corruption

**Never use anything that lands in this directory for training, evaluation, or
any scientific conclusion.**

## Status of the known incident: artifacts were DELETED, not quarantined

This directory is **empty by necessity**. The corrupted checkpoints it was
created to hold no longer exist: they were removed with `rm -rf
checkpoints/method_audit` during the method audit, *before* the instruction to
quarantine them was issued. They cannot be recovered, and nothing was moved here.

This README records the incident so the loss is documented rather than silent.

## What happened

While preparing the Task 1 audit checkpoints, a helper script written to `/tmp`
lacked an `if __name__ == "__main__":` guard. `generate_dataset` uses
`multiprocessing.get_context("spawn")` (`rvt_swarm/dataset.py:396`), and every
spawn worker re-imports the main module — so each worker re-executed the whole
training script. `pkill` removed the parent but not the already-detached
descendants.

The result was **four concurrent training processes writing to the same
checkpoint directory** (`checkpoints/method_audit/`). The evidence was four
independent `### DONE` markers in one log with four different recheck scores:

```
[rvt_swarm] rollout recheck selected epoch 30 with rollout_recheck_score=0.2271
[rvt_swarm] rollout recheck selected epoch 30 with rollout_recheck_score=0.4396
[rvt_swarm] rollout recheck selected epoch 30 with rollout_recheck_score=0.4590
[rvt_swarm] rollout recheck selected epoch 30 with rollout_recheck_score=0.4396
```

## Why those checkpoints were unusable

- `torch.save` from several processes to one path gives whichever write finished
  last, with no guarantee of a consistent file.
- The provenance stamp (`git_commit`, `evaluation_schema_version`, `epoch`) could
  not identify which run produced the surviving bytes.
- Checkpoint selection ran four times against four different validation samples,
  so the "selected" weights had no single, reproducible selection history.
- Consistency check 11 would have passed on them — it verifies schema and
  freshness, **not** single-writer exclusivity. That is a gap in the check.

## What replaced them

All audit checkpoints were regenerated from a single-writer run with
`cfg.train.n_workers = 1` (no spawn workers at all), verified by asserting exactly
one matching process and exactly one `### DONE` marker. The method-audit results
in `results/method_audit/` come from that clean run.

## Prevention

- Any script that calls `generate_dataset` **must** be guarded by
  `if __name__ == "__main__":`.
- Assert a single writer before training into a shared directory.
- Consistency check 11 should be extended to record a per-run writer token and
  fail when a checkpoint directory shows more than one.
