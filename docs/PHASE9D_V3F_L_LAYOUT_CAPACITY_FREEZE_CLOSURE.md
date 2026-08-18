# Phase 9D-V3F-L — V3 Train-Layout Capacity Owner Addendum and Final Freeze Closure

**Verdict A — the prospective layout-capacity amendment is clean. 20 TRAIN and
10 VALIDATION layouts are frozen, all 27 disjointness axes return zero, no
non-layout science changed, and the planned scientific budget is bit-identical.**

**Recommendation: `AUTHORIZE_RECOVERABILITY_V3_IMPLEMENTATION_AND_QUALIFICATION`.**

Fully prospective: 0 episodes executed, 0 selected events, 0 Target-V4
evaluations, 0 replica rollouts, 0 rows, 0 labels observed.

---

## 1. Owner decision

| offset | generator coordinate | role | layouts |
|---|---|---|---:|
| **0.22** | (train, variant 2) | **added — V3 TRAIN only** | 10 |
| **0.54** | (validation, variant 1) | retained — V3 TRAIN | 10 |
| **0.65** | (validation, variant 2) | retained — V3 VALIDATION | 10 |
| 0.33 | (train, variant 3) | **UNUSED_RESERVE** | 0 in either split |
| 0.76 / 0.87 | (validation, variants 3/4) | **FORBIDDEN** | 0 |

Scope is `LAYOUT_CAPACITY_ONLY`. No target, replica, row, loss or metric
decision was reopened. The addendum records explicitly that this is **not**
outcome tuning — no V3 outcome exists to tune toward, and the decision precedes
implementation, qualification, generation and training.

## 2. Offset 0.22 — verified from the generator, not from prose

`offset = _SPLIT_OFFSETS['train'] + 0.11 × 2 = 0.0 + 0.22`, i.e. **train-split
variant 2**. The frozen `_SPLIT_VARIANTS['train']` is `(0, 1)` — **variant 2 has
never been used**.

| check | result |
|---|---|
| defined by repository-authoritative generation | ✓ |
| in the frozen train variant tuple | **no** — so V2 never used it |
| geometry ∩ V2 TRAIN | **0** |
| geometry ∩ V2 VALIDATION | **0** |
| geometry ∩ 0.54 / 0.65 / 0.33 | **0 / 0 / 0** |
| is a final-test variant | **no** (final base 0.79) |
| is Study-A N24 or Study-B | **no** |

Recomputed from the live generator and the committed V2 job manifest. Only
layout metadata was materialized: **0 source-policy rollouts, 0 candidate
rollouts, 0 Target-V4 evaluations, 0 outcomes.**

## 3. Final capacity — intended design restored

| | layouts | episodes | per layout (min / max / mean) | uniform |
|---|---:|---:|---|:--:|
| **V3 TRAIN** | **20** | 1,200 | **60 / 60 / 60.0** | ✓ |
| **V3 VALIDATION** | **10** | 300 | 30 / 30 / 30.0 | ✓ |

TRAIN is 2 layouts per family across F1–F10; VALIDATION is 1 per family. The
60 episodes/layout figure was **not forced** — it falls out of the deterministic
manifest structure (10 families × 5 N × 6 policies × 2 layouts × 2 episode
indices = 1,200), which is exactly the V2 TRAIN design.

`V3_TRAIN_LAYOUT_SET_FINAL_V1`: 20 unique layout ids, 20 unique
`layout_sha256`, 20 unique geometry hashes, 20 unique parameter tuples — **no
duplicate geometry disguised under different ids**.

## 4. Contract preservation — nothing non-layout moved

| contract | hash | status |
|---|---|---|
| probabilistic target | `a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6` | unchanged |
| replica protocol | `6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a` | unchanged |
| row binding V3 | `bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c` | unchanged |
| training loss | `fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11` | unchanged |
| Brier metric | `0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04` | unchanged |
| source acquisition | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` | unchanged |
| Target V4 | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` | unchanged |

**The row-binding question was answered from the contract, not guessed.** Its
`row_identity_fields` bind **`layout_sha256`** and contain **no registry hash**.
So changing which layouts a split contains does *not* invalidate the row-binding
hash: a row identity is pinned to the specific geometry it was built from, and
adding fresh geometries creates new row identities without disturbing the
contract that defines them.

**H1 unchanged.** `H1_OWNER_REWORDING_REQUIRED = false`. Layout diversity is a
data-design property affecting how well a model may generalize — not what the
hypothesis claims. Primary metric, comparator set and 0.08 threshold all
untouched.

## 5. New prospective roots

| object | hash |
|---|---|
| `V3_LAYOUT_SPLIT_REGISTRY_V2` | `5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a` |
| V3 TRAIN manifest (dry, final) | `ffb1fe3363908369096f4fd8463fe3a8cd5434cb0a4d48d5a39382df7ced4898` |
| V3 VALIDATION manifest (dry, final) | `72f88a6269358063047bf43edfb304f23e3a26d62bacdb2be07a01cc9c836076` |
| V3 exclusion union V2 | `d39febcb3aa9c0cedce92560cf3fff68a5891b60e9d9273c8376b57b64fcacb9` |

The VALIDATION layout set is unchanged, but its manifest hash necessarily moves
because it now cites the V2 registry root.

**The superseded registry is preserved, not erased.**
`d84d0fb9699dad7d6fe4783d2bd55e1b644ed027948291aeb75148e88ea54dae` is recorded as
`SUPERSEDED_PRE_GENERATION_CAPACITY_VERSION`; its artifact still exists and still
self-verifies. Frozen V2 scenario code was not edited — the registry is additive
and references the unchanged generator.

## 6. Disjointness — 27 axes, all zero

Strengthened from 19 axes. Added: **layout_id axes across every split pair**,
**seed/stream identity between the two V3 splits**, and **explicit RESERVE
offset-0.33 exclusion from both splits**.

V3 TRAIN ∩ V3 VALIDATION = 0 on identity, `episode_id`, `layout_sha256`,
`layout_id` and seed/stream identity. Both V3 splits ∩ V2 TRAIN, V2 VALIDATION
and the development exclusion union = 0 on identity, `episode_id`,
`layout_sha256` and `layout_id`.

Development domains covered: V2 TRAIN/VALIDATION, H1R pilots, V2Q/V2I/V2I-RC/V2QR
canaries, V2 dataset audits (read-only, created no identity), V2 gate-7 forensic
identities (the replay drew only from official V2 identities and published 0
rows), V3D design evidence (executed no identity).

**Final domain: 0 identities enumerated, 0 outcomes inspected.** Proof is by the
existing guards — `generate_layouts` raises `PermissionError` for `final_test`
and `derive_seed` refuses final-test derivation — plus the generator's own offset
arithmetic separating 0.22/0.54/0.65 from the final base 0.79.

**Exclusion union membership is unchanged at 1,880 identities.** It is re-emitted
only because the manifests it must be proved against have new roots; no
development identity was added or removed.

## 7. Layout-id semantics — the hazard is real, and tested

V3 TRAIN legitimately contains **both** `validation-f1-01` (offset 0.54) and
`train-f1-02` (offset 0.22). A naive parser would classify the first as
VALIDATION. It is TRAIN.

**Frozen rule**: the split is determined by `study`, `split`, manifest identity
and registry membership — **never** by `layout_id` prefix, `layout_id` substring,
the string `"train"`, the string `"validation"`, or `generator_split_namespace`.

The regression test picks the worst-case layout — a TRAIN layout whose id begins
`validation-` — asserts that naive string inference gets it *wrong*, then proves
every authoritative path still returns TRAIN: registry membership, the
`v3_split` field on all 60 of its manifest episodes, the `/v3_train/` segment of
each `episode_id`, and its total absence from the VALIDATION manifest.

## 8. Compute — identical, as it should be

| | replica rollout cap | CPU-h | wall @ 12 workers |
|---|---:|---:|---:|
| V3 TRAIN | 16,800 | 25.56 | 2.13 h |
| V3 VALIDATION | 4,200 | 6.39 | 0.53 h |
| **combined** | **21,000** | **31.95** | **2.66 h** |

**Exactly the previously planned 21,000** — unchanged, as a pure layout-diversity
change should be. The amendment redistributes the same 1,200 TRAIN and 300
VALIDATION episodes across more distinct geometries; family and N distributions,
the K = 5 cap, the two-candidate rule and the replica protocol (F8/F9 R = 3,
others R = 1) are all untouched.

Workers 12, threads 1, chunk 1, timeout 243 s, replica counts and source budgets
**were not changed** by layout diversity.

## 9. Historical V2

Gate 7 remains **`FAILED_FOR_V2`** at **59 / 530 = 0.11132075471698113** against
a permitted **0.10**. Threshold unchanged, result unchanged, not reinterpreted.
Both V2 seals verify unchanged.

## 10. Execution counters

V3 source episodes executed **0** · selected source events **0** · Target-V4
evaluations **0** · replica rollouts **0** · scientific rows **0** · labels
observed **0** · V3 code implemented **0** · V2 mutations **0** · gate-7
modifications **0** · N24 **0** · Study-B **0** · final test **0**.

## 11. Implementation handoff

The next phase consumes **only** `V3_LAYOUT_SPLIT_REGISTRY_V2`, the final TRAIN
manifest and the final VALIDATION manifest.

**Fail-closed requirement**: the executable implementation must **refuse** to
begin official generation if handed the superseded 10-layout TRAIN registry or
any manifest citing it — comparing the manifest's registry hash against the
authoritative root and **raising rather than warning**, with no silent upgrade
or downgrade. The two superseded V3F manifests are named explicitly.

Full suite: **0 failures**, 67 new tests.

---

## Final verdict

**A** — the prospective V3 layout-capacity amendment is clean: 20 TRAIN and 10
VALIDATION layouts are frozen, all disjointness checks pass, no non-layout
science changed, and V3 is ready for implementation and qualification.

**Recommendation: `AUTHORIZE_RECOVERABILITY_V3_IMPLEMENTATION_AND_QUALIFICATION`.**

Do not generate V3 data. Do not implement V3 in this phase. Do not train. Do not
modify V2. Do not change historical gate 7. Do not access N24, Study-B or the
final test.
