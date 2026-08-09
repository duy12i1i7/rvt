# Phase 9C-RB20 — Clean Detached Reproducibility

**Result: the replay is exact. Verdict C.**

Every scientific field of the RB-18 structural canary reproduces bit-for-bit from
a clean detached checkout, using the RB-19 current provenance root. No semantic
repair was performed and none was needed.

| item | value |
|---|---|
| execution source commit | `53a51f9a9e0b169c016742313b31c59e4cccbae6` |
| RB-19 current root | `e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571` |
| Target V4 | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |
| RB-20 reproduction artifact | `8c55f4ef40be509dc6e0bc678467873e5ebd0ce60d0195a2227555676114b95a` |

## Two-commit provenance

Execution happened **first**, from a fresh detached worktree at the execution
source commit — never the development tree. The RB-20 evidence commit exists only
afterwards and adds artifacts, tests and this document; no executable or
scientific code changed in it, so the expensive canary does not need re-running
from the evidence commit. Nothing here claims execution occurred from the later
commit.

The detached tree was clean before execution and **still clean after** — every
replay output, including the dry-run writer records, was written to a scratchpad
path outside the tracked tree.

## What reproduced

The case manifest was read from the committed RB-18 artifact, not from prose, and
replayed without substitution: `train-f1-00` F1/N6/S1, `train-f9-00` F9/N12/S0,
`validation-f8-00` F8/N5/S1, `train-f5-00` F5/N8/S1.

| branch | reproduced |
|---|---|
| source episodes | **4 / 4** exact, zero mismatches |
| recoverability rollouts | **14 / 14** exact — every raw predicate, disposition, snapshot, trace and label |
| recoverability aggregates | recomputed from raw replicas, not trusted: 4 positive, 2 negative, 0 invalid |
| residual decision states | **4 / 4** exact |
| residual candidate evaluations | **36 / 36**, utilities exact on all 36 |
| dispositions | 3 LABELED, 1 NO_ELIGIBLE_ACTION, 0 invalid, 3 rows — recomputed and matching |

The F8/F9 three-replica all-success rule held; the changed-topology lifecycle
reproduced; recoverability and residual reruns were bit-identical; chunking and
retry moved only execution metadata; the writer produced byte-identical record
hashes to RB-18.

## Semantic projection

Because RB-18 predates the RB-19 provenance repair, byte identity of the whole
artifact is not the right test. The projection includes **every** scientific and
executable field — sources, labels, raw predicates, streams, identities, targets,
utilities, dispositions, traces, schema payloads, counts — and excludes only ten
top-level bookkeeping keys (`source_commit`, `contract_root`, `timing`, the
artifact self-hash, four constant descriptors, plus the RB-20-only `environment`
and `current_root`), the per-record `seconds`, the writer `path` (RB-18 wrote
inside the tree, RB-20 outside), and the RB-20-only aggregation-recomputation
fields.

```text
RB18 projection sha256 = 53c9bdc24b0a85027ee9c482c495d479c7f733e88819e2df9a50632ecc1f8435
RB20 projection sha256 = 53c9bdc24b0a85027ee9c482c495d479c7f733e88819e2df9a50632ecc1f8435
```

**Exact match; zero semantic mismatches.**

One reporting omission was found and fixed in the replay harness before the
comparison stood: the harness consumed the RB-18 manifest but did not echo it
back. The harness was corrected and the replay re-run — the artifact was never
patched by hand.

## Provenance delta

RB-18 referenced the incomplete RB-17 root, which never cited Target V4; RB-20
references the RB-19 root, which cites it explicitly. **Zero scientific fields
changed because of that repair** — the delta is metadata only, which is precisely
what the semantic projection demonstrates.

## Preflight and tests

Positive preflight reproduced: PASS, 53 checks, 0 failures. The negative matrix
reproduced with **12 cases and 0 escapes**: missing Target V4, wrong Target V4
hash, failed RB-16 as current, MISSION output, missing orientation, candidate
count ≠ 9, KEEP online, no-eligible fallback, broken N24 seal, broken final-test
seal, the 1800 s timeout as authoritative, and premature authorization.

Critical regressions from the detached checkout: **257 passed, 0 failed** across
transport, timeout, four-epoch, epoch isolation, S2 initialization, message
isolation, RB-15 V2, the WORLD repair, RB-17, RB-18 and RB-19. Full suite from
the execution source commit: **2,922 passed / 0 failed / 0 xfailed / 0 xpassed**.

## Isolation

Official recoverability rows 0 · residual rows 0 · scientific shards 0 · FD24
checkpoints 0 · optimizer states 0 · training operations 0 · final-test accesses 0
· Study A N=24 accesses 0. Sealed namespaces still contain only their manifests
and the final-test geometry is still unmaterialized.

Operational decisions remain RB-21's: the generation timeout, worker count and
chunk size are untouched, and official generation stays unauthorized.
