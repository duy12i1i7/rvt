# Phase 9G-V3A-T — Official Study-A Probabilistic Recoverability V3 TRAIN

**VERDICT A — prelaunch provenance/integrity failure. Recommendation: `DO_NOT_PROCEED`.**

**No official V3 TRAIN data were generated. No frozen artifact was modified.**

---

## The blocker

```
OFFICIAL_V3_LAYOUT_EXECUTION_SPECIFICATIONS_DO_NOT_EXIST
```

All twenty frozen official V3 TRAIN layouts — and all ten V3 VALIDATION layouts
— have **no compiled layout execution specification**. `build_source_session`
loads that object to construct a runtime binding, so not one official V3 source
episode can start.

```
BindingError: no compiled execution specification at
  /opt/rvt/results/rvt_fd24/layout_execution_specifications/train/train-f1-02.json
```

The same gap exists **inside the frozen production image**: it carries exactly
the thirty V2-era specifications (train variants 00/01, validation variant 00)
and none of the V3 layouts, so it cannot be worked around by running in the
qualified image.

### Root cause

| | |
|---|---|
| specifications are compiled from | `results/rvt_fd24/splits/{train,validation}_layouts.json` via `phase8e/compiler.py::compile_nonfinal_split` |
| those manifests contain | only the V2-era layouts — 20 train, 10 validation |
| the generator cannot even enumerate the V3 offsets | `_SPLIT_VARIANTS = {train: (0, 1), validation: (0,)}` produces train 0.0 / 0.11 and validation 0.43. V3 needs **0.22** (train variant 2), **0.54** (validation variant 1), **0.65** (validation variant 2) |
| a V3 compilation path | does not exist anywhere in `rvt_swarm`, and no V3D/V3F/V3F-L/V3I artifact mentions execution specifications at all |

**The frozen geometry is intact.** `V3_LAYOUT_SPLIT_REGISTRY_V2` carries a
`geometry_sha256` and an `episode_horizon_seconds` for every V3 layout. What is
absent is the compiled executable binding built from that geometry.

### Why no earlier phase caught it

Every V3 qualification canary deliberately used the offset-0.0 layouts
`train-f1-00`, `train-f8-00` and `train-f9-00`, chosen precisely *because* the
final V3 registry does not contain them — that is what made canary disjointness
from official identities structural rather than merely checked. Those layouts
have specifications. The official V3 layouts were therefore never loaded until
this phase tried to run one. The canary disjointness argument was correct; it
simply never exercised an official layout binding.

### Why this phase may not fix it

- The specifications derive from `results/rvt_fd24/splits/`, which sits inside the protected tuple of `test_phase9_scope_guard.py` and `test_phase9b_scope_guard.py`. Adding twenty layout records modifies a frozen Phase-8 artifact.
- The production image is frozen and must not be rebuilt, so newly compiled specifications could only reach official execution through a mount — official science reading a scientific input that is **not in the qualified image** is a provenance change, not a build detail.
- This phase authorizes generating TRAIN, not extending the frozen scenario-compilation authority.

### What an authorized follow-up must decide

1. Whether the thirty V3 layout records are added to the frozen split manifests, or a separate V3 layout manifest is frozen alongside them.
2. Whether `generate_layouts` gains the V3 variant indices, or the V3 registry geometry is compiled directly.
3. That each compiled specification **reproduces the `geometry_sha256` already frozen** in `V3_LAYOUT_SPLIT_REGISTRY_V2`, so no geometry moves.
4. That a new production image is built from the resulting commit, since the specifications must live inside the qualified image.
5. Whether the scope guards gain an explicitly reasoned authorization entry, as RB16R and A1S3Z already have.

---

## AUTHORIZATION

TRAIN only. VALIDATION, training, HP search, Residual, N24, Study B and the
final test were all out of scope and all remain at zero.

## PRODUCTION AUTHORITY (verified before the stop)

| | |
|---|---|
| final image | `sha256:a602ec015ff3d4063908f17e4d99087ce4aa89edda5853cf3483532eb53ab318` |
| architecture | `amd64/linux` |
| embedded source commit | `d635f17c8ef7e336fd54ff95a60dd608b61f3d7b` |
| rebuilt / packages installed | **no / no** |
| previous image `sha256:eaf52f74…` | present but **not used** (`PRE_FINAL_QUALIFICATION_IMAGE`) |

All frozen contracts verified **inside the image on the target**, exact:

```
probabilistic target  a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6
replica protocol      6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a
row binding V3        bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c
training loss         fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11
Brier metric          0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04
invalidity contract   66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75
source acquisition    19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d
Target V4             54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee
layout registry V2    5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a
```

Execution location proved before launch: `hostname=avis`, `whoami=avis`,
`WSL_DISTRO=Ubuntu-24.04`, 24 CPUs, Docker 29.6.1 `linux/amd64`. No official
scientific computation ran on the orchestration host —
`OFFICIAL_V3_EXECUTION_ON_UNAUTHORIZED_HOST` is **false**.

Production profile untouched: **workers 12 · threads 1 · chunk 1 · timeout 243 s**.

## MANIFEST

Both frozen manifests resolved exactly and remain dry.

| split | episodes | layouts | per layout | offsets | executed |
|---|---:|---:|---:|---|---:|
| `v3_train` | 1,200 | 20 | 60 | 0.22 + 0.54 | **0** |
| `v3_validation` | 300 | 10 | 30 | 0.65 | **0** |

TRAIN inner manifest root
`6390cd31570d3dc12040d3522ca77db915171b82a2724db02825a32e90bd6edd`, distinct
from the outer artifact hash `ffb1fe33…`. VALIDATION inner root
`431e42ee832c808a6bb9747ee23940d4bb7d18d9b7a5f55bc43fcaa7f4a648f2`. The
superseded 10-layout registry `d84d0fb9…` fails closed.

## EXCLUSION

`V3_OFFICIAL_TRAIN_PRELAUNCH_EXCLUSION_UNION_V1`

| | |
|---|---|
| identities | **1,884** |
| root | `8cadcbdf4dd808e8c62385bfcc113d174add15f2437dc23e5723ee038e959063` |
| predecessor | `V3_COMPREHENSIVE_DEVELOPMENT_EXCLUSION_UNION_V2`, 1,880 |
| membership removed | **0** |

The 1,880 predecessor was **reconstructed exactly** — same count, same
sorted-identity digest — from the V2 development union plus the V2 official
TRAIN and VALIDATION identity sets recomputed from their frozen manifests, then
extended with the four V3 qualification-canary identities that carried the
implementation canary, the final-image canary, the replica-order run and the
failure/resume qualification.

All four required intersections are **0**: TRAIN × union, VALIDATION × union,
TRAIN × VALIDATION, canary × official manifests. Axis-level disjointness is 0 on
`layout_sha256`, `layout_id`, episode identity and source-seed identity, for
TRAIN vs VALIDATION and for canary vs official. Split came from the manifest
`v3_split` field and registry membership — never from a layout-id string.

## STAGE A · REPLICAS · SUPERVISION · INVALIDITY · S8 · PAIRS · ROWS · OPERATIONS · SEALS

**None of these exist.** No official source episode ran, so a Stage-A manifest,
replica ledger, supervision ledger, S8 gate, pair-transaction ledger, family × N
matrix, k distribution, row-integrity record, shard manifest, resume audit,
operational ledger and composite seal would every one of them be a fabrication
rather than a measurement. Fourteen required artifact names are listed in the
readiness record as explicitly not emitted, with `empty_placeholders_emitted: 0`.

A three-episode smoke run of the official runner was executed first, into a
scratch namespace that the runner refuses to point at the official one. It
failed on the first episode with the `BindingError` above, **before any durable
write** — 0 Stage-A records, 0 event records — and its directory was removed
from the target.

## HISTORICAL V2

Gate 7 remains **59 / 530 = 0.11132075471698114 > 0.10 — `FAILED_FOR_V2`**,
unmodified, and was **not** recomputed as a V3 acceptance gate. V2 rows and
contracts untouched.

## CLOSED SCOPES

VALIDATION episodes **0** · VALIDATION Target-V4 evaluations **0** ·
VALIDATION rows **0** · models trained **0** · HP trials **0** · checkpoints
**0** · Residual **0** · N24 **0** · Study B **0** · final test **0** ·
executable science modified **0** · frozen manifests modified **0**.

---

## Artifacts

- `results/rvt_fd24/phase9g_v3a_t_prelaunch_exclusion_union_v1.json`
- `results/rvt_fd24/phase9g_v3a_t_prelaunch_go_v1.json` — **`DECISION: NO_GO`**
- `results/rvt_fd24/phase9g_v3a_t_execution_specification_blocker_v1.json`
- `results/rvt_fd24/phase9g_v3a_t_official_data_protection_v1.json`
- `results/rvt_fd24/phase9g_v3a_t_final_readiness_v1.json`
- `tests/test_phase9g_v3a_t_official_train_prelaunch.py` — 28 tests, all passing

The tests re-measure the missing specifications against the live filesystem
rather than reading the claim out of the artifact, so the finding cannot quietly
go stale once it is fixed.

## Verdict

**A** — Official V3 TRAIN encountered a provenance/integrity failure at
preflight. The twenty frozen official V3 TRAIN layouts have no compiled
execution specification, in the repository or inside the qualified production
image, so no official source episode can be bound to a runtime session.

**Recommendation: `DO_NOT_PROCEED`.** An authorized phase must first compile and
freeze the V3 layout execution specifications and rebuild the production image
around them.
