# Phase 9G-V2A-T — Official Study-A Recoverability V2 TRAIN Generation

**Result: the official TRAIN run completed exactly under the frozen 1200-episode
manifest, with every integrity counter at zero. Verdict C ·
AUTHORIZE_RECOVERABILITY_V2_TRAIN_DATASET_AUDIT.**

**90,294 scientific rows** from **5,032** candidate-blind selected source events.
No fabricated source state, no fake `GENERATION_INVALID`, no partial pair, no
duplicate row, no timeout, no retry, no unresolved infrastructure failure.

**Composite TRAIN seal: `a966f318832fb60bd99acdfdff72f0c7011d730f3e0fb51494ce318210f39bba`**

---

## 1. Authorization

TRAIN only, 1,200 source episodes. VALIDATION, Residual V2, model training, HP
search, Study-A N24, Study-B and final test were **not** executed and remain
unauthorized.

## 2. Target

| item | value |
|---|---|
| host | `avis` — Windows 11 Pro 10.0.26200.9168 |
| account form | `avis\avis`, passwordless SSH key auth (`BatchMode=yes` throughout) |
| WSL | `Ubuntu-24.04`, kernel 6.18.33.2-microsoft-standard-WSL2, 24 CPUs, 33.32 GB |
| Docker | Engine 29.6.1, linux/amd64 |
| image digest | `sha256:2949628f6eb57abafe680687b677958c7cc52bffab84545514a48d84a936c684` |
| image source commit | `f0a923f57fd8bea6b8249fad9652fcd37c674740` (verified in-container) |
| profile | workers 12 · threads 1 · chunk 1 · timeout 243 s · CPU-authoritative, no GPU |

The image was **not** rebuilt, modified or upgraded, and all scientific execution
happened inside it on the target. No credential material appears in any artifact,
script or log.

## 3. Scientific binding

| contract | SHA256 |
|---|---|
| Source-Acquisition Protocol V2 | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` |
| Recoverability Row Binding V2 | `98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8` |
| Target V4 execution contract | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |

All three recovered from committed artifacts and cross-checked against the live
code before launch. The Row Binding value was read in full from
`phase9g_v2i_recoverability_row_identity_v2_contract_v1.json`, not inferred from
an abbreviation.

## 4. Comprehensive exclusion union (A3/A4)

Built externally and additively from every committed design, pilot and
qualification artifact — the runtime scientific code was not touched.

| item | value |
|---|---|
| union SHA256 | `8b5ae40a00a9dc8709b6fab825495792c1091927818b2a7f68f714679f120905` |
| identities | **380** |
| namespaces | `study_a_design_pilot`, `study_a_qualification_canary`, `study_a_v2i_canary` |
| reconstruction failures | **0** — every recorded canary `episode_id` reproduced exactly |
| **TRAIN ∩ union** | **0** |
| VALIDATION ∩ union | 0 |
| TRAIN ∩ VALIDATION | 0 |

This closes the V2Q-R advisory: the `study_a_v2i_canary` namespace is now covered
by an explicit union rather than only by namespace disjointness.

**On V1 source identities.** TRAIN ∩ V1 official *source-episode* identities =
1,200, and that is correct, not a violation. `generation_budget_v1.json` fixes the
1,200-episode Study-A TRAIN budget and the owner resolution changes *acquisition*,
not the episode budget. The freshness requirement is
`merged_into_v2_confirmatory_data = false`, which concerns rows and datasets: V2
rows were generated fresh into a new namespace and **no V1 row was reused or
mutated**.

## 5. Frozen manifest

`OFFICIAL_V2_TRAIN_MANIFEST_SHA256 = 6be6785cef93964b7a2ded21e36a0ae2738dee1e9bc8dfc11715e49516979114`

1,200 source episodes · **120 per family** (F1–F10) · **240 per N** (5, 6, 8, 12,
16) · 6 source policies. N24 0 · Study-B 0 · final-test 0 · VALIDATION identities
0 · duplicates 0. Pre-launch decision: **GO**, zero blocking failures. The
manifest was not modified after freeze.

## 6. Stage A — candidate-blind acquisition

All 1,200 episodes ran and were frozen into an immutable ledger **before any
candidate was evaluated**, so candidate-blindness is structural, not conventional.

| metric | value |
|---|---:|
| source episodes | 1,200 |
| total eligible states | 10,096 |
| **selected source events** | **5,032** |
| episodes with M = 0 | 24 |
| episodes with 1 ≤ M < 5 | 495 |
| episodes with M ≥ 5 | 681 |
| **fabricated source states** | **0** |

Stage A root `06a4b428b26241dcb536dfc11bb9edaecbf699ed2a3441fadb98fbb3b115cb02`.

All 24 `M = 0` episodes are **F4/N16** — precisely the structural cell the H1R
design pilot predicted would fail initialization validity. They contributed 0
events, 0 candidates and 0 rows, and were **not** replenished. The 5,032 selected
events also match the H1R source-only projection of 5,032 almost exactly.

## 7. Stage B — candidate execution

| metric | value |
|---|---:|
| events executed | **5,032 / 5,032** |
| candidate aggregates attempted | **10,064** = 2 × 5,032 |
| candidate replica executions | 14,452 |
| COMPACT positive / valid-negative | 1,768 / 3,264 |
| LINE positive / valid-negative | 1,400 / 3,632 |
| total positives / valid negatives | 3,168 / 6,896 |
| **actual `GENERATION_INVALID`** | **0** |
| **fake `GENERATION_INVALID`** | **0** |

3,168 + 6,896 + 0 = 10,064 — dispositions reconcile exactly against aggregates.

## 8. Pair transactions and rows

| metric | value |
|---|---:|
| retained pair events | **5,032** |
| dropped pair events | 0 |
| **partial publications** | **0** |
| rows published | **90,294** |
| expected exact Σ 2·N over retained events | **90,294** |
| distinct row IDs | 90,294 |
| duplicate row IDs | **0** |
| **row validation failures** | **0** |
| event-identity recomputation mismatches | **0** |

Every one of the 90,294 rows was streamed and re-validated inside the image:
schema `rvt-recoverability-scientific-row/v2`, all three contract hashes exact,
candidate topology authorized, 64-hex graph fingerprint, identity field set
exactly the fourteen V2 fields with no operational contamination, and the row ID
**recomputed from its own identity and matched**. Accounting used the exact
per-event Σ 2·N, never an average N.

## 9. Family × N audit (descriptive only)

Every cell has 24 source episodes. Full table in
`phase9g_v2a_t_official_train_closure_v1.json`; totals:

| | value |
|---|---:|
| source episodes | 1,200 |
| eligible states | 10,096 |
| selected events | 5,032 |
| candidate aggregates | 10,064 |
| replica executions | 14,452 |
| positives / valid negatives | 3,168 / 6,896 |
| retained pair events | 5,032 |
| rows | 90,294 |

Two observations recorded for the **separate** adequacy audit, not acted on here:
F4/N16 is empty (M=0 × 24), and F3, F4 and F6 produced zero positive aggregates
across all N. No protocol, budget or weighting was changed in response.

## 10. Operations

| metric | value |
|---|---:|
| infrastructure timeout | 243 s, unchanged |
| timeout retries | **0** |
| infrastructure retries | **0** |
| unresolved infrastructure failures | **0** |
| timeout-exceeded events | **0** |
| maximum single-event wall time | 207.1 s (85.2 % of the timeout) |
| shards / bytes | 44 / 1,674,191,736 (1.67 GB) |

Nothing was ever converted from an infrastructure condition into a scientific
disposition. **The 207 s maximum is worth attention**: it leaves only ~15 %
headroom under the 243 s timeout. Nothing exceeded it here, but VALIDATION
planning should note the margin rather than assume it.

Stage A ran as one detached container; Stage B as another. Both were resumable at
scientific identity throughout, and no resume was needed.

## 11. Seals

| root | SHA256 |
|---|---|
| manifest | `6be6785cef93964b7a2ded21e36a0ae2738dee1e9bc8dfc11715e49516979114` |
| Stage A source-state | `06a4b428b26241dcb536dfc11bb9edaecbf699ed2a3441fadb98fbb3b115cb02` |
| candidate evaluation | `ea1f92b79f0c88cea41847d5e82dbf62c4f842af7d6092dd131b430d943dc50b` |
| pair transaction | `0ca651b133ac95e338faa4849031d62cac173675b011115eb664bd0841771fcb` |
| row dataset | `c91414f52543d2b0b40c4349000072e1674fc948454e63810ea7d3a66a6287a9` |
| operational ledger | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` (empty ledger) |
| dataset manifest | `cbb8906c75311c53dd203501542ee3a9a77f84e9e92391c27997dee0c4229ef6` |
| **composite TRAIN seal** | **`a966f318832fb60bd99acdfdff72f0c7011d730f3e0fb51494ce318210f39bba`** |

The composite seal binds the manifest, all three scientific contract hashes, the
image digest and source commit, the production profile, the exclusion-union hash,
all six roots, the row count and the selected-event count.

Row payloads (1.67 GB of ego-graph tensors across 44 shards) remain on the target
at `/home/avis/rvt-official-v2-train/rows`; the repository holds the manifests,
per-shard content hashes and audits — the same pattern V1 used.

## 12. V1 immutability

| root | verified |
|---|---|
| V1 TRAIN manifest `4ac3d2cb…` | unchanged |
| V1 VALIDATION manifest `c991aa30…` | unchanged |
| V1 combined root `7e583ef9…` | unchanged |

No V1 row was merged into V2 and no V1 artifact was mutated.

## 13. Closed scopes

VALIDATION rows **0** · VALIDATION runs **0** · Residual **0** · training **0** ·
HP trials **0** · checkpoints **0** · optimizer states **0** · Study-A N24 **0** ·
Study-B **0** · final test **0** · V1 mutations **0**.

Class weighting remains frozen at `NONE_UNWEIGHTED_BCE` and was not selected from
TRAIN outcomes. No adaptive stopping was used; no episode was replenished; the
fixed 1,200-episode manifest ran to completion. The qualified image is retained on
target for a subsequently authorized VALIDATION run.

---

## Verdict

**C — official Study-A Recoverability V2 TRAIN completed exactly under the frozen
1200-source-episode manifest; V2 source acquisition remained candidate-blind; no
fabricated source states or fake `GENERATION_INVALID` records occurred; pair
publication and row identities are exact; the dataset is sealed and ready for a
separate TRAIN dataset adequacy / quality audit before VALIDATION.**

Not A: every integrity counter is zero and no hard-stop condition triggered.

Not B: zero timeouts, zero retries, zero unresolved infrastructure failures.

Not D: all 1,200 episodes and all 5,032 selected events completed; nothing is
outstanding.

**Recommendation: AUTHORIZE_RECOVERABILITY_V2_TRAIN_DATASET_AUDIT.**

VALIDATION is **not** recommended and was not run. The zero-positive families
(F3, F4, F6) and the empty F4/N16 cell are exactly the kind of question the
adequacy audit exists to answer — against the unchanged ≥30 retained
validation-events-per-family gate — and that audit must come first.
