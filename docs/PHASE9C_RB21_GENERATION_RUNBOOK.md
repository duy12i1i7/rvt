# Phase 9C-RB21 Generation Runbook

## Release State

RB21-TARGET is operationally qualified, but generation is not self-starting.
Every permitted scope is `AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION`. This
runbook must not be used until that instruction exists for the named scope.

Study A N24 zero-shot and final-test remain sealed. No command for either
domain exists.

## Frozen Production Configuration

| Setting | Required value |
|---|---|
| Windows host | `AVIS`, Windows 11 Pro `10.0.26200.8875` |
| WSL | Ubuntu 24.04.4 LTS, WSL 2.7.10.0 |
| Docker | Desktop 4.80.0.232116, Engine 29.6.1, Linux/amd64 |
| Image | `sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b` |
| Scientific checkpoint | `a08f6f506333a20b71b60fc366c4a36d15e289ae` |
| Profile | `PROFILE_CPU_GENERATION` |
| Process workers | 12 |
| Residual chunk | 1 complete atomic unit |
| Recoverability chunk | 1 complete atomic unit |
| Infrastructure timeout | 1200 s |
| Infrastructure retries | 1 |
| Semantic retries | 0 |
| Writer | `STAGING_VALIDATE_ATOMIC_PROMOTION` |
| Resume key | atomic scientific-unit identity |

Set every nested numeric thread control to one:

```bash
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

The qualified harness must also set `torch.set_num_threads(1)` and
`torch.set_num_interop_threads(1)` in each worker. Do not introduce a CUDA
scientific path.

## Paths

Use WSL ext4 only:

```text
/home/avis/rvt-data/staging
/home/avis/rvt-data/final
/home/avis/rvt-data/temp
/home/avis/rvt-data/audit
```

Mount `/home/avis/rvt-data` as `/rvt-data` in the exact image. The source at
`/opt/rvt` is the immutable source baked into the image. Do not select `/mnt/c`
or a Windows bind mount for high-I/O generation.

## Reboot Verification

On Windows:

```powershell
wsl --status
wsl --version
wsl -l -v
docker version
docker info
docker ps --format "{{.ID}} {{.Names}} {{.Status}}"
```

Inside WSL, verify the exact image and storage before any release:

```bash
docker image inspect \
  sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b \
  --format '{{.Id}}'
findmnt -T /home/avis/rvt-data -o FSTYPE,TARGET,SOURCE
df -B1 /home/avis/rvt-data
```

The image output must equal the requested digest, the filesystem must be ext4,
and available capacity must remain above the 23,032,970,842-byte conservative
working projection with the contract's 2.0x minimum headroom.

## Mandatory Preflight

Use a clean checkout of the evidence commit. Validate all canonical artifacts:

```bash
python -m scripts.build_phase9c_rb21_target_final_artifacts --validate-only
python -m pytest -q \
  tests/test_phase9c_rb21_target_preflight.py \
  tests/test_phase9c_rb21_target_final_artifacts.py
```

Required:

- validator status `PASS`;
- readiness verdict `C`;
- positive preflight `PASS`;
- negative escapes `0`;
- Study A N24 accesses `0`;
- final-test accesses `0`;
- `git status --porcelain` empty.

Also compare the runtime host, image, worker, thread, chunk, timeout, resume, and
writer values against
`results/rvt_fd24/rb21_target_operational_execution_contract_v2.json`.

## Release Selection

The immutable future launch specifications are in
`results/rvt_fd24/rb21_target_official_command_plan_v1.json`. They are split
into exactly these unsealed selectors:

- Study A train recoverability;
- Study A train residual V2;
- Study A validation recoverability;
- Study A validation residual V2;
- Study B train recoverability;
- Study B train residual V2;
- Study B validation recoverability;
- Study B validation residual V2.

An owner-authorized generation task must bind the selected specification to the
qualified Phase-9 generator without changing its selector or operational
configuration. Do not synthesize a broad release flag. Do not combine a scope
that was not named by the owner.

## Atomic Units

Residual V2 atomic unit:

```text
one decision state x one robot x all nine candidate evaluations
```

Recoverability atomic unit:

```text
one decision state x one topology candidate x all frozen replicas
```

Parallelism is between atomic units only. Never scheduler-split candidates or
replicas. Chunk size is one complete atomic unit for both branches.

## Staging And Acknowledgement

Every unit starts under STAGING. A scientific record and its required audit
provenance commit coherently or remain incomplete and retriable. A worker must
not acknowledge completion before durable promotion of the coherent unit.

The permitted state flow is:

```text
STAGING
-> execute or exact replay of incomplete atomic unit
-> coherent record and sidecar validation
-> atomic promotion within staging namespace
-> task reconciliation
-> dataset seal checks
-> controlled promotion to FINAL
```

A partial staging dataset is never a complete dataset.

## Resume And Failure Handling

Resume by atomic scientific-unit identity. A completed unit is validated and
skipped; it must not create a new sample. An incomplete unit may replay exactly
with the same snapshot, matched streams, candidate IDs, Target V4 predicates,
labels, utilities, selected candidate, WORLD target, and disposition.

One infrastructure retry is allowed. Semantic retry is prohibited. Timeout is
an infrastructure failure only and must not emit a negative label, target row,
or denominator entry.

For a worker or writer failure:

1. Stop scheduling new chunks.
2. Preserve the audit attempt and partial temporary files.
3. Reopen the staging index and validate every acknowledged unit.
4. Requeue only incomplete atomic identities.
5. Reject any duplicate whose scientific content differs.
6. Escalate after the single infrastructure retry is exhausted.

## Monitoring

Monitor separately:

- completed, incomplete, and retried atomic units;
- semantic retry count, which must remain zero;
- unresolved infrastructure failures;
- p95 and maximum atomic latency against the qualification envelope;
- aggregate worker RSS against 33,323,384,832-byte WSL RAM;
- writer queue depth and commit validation failures;
- staging, final, temp, and audit free bytes;
- disposition counters and scheduled-task reconciliation;
- GPU only as an observation, never as a generation dependency.

Expected selected throughput is about 0.3305 recoverability unit/s and 0.2435
residual decision/s. These are capacity estimates, not scientific gates.

## Completion And Promotion

Promotion to FINAL requires all of the following:

1. Every scheduled atomic identity is reconciled.
2. Every legitimate attempt has a disposition.
3. Unresolved infrastructure failures equal zero.
4. Duplicate validation passes with no changed science.
5. Scientific and disposition counters reconcile.
6. Every shard and index hash validates.
7. Study/split seal validation passes.
8. Staging is sealed against further writes.
9. Controlled promotion completes without changing bytes.

Do not promote a partial dataset.

## Abort Rules

Abort immediately if any of these occurs:

- host, image, source, provenance root, or portability root mismatch;
- worker, nested thread, chunk, timeout, resume, or writer mode mismatch;
- a scientific digest differs from the qualified projection;
- a duplicate changes scientific content;
- any partial record is accepted as complete;
- semantic retry becomes nonzero;
- unresolved infrastructure failure remains after one retry;
- available storage falls below the required projection and headroom;
- any Study A N24 or final-test access appears without a separate seal-opening
  instruction;
- any action would generate through CUDA or alter frozen science.

On abort, preserve STAGING and audit evidence. Do not promote, delete, rewrite,
or relabel scientific output.

## Current Isolation

At RB21-TARGET completion:

- official recoverability rows: 0;
- official residual rows: 0;
- official shards: 0;
- checkpoints: 0;
- optimizer states: 0;
- training operations: 0;
- Study A N24 accesses: 0;
- final-test accesses: 0.

The command plan is prepared but has not been executed.
