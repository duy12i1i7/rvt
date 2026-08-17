# Phase 9G-V2A-V — Official Study-A Recoverability V2 VALIDATION Generation

**Result: the official VALIDATION run completed exactly under the frozen
300-source-episode manifest, passes the frozen ≥30 retained-event
per-primary-family adequacy gate, and every integrity counter is zero.
Verdict C · AUTHORIZE_COMBINED_RECOVERABILITY_V2_TRAIN_VALIDATION_AUDIT.**

**23,220 scientific rows** from **1,285** candidate-blind selected source
events. No fabricated source state, no fake `GENERATION_INVALID`, no partial
pair, no duplicate row, no timeout, no retry, no unresolved infrastructure
failure.

**Composite VALIDATION seal:
`667b117555a65ad9da7f8e6e7f71b2cfb6843cc66d8e8c35eb68650b7818ca69`**

---

## 1. Authorization

VALIDATION only, exactly 300 source episodes. Additional TRAIN, model training,
HP search, Residual V2, Study-A N24, Study-B and final test were **not**
executed and remain unauthorized.

The budget was a **cap, not a target**: 300 × K=5 = 1,500 maximum selected
events, 1,285 realized. No replenishment, no adaptive stopping, no
outcome-dependent action.

## 2. Target

| item | value |
|---|---|
| host | `avis` — Windows 11 Pro 10.0.26200.9168 |
| account form | `avis\avis`, passwordless SSH key auth (`BatchMode=yes` throughout) |
| WSL | `Ubuntu-24.04`, kernel 6.18.33.2-microsoft-standard-WSL2, 24 CPUs, ~31 GB |
| Docker | Engine 29.6.1, linux/amd64 |
| image digest | `sha256:2949628f6eb57abafe680687b677958c7cc52bffab84545514a48d84a936c684` |
| image source commit | `f0a923f57fd8bea6b8249fad9652fcd37c674740` |
| profile | workers 12 · threads 1 · chunk 1 · timeout 243 s · retry 1 · CPU-authoritative, no GPU |

The image was **not** rebuilt, updated or substituted. The embedded commit was
verified twice by independent means: the OCI label
`org.opencontainers.image.revision` on the image, and `git rev-parse HEAD`
inside a running container. Both returned `f0a923f5…`. All scientific execution
happened inside that image on the target. No credential material appears in any
artifact, script or log.

## 3. Scientific provenance

| contract | SHA256 |
|---|---|
| Source-Acquisition Protocol V2 | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` |
| Recoverability Row Binding V2 | `98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8` |
| Target V4 execution contract | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |

All three were recovered from repository authority and cross-checked against
the live code before launch, then re-verified on **every one of the 23,220
published rows**. The Row Binding value is the full 64-hex hash throughout; no
abbreviation appears in any canonical artifact.

## 4. Comprehensive exclusion union (V4/V5)

`OFFICIAL_V2_VALIDATION_COMPREHENSIVE_EXCLUSION_UNION_V1 =
89a1839ce8087015040f44f903745e5e4b8f16a34ca9407879c7bdc1dfe67ab5`

Rebuilt from committed provenance rather than copied from the TRAIN union —
**380 identities**, every canary `episode_id` reconstructed and matched exactly
(0 unmatched).

The prompt warned not to assume the prior 380-identity union was still complete
after the TRAIN audit, so completeness is **demonstrated, not asserted**: an
exhaustive sweep of every `results/rvt_fd24/**/*.json` and `docs/*.md` for
non-official namespace prefixes found **330 distinct non-official episode ids
and 0 unaccounted** for.

**On the TRAIN audit (Phase 9D-V2T) specifically.** It contributed **zero** new
identities, and this is provable rather than assumed. Its zero-positive replay
diagnostic declares a per-family event universe of F3 = 423, F4 = 324, F6 = 519,
which equals the official TRAIN Stage-A selected-event counts for those families
*exactly*; the replay therefore drew only from official TRAIN identities and
created no new source episode. It published 0 rows. Its other operations were
read-only. Since official TRAIN ∩ official VALIDATION = 0 is proved
independently, no V2T identity can reach VALIDATION.

| set | value |
|---|---|
| **VALIDATION ∩ union** | **0** |
| TRAIN ∩ union | 0 |
| TRAIN ∩ VALIDATION | 0 |
| design-pilot ∩ VALIDATION | 0 |
| qualification-canary ∩ VALIDATION | 0 |
| V2I/V2QR audit-canary ∩ VALIDATION | 0 |

## 5. Split hygiene

Verified from authoritative manifests, not taken from the prompt.

| dimension | TRAIN | VALIDATION | overlap |
|---|---:|---:|---:|
| source-episode identity | 1,200 | 300 | **0** |
| `job_id` | 1,200 | 300 | **0** |
| `layout_id` | 20 | 10 | **0** |
| `layout_sha256` | 20 | 10 | **0** |

**V1 relation.** V1 VALIDATION *source-episode identity* overlap is **300**, and
that is correct, not a violation: `generation_budget_v1.json` fixes the
300-episode Study-A VALIDATION budget and the H1R-OD owner resolution changes
*acquisition*, not the episode budget. The freshness requirement is
`merged_into_v2_confirmatory_data = false`, which concerns rows and datasets.

| V1 quantity | value |
|---|---:|
| V1 VALIDATION rows reused | **0** |
| V1 VALIDATION events reused | **0** |
| V1 scientific-row identity overlap | **0** |
| V1 row-ID overlap | **0** |
| V1 artifacts mutated | **0** |

The row-ID result is not merely structural. For **5,000 published V2 rows** the
V1 row identity was rebuilt over *exactly the same scientific content* — same
episode, same state, same robot, same candidate topology, same graph
fingerprint — and hashed with the V1 identity function. **Zero** V1-form ids
collided with any V2 id. This tests the only collision that could actually
matter, rather than resting on the schema string alone.

This is consistent with the TRAIN audit; no repository authority contradicts it.

## 6. Frozen manifest (V6)

`OFFICIAL_V2_VALIDATION_MANIFEST_SHA256 =
ce67634dba2b4c4b893938be768a4047d2ac7aaa03bfa67e64db21abd6fa12f1`

300 source episodes · **30 per family** (F1–F10) · **60 per N** (5, 6, 8, 12,
16) · 50 per source policy across all 6 · 10 layouts. N24 0 · Study-B 0 ·
final-test 0 · duplicate identities 0.

Frozen before any candidate generation, binding study, split, families, N,
layouts, episode ids, source policies, source random streams, all three contract
hashes, the image digest, the production profile and the exclusion-union hash.
Not modified after freeze.

**Pre-launch decision: GO**, zero blocking failures
(`7089c55f5306e3c7bce4844d0b9543f4b93b3dcc952ca6d50afcb90cdbada77e`).

## 7. TRAIN immutability (V2, before launch)

Verified **on the target** against the sealed dataset before a single
VALIDATION episode ran: 44/44 shards byte-identical (content hash, row count
and byte length each checked), 90,294 rows, 0 duplicate row ids, dataset
manifest self-hash valid, row dataset root recomputed from the streamed row ids
to `c91414f5…` matching the declared value, composite seal
`a966f318…` **exact**. Nothing was written into any TRAIN directory.

## 8. Stage A — candidate-blind acquisition (V9/V10)

All 300 episodes ran and were sealed into an immutable ledger **before any
candidate was compiled or executed**, so candidate-blindness is structural.

| metric | value |
|---|---:|
| source episodes | 300 |
| total eligible states | 2,714 |
| **selected source events** | **1,285** |
| cap (300 × K) | 1,500 |
| episodes with M = 0 | 6 |
| episodes with 1 ≤ M < 5 | 115 |
| episodes with M ≥ 5 | 179 |
| **fabricated source states** | **0** |
| duplicate source event ids | 0 |

Stage A root `5a0f6fada073d6bdb8ca740433d785aed55728f550695d5d626d15c1c85a611e`.

**M semantics were independently recomputed**, not trusted: for all 300
episodes the selected index tuple was recalculated from
`select_realized_trajectory_uniform_k(M, K=5)` and compared against the ledger —
**0 mismatches**. Every selected index lies inside `[0, M)`; for M > 5 the first
and last realized states are always included; timesteps are strictly monotonic.

All 6 `M = 0` episodes are **F4/N16** — the same structural cell the H1R design
pilot predicted prospectively and that produced 24/24 `M = 0` in TRAIN. They
contributed 0 events, 0 candidates and 0 rows, and were **not** replenished.

Selection-ordinal histogram: 294 / 293 / 281 / 238 / 179 for ordinals 0–4 —
the expected decay as episodes with M < 5 drop out.

## 9. Stage B — candidate execution (V11–V14)

| metric | value |
|---|---:|
| events executed | **1,285 / 1,285** |
| candidate aggregates attempted | **2,570** = 2 × 1,285 |
| candidate replica executions | 3,710 |
| COMPACT positive / valid-negative | 493 / 792 |
| LINE positive / valid-negative | 407 / 878 |
| total positives / valid negatives | **900 / 1,670** |
| **actual `GENERATION_INVALID`** | **0** |
| **fake `GENERATION_INVALID`** | **0** |
| nonexistent source states producing aggregates | **0** |

900 + 1,670 + 0 = 2,570 — dispositions reconcile exactly against aggregates.

**F8/F9 replica policy verified**: every F8 event (147) and every F9 event (138)
ran **exactly 3 replicas per candidate** under frozen all-success aggregation
with matched COMPACT/LINE disturbance streams; all other families ran 1. That
accounts for the 3,710 replica executions against 2,570 aggregates: the 1,000
single-replica events contribute 2 × 1,000 × 1 = 2,000 and the 285 F8/F9 events
contribute 2 × 285 × 3 = 1,710.

TRAIN label frequencies were not consulted at any point during execution.

## 10. Pair transactions and rows (V12/V21/V22)

| metric | value |
|---|---:|
| retained pair events | **1,285** |
| dropped pair events | 0 |
| **partial publications** | **0** |
| rows published | **23,220** |
| expected exact Σ 2·N over retained events | **23,220** |
| distinct row IDs | 23,220 |
| duplicate row IDs | **0** |
| duplicates with conflicting payload | **0** |
| **row validation failures** | **0** |
| event-identity recomputation mismatches | **0** |

Every row was streamed and re-validated inside the image: schema
`rvt-recoverability-scientific-row/v2`, identity schema
`rvt-recoverability-row-identity/v2`, all three contract hashes exact,
candidate topology in {COMPACT, LINE}, 64-hex graph fingerprint, identity field
set exactly the fourteen V2 fields with no operational contamination, and the
row ID **recomputed from its own identity and matched**. Accounting used the
exact per-event Σ 2·N, never an average N.

12 shards, 445,716,747 bytes (446 MB).

## 11. Family × N (V23, descriptive only)

Every cell has 6 source episodes. Complete 50-cell table in
`phase9g_v2a_v_family_n_validation_audit_v1.json`; per-family rollup:

| family | eps | M=0 | eligible | selected | aggregates | replicas | pos | neg | invalid | retained | rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F1 | 30 | 0 | 309 | 147 | 294 | 294 | 214 | 80 | 0 | 147 | 2,740 |
| F2 | 30 | 0 | 282 | 128 | 256 | 256 | 85 | 171 | 0 | 128 | 2,362 |
| F3 | 30 | 0 | 123 | 111 | 222 | 222 | **0** | 222 | 0 | 111 | 1,956 |
| F4 | 30 | 6 | 80 | 77 | 154 | 154 | **0** | 154 | 0 | 77 | 1,106 |
| F5 | 30 | 0 | 315 | 146 | 292 | 292 | 115 | 177 | 0 | 146 | 2,740 |
| F6 | 30 | 0 | 237 | 131 | 262 | 262 | **0** | 262 | 0 | 131 | 2,338 |
| F7 | 30 | 0 | 388 | 147 | 294 | 294 | 219 | 75 | 0 | 147 | 2,724 |
| F8 | 30 | 0 | 354 | 147 | 294 | 882 | 126 | 168 | 0 | 147 | 2,786 |
| F9 | 30 | 0 | 400 | 138 | 276 | 828 | 94 | 182 | 0 | 138 | 2,532 |
| F10 | 30 | 0 | 226 | 113 | 226 | 226 | 47 | 179 | 0 | 113 | 1,936 |
| **total** | **300** | **6** | **2,714** | **1,285** | **2,570** | **3,710** | **900** | **1,670** | **0** | **1,285** | **23,220** |

No protocol, budget or weighting was changed in response to this table.

## 12. Adequacy gate (V24) — **PASS**

Gate recovered from authority (`phase9d_h1_requirement_map_v1.json`,
`phase9d_h1r_owner_sampling_resolution_v1.json`): **≥ 30 retained VALIDATION
source events per primary family**, primary families **F1–F10**, unchanged.

The scientific unit is the **retained source-event pair** — not robot rows, not
candidate aggregates.

| family | retained source events | ≥ 30 |
|---|---:|:--:|
| F1 | 147 | ✓ |
| F2 | 128 | ✓ |
| F3 | 111 | ✓ |
| F4 | **77** | ✓ |
| F5 | 146 | ✓ |
| F6 | 131 | ✓ |
| F7 | 147 | ✓ |
| F8 | 147 | ✓ |
| F9 | 138 | ✓ |
| F10 | 113 | ✓ |

**All ten primary families pass.** The worst family is F4 at 77 — 2.6× the gate.
H1R prospectively projected F4 as the worst family at 48 retained validation
events; the realized 77 exceeds that projection, so the prospective feasibility
model was conservative rather than optimistic.

The gate was evaluated **only after** the fixed 300-episode manifest completed.
Episodes added for weak families: **0**. Outcome-dependent stopping: **none**.
M=0 episodes replaced: **0**.

## 13. Zero-positive families (V26) — carried forward, not reinterpreted

F3, F4 and F6 produced **zero positive aggregates on both candidate
topologies**, independently reproducing the TRAIN result under a fresh set of
source episodes and fully disjoint layouts.

| family | COMPACT + / − | LINE + / − |
|---|---|---|
| F3 | 0 / 111 | 0 / 111 |
| F4 | 0 / 77 | 0 / 77 |
| F6 | 0 / 131 | 0 / 131 |

This is reported **descriptively**. No predeclared authoritative validation gate
requires positives, so it is not a gate failure — and all three families clear
the ≥30 retained-event gate comfortably.

**The scenario-manifest tension is preserved unmodified.** Historical scenario
authority declares `LINE_ONLY_SUCCESS` for F3/F4 and
`COMPACT_ONLY_SUCCESS`/`BOTH_SUCCESS` for F6, which did not materialise in
mid-trajectory Recoverability labels. Nothing was done to resolve it here:
sampling points, Target V4, scenario geometry, transition semantics, safety and
labels are all unchanged, and no attempt was made to find positive examples or
rebalance families. It is handed to the combined audit.

One observation worth recording for that audit, offered as evidence rather than
conclusion: VALIDATION is an **independent replication** of the TRAIN finding on
disjoint layouts and disjoint episodes. That materially strengthens the
structural interpretation over an acquisition-artefact interpretation, but it
does not by itself reconcile the scenario manifest, and the combined audit
should still treat the declared expectations as unexplained.

**F4/N16** is again `EXPECTED_STRUCTURAL_SOURCE_EMPTY` — 6/6 `M = 0`, matching
the 24/24 in TRAIN and the prospective H1R prediction.

## 14. Label gates and weighting (V27)

Only the predeclared frozen gates were applied. No new positive-rate threshold
was invented. Class weighting remains **`NONE_UNWEIGHTED_BCE`** and was not
selected from outcomes.

## 15. Operations (V15/V16/V18)

| metric | value |
|---|---:|
| infrastructure timeout | 243 s, unchanged, never adjusted live |
| infrastructure retry limit | 1 (`rb21_target_operational_execution_contract_v2.json`), semantic retries 0 |
| timeout retries | **0** |
| infrastructure retries | **0** |
| unresolved infrastructure failures | **0** |
| timeout-exceeded events | **0** |
| events over 200 s | **0** |
| median / p95 / p99 event | 4.81 s / 69.6 s / 144.0 s |
| **maximum single-event wall time** | **169.86 s** (F8/N16, 69.9 % of the timeout) |
| Stage A wall / CPU | ~2.6 min / 822.7 s |
| Stage B wall / CPU | 27 min 58 s / 19,594 s |
| **total CPU-hours** | **5.67** |
| swap used | 0 |
| shards / bytes | 12 / 445,716,747 |

Nothing was ever converted from an infrastructure condition into a scientific
disposition, and no scientific workload was reduced — no family, no N and no
long-running cell was skipped.

**On the long-tail warning.** `VALIDATION_OPERATIONAL_LONG_TAIL_WARNING` was
carried in on the strength of TRAIN's 207.1 s maximum (14.8 % headroom). The
timeout was **not** raised preemptively. The realized VALIDATION maximum came in
at 169.9 s — **30.1 % headroom** — so the warning did not materialise into any
timeout or retry. It remains recorded rather than closed: this run does not
prove the tail is safe in general, only that it did not bite here.

## 16. Resume and idempotence (V17)

| metric | value |
|---|---:|
| Stage A records / distinct episodes | 300 / 300 |
| Stage A duplicates | 0 |
| Stage B records / distinct events | 1,285 / 1,285 |
| Stage B duplicates | 0 |
| Stage B events equal Stage A selection | **true** |
| alternate scientific ids created | 0 |
| resumes performed | 0 |

Both stages were resumable at scientific identity throughout; no resume was
needed. Stage B consumed exactly the frozen Stage A selection — it hard-stops if
the resolved control steps or event identities diverge.

## 17. Seals (V28)

| root | SHA256 |
|---|---|
| manifest | `ce67634dba2b4c4b893938be768a4047d2ac7aaa03bfa67e64db21abd6fa12f1` |
| Stage A source-state | `5a0f6fada073d6bdb8ca740433d785aed55728f550695d5d626d15c1c85a611e` |
| candidate evaluation | `53a2b2316c0cc0a3fd2920155c70b732b28a176a106fe9cca2368d7d6569b3b8` |
| pair transaction | `0d014f0a548b756ac6220997cb292f96afbedd33f3ea7da9351de042dee71ed8` |
| row dataset | `28d52af90b67e0e1e6a6099dca8db53776987e4079c81644ddfb0d229db8de22` |
| operational ledger | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` (empty ledger) |
| dataset manifest | `0307028ef3cba85d6d4fe5996e2613795234f86b296d60e65cd5b0a48d7c9221` |
| **composite VALIDATION seal** | **`667b117555a65ad9da7f8e6e7f71b2cfb6843cc66d8e8c35eb68650b7818ca69`** |

The composite seal binds the manifest, all three scientific contract hashes, the
image digest and source commit, the production profile, the exclusion-union
hash, all six roots, the row count and the selected-event count.

Row payloads (446 MB across 12 shards) remain on the target at
`/home/avis/rvt-official-v2-validation/rows`; the repository holds the
manifests, per-shard content hashes and audits — the same pattern TRAIN and V1
used.

**Namespace isolation (V8).** VALIDATION wrote only to the new
`/home/avis/rvt-official-v2-validation` namespace, guarded by an in-runner hard
stop against the TRAIN, canary, pilot and audit paths. The TRAIN namespace file
count was 61 before the run and 61 after.

## 18. Immutability after the run (V29)

| item | verified |
|---|---|
| composite TRAIN seal `a966f318…` | **unchanged** |
| TRAIN shards | 44/44 byte-identical |
| TRAIN rows / duplicates | 90,294 / 0 |
| TRAIN row dataset root `c91414f5…` | recomputed, matches |
| TRAIN dataset manifest self-hash | valid |
| V1 TRAIN manifest `4ac3d2cb…` | unchanged |
| V1 VALIDATION manifest `c991aa30…` | unchanged |
| V1 combined root `7e583ef9…` | unchanged |

Re-verified on the target after generation finished, not merely asserted.

## 19. Closed scopes

Additional TRAIN rows **0** · Residual **0** · training **0** · HP trials **0** ·
checkpoints **0** · optimizer states **0** · Study-A N24 **0** · Study-B **0** ·
final test **0** · V1 mutations **0** · official V2 TRAIN mutations **0**.

## 20. Carry-forwards for the combined audit

1. **`TRAINING_PIPELINE_NOT_V2_READY`** — no module reads the V2 row schema; an
   additive V2 loader enforcing decision-event grouping and the frozen
   event-equal reduction is required before any training. Not needed yet: the
   combined audit comes first.
2. **`VALIDATION_OPERATIONAL_LONG_TAIL_WARNING`** — recorded, did not
   materialise (169.9 s against 243 s).
3. **`SCENARIO_MANIFEST_VS_MID_TRAJECTORY_TENSION`** — F3/F4/F6 zero-positive on
   both topologies in TRAIN *and* independently in VALIDATION, against declared
   scenario expectations. Unresolved by design.
4. **`F4_N16_STRUCTURAL_SOURCE_EMPTY`** — prospectively predicted; 24/24 M=0 in
   TRAIN, 6/6 in VALIDATION.

---

## Verdict

**C — official Study-A Recoverability V2 VALIDATION completed exactly under the
frozen 300-source-episode manifest, passes the frozen ≥30 retained-event
per-primary-family adequacy gate, contains no fabricated source states, no fake
`GENERATION_INVALID` and no partial publication, is sealed, and is ready for a
combined TRAIN+VALIDATION scientific adequacy audit.**

Not A: every scientific and provenance integrity counter is zero; no hard-stop
condition triggered.

Not B: all ten primary families clear the gate, the worst at 2.6× the minimum.

Not D: all 300 episodes and all 1,285 selected events completed; nothing is
outstanding.

Not E: zero timeouts, zero retries, zero unresolved infrastructure failures.

**Recommendation: `AUTHORIZE_COMBINED_RECOVERABILITY_V2_TRAIN_VALIDATION_AUDIT`.**

Training remains **not** authorized and was not performed, even though the gate
passed. The required next sequence is combined audit → V2 training-loader
implementation/qualification → only then training. Residual V2 remains on HOLD.
