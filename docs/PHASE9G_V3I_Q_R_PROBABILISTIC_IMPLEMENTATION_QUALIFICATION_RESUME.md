# Phase 9G-V3I-Q-R — Probabilistic Recoverability V3 Implementation and End-to-End Qualification Resume

**Owner-freeze commit (full):** `ff22bd6001722bcdc9f4147fb396b72b8e5c05cc`
**Implementation closure commit:** `42d8012249a6773a9e047e4dc0098abdbb7ac3b6`
**Final implementation commit:** `beb65ba6eedcf0eebba07cde57a361b9956d15be`
**Branch:** `research/rvt-phase9g-v3i-q-r-probabilistic-implementation-qualification-v1`

**Verdict C. Recommendation `AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION` — TRAIN ONLY.**

| | |
|---|---|
| canary semantic digest, reference **and** target | `95dbdab76ce8066f6e535c09a86dca73bb4018e135c590a0ac72584b992df340` |
| production image | `sha256:eaf52f7495f7eea1c1ae0392a4b688ce9918ecaee53d9be56ce1bb5b9518f169` |
| invalidity contract bound | `66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75` |
| canonical host suite | 4,265 passed / **0 failed** |
| in-image suite on Windows target | 4,265 passed / **0 failed** (×2) |
| official V3 rows generated | **0** |

---

## BASELINE (R0)

The owner-freeze phase reported 4,144 passed / 2 failed. Both failures were
reproduced on the exact owner-freeze source state, then run again in the
repository-authoritative environment.

| invocation | commit | passed | failed |
|---|---|---:|---:|
| ordinary host, no `PYTHONPATH` | `ff22bd60` | 4,144 | 2 |
| canonical environment, `PYTHONPATH` set | `ff22bd60` | **4,146** | **0** |
| canonical environment, after V3 | `beb65ba6` | **4,265** | **0** |

**Mechanism.** Both tests spawn `scripts/run_phase9_official_generation.py` as a
subprocess. The child interpreter puts the *script's* directory on `sys.path`,
not the repository root, so `import rvt_swarm` raises `ModuleNotFoundError`
before the script executes a line. The canonical image declares
`PYTHONPATH=/opt/rvt`, and `tests/test_phase9g_v2q_production_qualification.py`
already asserts that string appears in the Dockerfile.

**Classification: `TOOL_ENVIRONMENT_ONLY`.** No package, source or science
change was needed; no test assertion was touched; no `setup.py` or
`pyproject.toml` was added. This is not a new judgement — Phase 9D-H1R-OD
recorded the identical two tests, the identical mechanism and the identical
resolution (3,251/2 without `PYTHONPATH` versus 3,253/0 qualified). The failures
are not buried under later V3 counts; final qualification is **0 failures**, met
on both host and target.

## IMPLEMENTATION

**Dispatch (R2).** V1 and V2 modules are untouched and import nothing from V3.
Eight new modules: `contracts_v3`, `compiler_v3`, `producer_v3`, `writer_v3`,
`canary_v3` under `phase9g0r`, and `loss_v3`, `metrics_v3`, `loader_v3` under
`fd24`.

The design decision that matters: **V3 reuses rather than reimplements.** Stage A
is a thin alias to the frozen V2 acquisition; the per-replica outcome is
`evaluate_target_v4` unchanged; and the candidate rollout is the frozen
`produce_recoverability_candidate`. That last one is why owner-ratified C7 is
*structural* — that function iterates the complete replica-job tuple and only
breaks on infrastructure retry exhaustion, so scientific invalidity has no branch
that could stop it. A second implementation could have drifted; an alias cannot.

**Compiler (R3–R6).** Consumes the final registry V2 and the frozen dry
manifests, verifying both nesting levels of every hash. Official mode hard-fails
on the superseded registry. Acquisition stays `REALIZED_TRAJECTORY_UNIFORM_K`,
K=5, candidate-blind, with zero fabricated source states.

**Split authority (R5).** Never inferred from `layout_id`. V3 TRAIN legitimately
contains ten layouts whose ids begin `validation-`; a string parser would
misclassify every one of them. Split comes from the manifest's `v3_split` and
from registry membership, with a regression test that asserts the naive parser
would have been wrong.

**Supervision, writer, loader.** `(k, R)` per candidate with full per-replica
evidence retained — V2 discarded it and the gate-7 forensics had to replay the
whole dataset to get it back. The writer owns a `v3_recoverability` namespace it
cannot escape into a V1/V2 path. The loader's unit is the decision event: two
candidates, N rows each, one `(k, R)` per candidate, or the event does not exist.

## INVALIDITY

| property | status |
|---|---|
| frozen contract bound | `66bdd9ff…`, fail-closed on missing/empty/wrong |
| R shrink | forbidden — `R` is compared against the frozen protocol, never inferred from the executed set |
| Y imputation | impossible — an invalid replica's `target_v4_label` is `None`; a supervision record built from any invalid replica **raises** |
| replacement replica | 0 sampled |
| early abort | forbidden; `2 × R` planned executions are computed before any outcome exists and the producer raises on a shortfall |
| full required execution | every required replica of **both** candidates runs regardless of when invalidity appears |
| pair not labelable | `2 × N` rows or 0; `SCIENTIFICALLY_RECONCILED_GENERATION_INVALID` |
| audit preserved | nine evidence classes retained; 0 placeholder rows |

The pair status strings are the **existing** repository ones, pinned by a test
that compares them against what `reconcile_candidate_pair` emits — no
semantically duplicate status was invented.

Infrastructure failure stays separate: it yields no disposition, does not reduce
R, does not construct `(k, R)`, and does not make a pair non-labelable. It
produces `PENDING_INFRASTRUCTURE_RESOLUTION`, which takes precedence over
scientific invalidity precisely because an unresolved candidate has not yet
produced the disposition invalidity would be read from.

## S8

- **numerator** — executed required Target-V4 replica rollouts disposed `GENERATION_INVALID`
- **denominator** — executed required Target-V4 replica rollouts
- **unit** — the replica rollout
- censored scientific-invalid rollouts **remain** in the denominator; unresolved infrastructure failures are **excluded** until executed
- thresholds unchanged and **strict**: below 0.02 overall, below 0.05 per family

Synthetic qualification proves the exact fraction (3/200 → PASS), the boundary
(exactly 0.02 → **FAIL**, because the frozen wording is "below"), and
infrastructure exclusion. Canary measurement: 0 / 94, PASS. Gate not tuned.

## LOSS

`L_robot = -[k·log p + (R−k)·log(1−p)] / R`, implemented as
`BCEWithLogits(z, k/R)` — algebraically identical and log-sum-exp stable, so no
clamping is needed and the loss stays finite at logits of ±80. Maximum deviation
from the written-out reference formula in float64: **1.11 × 10⁻¹⁶**.

- Event-equal: rows → mean over N → mean over two candidates → event weight 1 → mean over events.
- N- and R-invariant: `W(5,1) = W(16,1) = W(5,3) = W(16,3)`, verified.
- R=1 reduces **exactly** — bit-identical to `binary_cross_entropy_with_logits` at target 0 and 1.
- Per-replica masking is refused at the interface, so the contract's prohibition cannot be bypassed by accident.

## BRIER

`Brier_robot = (1/R)·Σ(p − Y_r)² = p² − 2p(k/R) + k/R`. The shortcut
`(p − k/R)²` is implemented nowhere.

**Mandatory fixture: p = 0.5, k = 1, R = 3 → 0.25** on both reference and target,
against the shortcut's 0.0278 — an eleven-fold difference on exactly the
stochastic-boundary events V3 exists to learn. All six `(k, R)` patterns match
the literal replica-by-replica definition to **1.67 × 10⁻¹⁶**.

## REGISTRY

TRAIN 20 layouts / 1,200 episodes / 60 per layout at offsets 0.22 + 0.54.
VALIDATION 10 / 300 / 30 at offset 0.65. Offset 0.33 stays `UNUSED_RESERVE`;
0.76 and 0.87 are absent. Both manifests remain dry (executed 0, generated 0,
rows 0). The superseded 10-layout registry `d84d0fb9…` **hard-fails**, as does
any unknown registry — raise, never warn, in both directions.

## REGRESSION

V1 and V2 modules unmodified; neither imports V3. Historical gate 7 remains
`FAILED_FOR_V2` at **59/530 = 0.11132075471698114 > 0.10**, never marked passed.

Two existing guards fired on the new code and both got a real answer rather than
a suppression:

- The **strict decentralization audit** flagged `torch.Tensor` and `Mapping` parameters in the three offline training-side modules. That guard already has a principled mechanism for this case — `OFFLINE_MODULES`, where training-time modules are excluded *with a stated reason*, as `training` already is. The three modules are declared there with their reasons.
- The **Phase 9/9B scope guards** froze `rvt_swarm/fd24` and `rvt_swarm/decentralized` with a single subset check over the whole diff. Rather than widening the authorized set, the check was **split**: modifications stay bound by the older RB16R/A1S3Z authorizations only, additions by an explicit three-file V3 set. That is strictly stronger than what it replaced, which would have accepted a modification to any newly authorized file.

Neither assertion was weakened.

## REFERENCE

Full suite 4,265/0 on the canonical host. Image built from a clean clone at the
exact final commit, reporting that commit from inside the running container:
Python 3.9.6, torch 2.8.0+cpu, numpy 2.0.2, `PYTHONPATH=/opt/rvt`,
`PYTHONHASHSEED=0`, single-threaded BLAS, immutable Debian snapshot, zero package
upgrades.

Canary: 4 episodes, 19 decision events, **270 rows**, F1/F8/F9, N ∈ {5, 6, 12},
R ∈ {1, 3}, both candidates, real Target-V4 execution, identities never chosen by
desired k. Rows per event were 10, 12 and 24 — exactly `2 × N`, never `2 × N × R`.
One candidate returned **k = 2 of R = 3**: a genuine mixed outcome that stayed
valid supervision rather than being called invalid (R33).

Digest identical across W1, W12 and reversed candidate order. Replica-order
permutation identical. Resume after a controlled interruption: 0 duplicates,
0 partials, 0 identity mismatches, 0 seed substitutions.

## WINDOWS TARGET

Passwordless SSH as `avis\avis` under `BatchMode=yes`; no password requested or
used, no credential material recorded anywhere. Windows 11
`10.0.26200.9168` → WSL2 `Ubuntu-24.04`, kernel `6.18.33.2-microsoft-standard-WSL2`,
24 CPUs → Docker 29.6.1 `linux/amd64`.

In-image self-identity on target confirmed the final commit and all five frozen
hashes including the invalidity contract, each recomputed from its artifact
rather than string-matched.

| | passed | failed | seconds |
|---|---:|---:|---:|
| canonical host | 4,265 | **0** | 396.8 |
| in image, target, run 1 | 4,265 | **0** | 374.5 |
| in image, target, run 2 | 4,265 | **0** | 375.9 |

**Reference digest == target digest**, bit for bit, with no new tolerance — and
the comparison crosses both operating system and CPU architecture (macOS arm64
versus linux/amd64). W1 == W12 on both sides. Target resume clean. All 24
loss/Brier fixtures bit-identical by float64 `repr`, including the mandatory
0.25.

### Two limitations, declared

**Image transport.** The reference host is arm64 and has no linux/amd64 Docker
daemon, so the image was built **once**, natively, in the target's WSL2 Docker
from a clean clone materialized by a git bundle whose SHA-256 was verified
identical on both sides. It was never rebuilt. R46's save/transfer/load integrity
check is therefore not applicable — exactness holds by identity instead — and the
reference-versus-target semantic comparison is made between the canonical host
environment and that image.

**One segfault.** An earlier in-image full-suite invocation on target terminated
with a segmentation fault about 3% in, at
`test_09_open_field_generates_far_fewer_epochs_than_a_corridor` — a pre-existing
decentralized-runtime test unrelated to V3. It did **not** reproduce: five
isolated runs of that file (16 passed each) and two complete full-suite runs
(4,265/0 each) followed with no recurrence, and the same test passes repeatedly
on the host. The crash point is a pure-Python beacon-ingest loop with no
recursion and no native call of its own, which makes it where the interpreter
happened to be rather than the cause. Memory was not under pressure (22 GiB free
of 31). Recorded rather than omitted.

**A third scope note.** The live canary produced **zero** scientific
`GENERATION_INVALID` replicas, so the invalidity semantics rest on the synthetic
R13 matrix and on structural reuse of the frozen producer, not on an observed
invalid rollout. That is expected — V2 measured 0 invalids across TRAIN and
VALIDATION — but it is a limit on what the live run proves.

## OFFICIAL DATA

Official V3 TRAIN episodes executed **0** · VALIDATION episodes **0** · selected
source states **0** · Target-V4 evaluations **0** · rows **0** · qualification
identities overlapping official manifests **0**. Disjointness is structural: the
canary runs on offset-0.0 layouts the final V3 registry does not contain, and it
was proved before anything executed.

## SEALED DOMAINS

Study-A N24 **0** · Study B **0** · final test **0** · training **0** · HP
trials **0** · V2 modified **0** · gate 7 modified **0** · frozen V3 science
modified **0**.

---

## Artifacts

23 canonical-hashed records under `results/rvt_fd24/phase9g_v3i_q_r_*.json`,
plus 171 tests across
`tests/test_phase9g_v3i_q_r_probabilistic_v3.py` (119) and
`tests/test_phase9g_v3i_q_r_qualification_artifacts.py` (52).

**Two suite counts, reconciled.** 4,265 is the suite at the final implementation
commit `beb65ba6` — what the image contains, and what both the canonical host and
the in-image target run report. 4,316 is the same suite at phase closure, after
this phase's 52 qualification-record tests were added; those assert over
`results/rvt_fd24` artifacts and contain no runtime code, so they postdate the
image by construction and could not have been inside it.

## Verdict

**C** — Probabilistic Recoverability V3 is implemented additively against all
frozen contracts, including required-replica invalidity and no-early-abort
semantics; loss, Brier and event weighting are exact; V1 and V2 remain unchanged;
the exact implementation image reproduces reference semantics on the Windows
target; no official V3 data have been generated.

All 27 R55 readiness criteria are met.

**Recommendation: `AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION` —
TRAIN ONLY.** VALIDATION generation, training and HP search remain unauthorized.
