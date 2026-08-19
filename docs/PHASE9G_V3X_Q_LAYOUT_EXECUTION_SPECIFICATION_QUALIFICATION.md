# Phase 9G-V3X-Q — V3 Layout Execution-Specification Compilation, Freeze, Image Rebuild and Qualification

**VERDICT C** · **`AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION_RETRY` — TRAIN ONLY**

| | |
|---|---|
| `FINAL_V3_EXECUTABLE_SOURCE_COMMIT_V2` | `2ab73cf4e9f29c9b626f3a39fceb47effd80960b` |
| `FINAL_V3_PRODUCTION_IMAGE_V2_SHA256` | `sha256:0b2d9a686d17ae9a67fbf8745535e56df9da88d82560b9378254947904782137` |
| `V3_LAYOUT_EXECUTION_SPEC_REGISTRY_V1` root | `e16928c999e80c2661861efac4924f0e6270ef864bfbc311fa04c47bc0117195` |
| in-image suite | **4,440 passed / 0 failed** |
| official V3 rows | **0** |

---

## ROOT CAUSE — why 30 specifications were missing

The V3 layout domain was frozen as **geometry**: the registry pins a
`geometry_sha256`, a parameter-tuple hash, a horizon and a seed commitment for
all 30 layouts. It was never compiled into an **executable binding**, and
`build_source_session` needs one, so no official V3 episode could bind.

Historical specifications come from `compile_nonfinal_split`, which enumerates
`results/rvt_fd24/splits/{split}_layouts.json` — V2-era layouts only. The
generator's enumeration helper cannot even reach the V3 offsets:
`_SPLIT_VARIANTS = {train: (0, 1), validation: (0,)}` yields train 0.0/0.11 and
validation 0.43, while V3 needs **0.22, 0.54, 0.65**.

No earlier phase caught it because every V3 canary deliberately used the
offset-0.0 layouts `train-f{1,8,9}-00`, chosen precisely *because* the final
registry excludes them — that is what made canary disjointness structural. Those
layouts have specifications, so an official V3 layout was never loaded until the
V3A-T prelaunch tried one.

## OWNER AUTHORIZATION

`ADDITIVE_V3_LAYOUT_EXECUTION_SPECIFICATION_COMPILATION` — compile executable
specifications for the already-frozen layouts, and nothing else. Geometry,
identity, assignment, TRAIN/VALIDATION membership, episode manifests and
scenario families are untouched.

## EXECUTION-SPEC SCIENCE

`phase8e/compiler.py::compile_layout_record` is a **pure function of three
inputs**: the frozen layout record, the split, and the frozen executable
protocol. It reads no runtime configuration. Every helper takes only
geometry- or protocol-derived arguments. It emits `category_d_count: 0`, and
`build_binding` refuses any specification that does not.

The layout record itself is re-derived from `phase8/scenario.py::_layout`, called
with the registry's own `(family, generator_split_namespace, variant_index)`
triple — and then **checked**, not trusted.

### X2 field classification

| category | count |
|---|---:|
| **A** deterministic function of frozen layout geometry | 13 |
| **B** deterministic function of an existing frozen scenario contract | 10 |
| **C** already explicitly frozen in the V3 layout registry | 1 |
| **D** new unbound scientific degree of freedom | **0** |

All 26 specification fields classified; none unexplained.

### X3 what `geometry_sha256` actually covers

It covers generator version, family, start, goal, centerline, nominal passage
width, static obstacles, dynamic obstacle paths, bypass, communication
*profile*, initial topology, horizon and canonical parameters — so obstacle
geometry, corridor geometry, goal, start, horizon, family parameters and dynamic
obstacle parameters are all inside it.

It does **not** cover the executable-protocol hash, the Target-V4 hash, world
bounds, source-policy ids, or the goal tolerance and dwell formulas — which are
carried as *formulas* and resolved from the frozen runtime configuration at bind
time, never baked in. `geometry_sha256` is not claimed to cover the whole
specification; every field outside it traces to an existing frozen contract,
which is exactly why the D count is zero.

## ROW-BINDING IMPACT

**Row Binding V3 does not change.** `bdab65bd…` is untouched, 16 identity fields.

Row identity already binds `layout_sha256`, which *is* the frozen
`geometry_sha256`. The specification is a deterministic compilation of that same
geometry plus already-frozen contracts, so it introduces no scientific variable
that identity does not already carry, and with D = 0 there is no free parameter
whose value a row would need to record. Had any execution-critical field been
category D, the chosen value would have been new authority and identity would
have had to bind the execution-spec hash — that counterfactual is recorded.

## COMPILATION

TRAIN **20/20**, VALIDATION **10/10**, reserve **0**, forbidden offsets **0**.
Offsets compiled: exactly `{0.22, 0.54, 0.65}`. The 0.33 reserve layouts have no
official specification and are refused by name.

Compiled **inside the previously qualified image on the remote target**, then
**independently recompiled on the orchestration host** to the same registry root
`e16928c9…`. That is what makes determinism demonstrated rather than asserted.

## HASH REPRODUCTION

| check | result |
|---|---|
| geometry hash | **30/30**, 0 mismatches |
| parameter-tuple hash | 30/30 |
| seed commitment | 30/30 |
| horizon | **30/30**, 0 mismatches |
| execution-spec canonical hash recomputes | 30/30 |
| registry hash rewritten | **0** |

No frozen hash was adjusted to make anything work.

## V2 PRESERVATION

`_SPLIT_VARIANTS` and `_SPLIT_OFFSETS` are byte-identical. `results/rvt_fd24/splits`
is untouched. No historical execution specification was modified — measured as
`git diff --diff-filter=MRD` from the Phase-8 commit over the specification
directories, the split manifests and `rvt_swarm/phase8`: **empty**.

Five V2-era tests globbed the specification directories and would have counted
the new files. Each was **narrowed** to the V2-era layout set defined by the
frozen split manifests, keeping its original force over the historical 30 rather
than being loosened. Assertions relaxed: **0**.

No scope guard fired: every change lands outside the protected tuple —
`rvt_swarm/phase9g0r` and `results/rvt_fd24/layout_execution_specifications`.
The pathspec `rvt_swarm/phase8` does not match `rvt_swarm/phase8e` either, and
nothing in `phase8e` was touched.

## PROVENANCE

The execution-spec registry root is bound by the **V3 produced dataset manifest**
and the **V3 dataset seal** (both amended in `writer_v3.py`), by the final
generation authority, and — already, per layout — by the frozen
`ScenarioRuntimeBinding.layout_execution_spec_hash`. It is **not** bound by row
identity or by candidate execution provenance.

The frozen dry **source** manifests were not re-emitted; their episode, layout
and seed membership is unchanged and their roots still identify the
source-episode population. Stated plainly, as X17 requires: the TRAIN manifest
root `6390cd31…` does **not** by itself identify the complete runtime authority.
The complete authority is the pair *(manifest root, execution-spec registry
root)*, and both are recorded together in the final generation authority
artifact. Nothing pretends otherwise.

## DRY BINDING

| check | result |
|---|---|
| all 30 layouts bind | **30/30**, 0 mismatches |
| layout × team size | **150/150** |
| TRAIN episodes dry-bind | **1200/1200**, 0 failed, 20 distinct layouts |
| VALIDATION episodes dry-bind | **300/300**, 0 failed, 10 distinct layouts |
| **simulator steps** | **0** |
| official outcomes observed | **0** |

Fail-closed matrix, all rejecting: reserve layout · unknown layout · split
mismatch · tampered specification · missing specification.

**X23 — the original blocker.** `train-f1-02`, the exact layout that stopped the
official TRAIN phase, now resolves through the *frozen* loader and binds at every
qualified team size. A regression test pins it.

**X10 — the split hazard.** `validation-f1-01` is a V3 **TRAIN** layout. Its V3
split comes from registry membership (`v3_train`); a naive string parse would say
`v3_validation` and be wrong. Its *geometry namespace* is `validation`, which is
a different thing.

> **Declared deviation.** The phase asked that a V3 TRAIN layout resolve to a
> "TRAIN execution-spec namespace". The specifications instead live in the
> geometry namespace (`train/`, `validation/`), because the frozen loader
> hard-requires `split in ("train","validation")` and `source_layout.split ==
> split` and builds the path from that value — a `v3_train/` directory would have
> meant editing frozen V1/V2 runtime, which this phase equally forbids. The V3
> *lookup* satisfies the requirement's substance: it resolves by registry
> membership, verifies the V3 split explicitly, and never parses a layout id.

## IMAGE

Built once per commit on the remote target, native `linux/amd64`, from a clean
`--no-local` clone garbage-collected before the build.

| | |
|---|---|
| source commit | `2ab73cf4e9f29c9b626f3a39fceb47effd80960b` |
| digest | `sha256:0b2d9a686d17ae9a67fbf8745535e56df9da88d82560b9378254947904782137` |
| architecture / size / layers | `amd64/linux` · 630,284,244 B · 14 |
| clean tree / untracked in context | 0 / 0 |
| tracked files / specification files | 1,781 / **60** |
| Dockerfile · lockfile | `59d35736…` · `4b8ae11c…` |
| base image · Debian snapshot | `python:3.9.6-slim-bullseye@sha256:4115592f…` · `20260220T214329Z` |
| package upgrades | **0** |
| pins | Python 3.9.6 · torch 2.8.0+cpu · numpy 2.0.2 |

### Two builds, both recorded

The first image, at commit `479c53c4…`, **failed the in-image suite with two
failures**. Both were portability defects in my own tests, not environment
problems: one hard-coded `.venv/bin/python`, which exists only on the
orchestration host; the git-backed tests were refused by git's dubious-ownership
guard because `/opt/rvt` is root-owned while the suite runs unprivileged. X30
permits no environment exemption, so the tests were fixed
(`sys.executable`, `git -c safe.directory=*`) and the image was **replaced rather
than excused**. A third correction went in at the same time: a specification-count
assertion measured additions since the Phase-8 commit and expected 30, but the
V2-era specifications were themselves added after Phase 8, so the honest count
there is 60 — it now measures this phase's own delta against the V3A-T stop
commit, 30 added and 0 modified.

`sha256:67f378d5…` is recorded as `SUPERSEDED_FAILED_IN_IMAGE_SUITE`, not
authorized. `sha256:a602ec01…` at `d635f17c…` becomes
**`PRE_EXECUTION_SPEC_PRODUCTION_IMAGE`, not authorized for official V3
generation** — it does not contain the specifications. Neither history is
deleted.

## QUALIFICATION

| check | result |
|---|---|
| full suite in final image | **4,440 / 0**, 390.35 s, no exemption |
| V1/V2 + scope-guard subset in image | 314 / 0 |
| all-30 in-image binding | **30/30**, 0 mismatches |
| semantic canary W1 | `95dbdab7…92df340` |
| semantic canary W12 | `95dbdab7…92df340` |
| historical qualified digest | `95dbdab7…92df340` — **identical, recomputed not blessed** |
| Brier `p=0.5, k=1, R=3` | **0.25** |
| R = 1 vs `binary_cross_entropy_with_logits` | bit-identical |
| `W(5,1) = W(16,1) = W(5,3) = W(16,3)` | one distinct value |
| replica-order invariance | identical |
| failure/resume | 0 duplicates · 0 partials · 0 seed substitutions · 0 identity differences |

## TARGET

**All heavy execution ran on `100.71.102.9`** — compilation, binding loads,
dry-binding, both image builds, both in-image suites, the canary, the resume
qualification. The orchestration host did git inspection, artifact authoring, SSH
orchestration and one independent recomputation of the registry root, which is
pure metadata hashing and steps no simulator. Scientific simulation on the
orchestration host: **0**. Docker qualification on the orchestration host: **0**.

```
Windows      Microsoft Windows [Version 10.0.26200.9168]
WSL          2.7.10.0   kernel 6.18.33.2-2 (uname 6.18.33.2-microsoft-standard-WSL2)
distribution Ubuntu-24.04, x86_64
CPUs         24 (Docker sees 24)
memory       33,323,405,312 B
Docker       29.6.1, API 1.55, linux/amd64
```

Access via `ssh -o BatchMode=yes 'avis\avis'@100.71.102.9` — passwordless, no
password requested or used, no credential material recorded anywhere.

**Runtime anomaly.** The historical one-off segfault did **not** reproduce: zero
segmentation faults across two complete in-image suites and every qualification
run. `TRANSIENT_NONREPRODUCED_RUNTIME_ANOMALY` retained; science unaltered.

## OFFICIAL DATA

Official V3 TRAIN source episodes executed **0** · VALIDATION episodes **0** ·
Target-V4 evaluations **0** · robot rows **0** · labels observed **0** ·
simulator steps **0**. Dry-binding was performed; simulation was not.

Frozen V3 geometry changed **0** · new layouts **0** · layout assignment **0** ·
episode manifests **0** · scenario families **0** · V2 **0** · Gate 7 **0**.

## SEALED DOMAINS

N24 **0** · Study B **0** · final test **0** · training **0** · HP trials **0**.

## FINAL PRODUCTION AUTHORITY

The next official TRAIN attempt must use, together:

```
source commit    2ab73cf4e9f29c9b626f3a39fceb47effd80960b
image            sha256:0b2d9a686d17ae9a67fbf8745535e56df9da88d82560b9378254947904782137
target V3        a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6
replica protocol 6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a
row binding V3   bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c
training loss    fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11
Brier metric     0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04
invalidity       66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75
acquisition      19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d
Target V4        54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee
layout registry  5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a
exec-spec reg.   e16928c999e80c2661861efac4924f0e6270ef864bfbc311fa04c47bc0117195
TRAIN manifest   6390cd31570d3dc12040d3522ca77db915171b82a2724db02825a32e90bd6edd
VALID manifest   431e42ee832c808a6bb9747ee23940d4bb7d18d9b7a5f55bc43fcaa7f4a648f2
profile          workers 12 · threads 1 · chunk 1 · timeout 243 s
```

---

## Artifacts

18 canonical-hashed records under `results/rvt_fd24/phase9g_v3x_q_*.json`, the 30
specifications under `results/rvt_fd24/layout_execution_specifications/`, and 67
tests in `tests/test_phase9g_v3x_q_execution_specifications.py`.

## Verdict

**C** — all 30 V3 execution specifications are deterministic executable
compilations of already-frozen scientific authority; every hash and
execution-critical field reproduces exactly; V1 and V2 remain unchanged; a new
exact qualified `linux/amd64` image contains the specifications; all remote
qualification passes; official V3 data remain untouched. All 18 criteria met.

**Recommendation: `AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION_RETRY`
— TRAIN ONLY.**
