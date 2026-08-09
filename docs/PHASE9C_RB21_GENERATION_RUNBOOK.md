# Phase 9C-RB21 Generation Runbook

## Current State

**Blocked by the Phase 15 scientific-semantic gate.**

Do not execute official generation on `AVIS`, in WSL2, or in the RB21 probe
image. Worker count, chunk size, timeout, capacity, H4 classification, and
authorization are intentionally unset.

## Reboot Verification

After a Windows reboot, these commands only verify infrastructure. They do not
authorize or start scientific generation.

```powershell
wsl --status
wsl --version
wsl -l -v
docker version
docker info
docker ps --format "{{.ID}} {{.Names}} {{.Status}}"
```

Inside WSL:

```bash
cd /home/avis/rvt
git rev-parse HEAD
git status --porcelain
docker --config /home/avis/.docker-rvt-public image inspect \
  rvt-generation:rb21-qualified-stack-probe
```

The semantic probe source must remain
`b8c60b8d7d744b8d8c4ee069bde58e05dc6e3e1b`. The probe image ID recorded by
this qualification is
`sha256:695acb7a54004b32116820ac2e4b325dde5a73e1b63a9a163688a1366c61ff2b`.
It is evidence of the failure, not an approved production identity.

## Reproducing The Gate

The critical suite is diagnostic and may be rerun. The complete suite is the
decisive gate:

```bash
docker --config /home/avis/.docker-rvt-public run --rm \
  rvt-generation:rb21-qualified-stack-probe rvt-test -q
```

The accepted negative result at the evidence source is:

```text
2967 passed, 3 failed, 0 xfailed, 0 xpassed
```

Do not loosen tolerances, round compiled layout values, regenerate frozen
layout artifacts, change model batching, or replace the scientific stack to
make this command pass.

## Data Paths

The prepared Linux-native paths are:

- `/home/avis/rvt-data/staging`;
- `/home/avis/rvt-data/final`;
- `/home/avis/rvt-data/temp`;
- `/home/avis/rvt-data/audit`.

They must remain unused for official data until a later qualification passes
all semantic and operational gates.

## Sealed Domains

Study A N24 zero-shot and final test remain sealed and unauthorized. No command
for either domain exists. Diagnostic work must remain limited to already
authorized train/validation structures and must not generate official rows.

## Stop Rules

Stop immediately if any action would:

- change frozen science;
- access Study A N24 or final-test layouts;
- generate official recoverability or residual rows;
- train a model or create a checkpoint/optimizer state;
- treat the semantic probe image as qualified;
- select workers, chunks, or timeout from unexecuted benchmarks.

## Required Scientific Decision

The next action is not an infrastructure tuning task. A scientific owner must
decide and version a cross-platform numeric contract for both model batching
and layout compilation, then re-freeze affected provenance before RB21-TARGET
can restart from Phase 8. Until that happens, Verdict B remains authoritative.
