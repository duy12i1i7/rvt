# Phase 9G-V2Q-R — Windows Target Requalification

**Result: the Windows/WSL2 target is fully requalified with the exact V2 image.
Verdict C · AUTHORIZE_OFFICIAL_RECOVERABILITY_V2_TRAIN.**

Reference and target produce a **byte-identical scientific semantic digest**, W=1
and W=12 agree exactly, failure/resume is clean, and the full suite passes
3,427/0 inside the exact image on target. `TARGET_REQUALIFICATION_PENDING` →
**`TARGET_REQUALIFIED`**.

---

## 1. Access

| item | value |
|---|---|
| account form used | `avis\avis` |
| method | SSH **public-key** authentication |
| passwordless | **true** — every call ran under `BatchMode=yes`, which makes an interactive password prompt impossible |
| password requested or used | **no** |
| credential material recorded | **none** — no key, password or `authorized_keys` content appears in any artifact, script, log or command |

## 2. Windows host

```
whoami   : avis\avis
hostname : avis
ver      : Microsoft Windows [Version 10.0.26200.9168]
OS Name  : Microsoft Windows 11 Pro
System   : x64-based PC
```

The handoff quoted build `10.0.26200.8875`; the host now reports **`.9168`**. It
has been updated since the spec was written. Recorded as observed rather than as
stated — the difference is a Windows servicing update and touches nothing
scientific.

## 3. WSL

Authoritative distribution label is **`Ubuntu-24.04`** (not "Ubuntu 24.04.4",
which is the *description*). `docker-desktop` also runs as a distribution.

| item | value |
|---|---|
| distribution | `Ubuntu-24.04` — Ubuntu 24.04.4 LTS, default, version 2 |
| WSL | 2.7.10.0 |
| kernel | `6.18.33.2-microsoft-standard-WSL2`, x86_64 |
| CPUs | **24** |
| RAM | 31 GiB (33,323,397,120 B) |
| swap | 8 GiB |

## 4. Docker

Client/server **29.6.1**, API 1.55, `linux/amd64`, 24 CPUs, 33.3 GB, runtime
`runc`, storage `overlayfs`. Nothing was reinstalled.

## 5. Image

The exact digest was **not** present on target and was **not rebuilt** there.
It was transported byte-exact:

```
docker save → gzip -1 → scp → docker load
archive sha256 58eed5d33fb57e208be9d6e2e16a3f6f1284223e08a6f2d61dc4f85d0efc4016
  local  = target  ✓  (verified with sha256sum on the target)
```

| item | value |
|---|---|
| image ID | `sha256:2949628f6eb57abafe680687b677958c7cc52bffab84545514a48d84a936c684` |
| present & digest-verified on target | **yes** |
| architecture | amd64/linux |
| size | 1,883,435,555 B — identical to reference |
| rebuilt on target | **no** |

Transfer took 45 min at ≈1.1 MB/s over the link.

## 6. Image source identity (Q5)

Run inside the image **on target**:

```
COMMIT   = f0a923f57fd8bea6b8249fad9652fcd37c674740
PROTOCOL = 19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d
ROWBIND  = 98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8
PY=Python 3.9.6  PYTHONPATH=/opt/rvt  HASHSEED=0
OMP=1 MKL=1 OPENBLAS=1 NUMEXPR=1  PROFILE=FD24_NUMERICAL_EXECUTION_PROFILE_V1
```

Content identity, not tag identity: the digest was inspected directly and the
commit read from inside the running container.

## 7. Target full test suite (Q6)

| | passed | failed | seconds |
|---|---:|---:|---:|
| reference (in image) | 3,427 | **0** | 747.3 |
| **target (in image)** | **3,427** | **0** | **374.9** |

Counts are identical — no explanation of divergence is needed. The target is
~2× faster.

## 8. Source + candidate canary (Q7–Q9, Q12)

Non-official `study_a_v2i_canary` / `v2i_canary` identities, 10 episodes across
F1–F10 and N ∈ {5, 6, 8, 12, 16}. The canary script was piped into both hosts
from one file — `sha256 0bc85a85…`, verified identical on both sides.

| metric | reference | target W12 | target W1 |
|---|---:|---:|---:|
| episodes / events | 10 / 43 | 10 / 43 | 10 / 43 |
| rows published | 780 | 780 | 780 |
| **rows not binding `19fa68a3…`** | **0** | **0** | **0** |
| rows not binding row contract | 0 | 0 | 0 |
| **rows with the two hashes conflated** | **0** | **0** | **0** |
| duplicate row IDs | 0 | 0 | 0 |
| partial publications | 0 | 0 | 0 |
| actual `GENERATION_INVALID` | 0 | 0 | 0 |
| **fake `GENERATION_INVALID`** | **0** | **0** | **0** |
| fabricated source states | **0** | **0** | **0** |
| selection semantics all correct | true | true | true |
| F8/F9 three replicas | true | true | true |
| other families frozen replica count | true | true | true |
| matched randomness identical COMPACT/LINE | true | true | true |

Selection was checked per episode, not asserted: `M = 0` → 0 events and 0 tasks;
`M ≤ 5` → exactly `M` events with indices `0..M-1`; `M > 5` → exactly the
`floor(j·(M−1)/4)` set. All 10 episodes passed.

## 9. Provenance binding (Q9)

Every one of the 780 target rows carries, in **separate fields**:

- `source_acquisition_protocol_sha256` = `19fa68a3…` (scientific)
- `recoverability_row_binding_v2_spec_sha256` = `98f18a94…` (additive contract)
- `target_v4_contract_sha256` = `54a0e0ba…`

Rows where the first two were conflated: **0**.

## 10. Reference vs target (Q10)

```
reference  semantic digest : 7e63321b4c7147afe04883207f325f7b2f4beadbf19f13eee7e6edba3e1ee9ba
target W12 semantic digest : 7e63321b4c7147afe04883207f325f7b2f4beadbf19f13eee7e6edba3e1ee9ba
IDENTICAL
```

**Invariant-field mismatches: 0**, compared per episode and per event across
episode identity, `M`, terminal cause, selected indices, selected timesteps,
source fingerprints, acquisition sha256, event IDs, realized timesteps, replica
counts, matched disturbance seeds, dispositions, Target V4 status, pair decisions
and every row identity. **No new tolerance was introduced** — comparison is exact
equality throughout.

## 11. W=1 vs W=12 on target (Q11)

```
target W1  digest : 7e63321b…
target W12 digest : 7e63321b…
IDENTICAL
```

Wall time changed (414.5 s vs 151.5 s); nothing scientific did. Threads = 1,
chunk = 1 in both.

## 12. Failure / resume (Q13)

| check | result |
|---|---|
| Stage A idempotent | **true** (same `acquisition_sha256`, same event IDs, same fingerprints) |
| interrupted after | 2 of 5 events |
| completed units skipped on resume | 2 |
| units resumed | 3 |
| completed units regenerated under a new identity | **0** |
| duplicate row IDs | **0** |
| partial candidate-pair rows | **0** |
| partial robot rows | **0** |
| pair atomicity preserved | true |

Re-submitting an already-completed unit reproduced byte-identical row IDs and was
refused a second ledger append. No official namespace was touched.

## 13. Timeout (Q14)

Infrastructure timeout **243 s, unchanged**. Worst atomic unit on target
**38.54 s** (15.9 % utilization); reference worst was 80.3 s. Not exceeded.
Timeouts misclassified as a scientific outcome: **0**.

## 14. Performance (Q15)

| item | value |
|---|---|
| CPU | Intel Core Ultra 9 285K, 24 visible CPUs, 1 thread/core |
| RAM | 33.32 GB; swap 8.59 GB with **20 KB used** (no swapping) |
| disk | 1.08 TB total, 4.3 GB used (1 %) |
| canary wall, W12 / W1 | 151.5 s / 414.5 s |
| source episodes / s (W12) | 0.066 |
| selected source states / s (W12) | 0.284 |
| candidate aggregates / s (W12) | 0.568 |
| full suite | 374.9 s vs 747.3 s on reference |

Used for execution planning only. **No scientific budget was modified.**

## 15. Dry official manifests (Q17/Q18)

Compiled on target inside the exact image. **Not executed**; candidate results
materialized: 0.

| split | source episodes | max selected | binds `19fa68a3…` | N24 | Study B | final test | authorizes |
|---|---:|---:|---|---:|---:|---:|---|
| train | **1,200** | 6,000 | yes | 0 | 0 | 0 | false |
| validation | **300** | 1,500 | yes | 0 | 0 | 0 | false |

Manifest roots match the reference exactly: train `c3f20538…`, validation
`80b13351…`. All ten families, N ∈ {5,6,8,12,16}, all six source policies. 350
excluded identities enforced. Every sealed study and split guard **failed closed**.
No validation outcome was inspected.

## 16. One advisory finding

**V2QR-F1 (advisory).** The `study_a_v2i_canary` namespace this canary uses is
not listed in a formal exclusion set — `load_v2_excluded_identities` loads 350
identities (design pilot 300 + V2Q canary 50) and does not include it.

**Substantive risk: none.** I verified computationally that the canary and
official identity sets are provably disjoint: `canary ∩ official = 0` over all
1,200 re-namespaced identities versus all 1,500 official train+validation
identities, and `official ∩ excluded = 0`. A canary identity therefore cannot be
selected into an official manifest. The gap is formal bookkeeping, not exposure.

Adding the exclusion set would change `load_v2_excluded_identities` and require an
image rebuild, which would invalidate the exact image under qualification — so it
was deliberately **not** done here. Recommended as an additive change in the phase
that follows.

## 17. Sealed counters

Study-A N24 **0** · Study-B **0** · final test **0** · official V2 TRAIN rows
**0** · official V2 VALIDATION rows **0** · Residual **0** · training **0** ·
HP trials **0** · V1 mutations **0**.

The transferred archive was deleted from the target after loading; the qualified
image is retained for the authorized TRAIN phase.

---

## Verdict

**C — the Windows/WSL2 target is fully requalified with the exact V2 image;
reference-vs-target and W1/W12 semantics are invariant; failure/resume is clean;
the project is ready for separately authorized official Recoverability V2 TRAIN
generation.**

Not A: no scientific semantic mismatch — the digests are identical and 0 invariant
fields differ.

Not B: the exact image reproduces reference scientific output on target
bit-for-bit; it was transported, never rebuilt.

Not D: every qualification item Q0–Q18 completed with evidence.

**Recommendation: AUTHORIZE_OFFICIAL_RECOVERABILITY_V2_TRAIN.**

No official TRAIN, VALIDATION, Residual or training was run, and none is
authorized by this phase. Target status moves from
`TARGET_REQUALIFICATION_PENDING` to **`TARGET_REQUALIFIED`**.
