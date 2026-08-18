# Phase 9D-V3F-I — Required-Replica Scientific Invalidity Semantics for Probabilistic Recoverability V3

**Handoff commit (full):** `abab5f477340b7f10c042a66cdfc0adef6024258`
**Branch:** `research/rvt-phase9d-v3f-i-replica-invalidity-freeze-v1`
**Clears stop token:** `V3_REPLICA_INVALIDITY_SEMANTICS_OWNER_DECISION_REQUIRED`

## Outcome

**Verdict A.** The owner-selected `PAIR_NOT_LABELABLE` semantics are compatible
with frozen V3 science. The additive invalidity contract is prospectively frozen
and Phase 9G-V3I-Q may resume implementation and qualification.

**Recommendation: `RESUME_RECOVERABILITY_V3_IMPLEMENTATION_AND_QUALIFICATION`.
DO NOT GENERATE DATA.**

**New frozen contract**
`RECOVERABILITY_V3_REQUIRED_REPLICA_INVALIDITY_CONTRACT_V1`
`66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75`

Row Binding V3 is **unchanged**, so verdict C was not triggered. No frozen
contract mandated a different behaviour, so verdict B was not triggered.

---

## The ten questions

### Q1. What happens if 1 of R required replicas is scientifically `GENERATION_INVALID`?

The candidate is **not scientifically labelable**. No supervision exists,
`(k, R)` is `UNDEFINED`, and the whole `(COMPACT, LINE)` pair publishes **zero**
supervised robot-local rows. All `R_required` replicas of **both** candidates are
still executed — contract clause C7 forbids early abort — and every replica
disposition, every valid `Y_r` that did exist, and the pair transaction are
retained in the audit ledger.

### Q2. Why is R not reduced?

Because a data-dependent `R_required → R_valid` would violate four things at
once: the fixed replica protocol; `adaptive_replication = DISABLED` and
`R_expansion_permitted = false`; the outcome-independent observation design; and
the frozen row-binding sentence *"R is bound through
`recoverability_replica_protocol_v3_sha256`, not through an outcome payload
field. The protocol fixes R per family, so identity determines R without
recording it."* If R could vary with the observed data, identity would no longer
determine R. `SHRINK_R_ON_INVALID = FORBIDDEN`.

### Q3. Why is the invalid replica not counted as Y = 0?

The frozen normalized grouped Bernoulli likelihood
`-[k·log p + (R−k)·log(1−p)] / R` assumes **R actual Bernoulli observations**. A
scientific-invalid rollout is not a Bernoulli task-success failure — it is a
simulation whose output is undefined. Placing it in the `(R−k)` term silently
converts a non-observation into `Y = 0` and changes the scientific target.
`INVALID_AS_FAILURE = FORBIDDEN`. Target V4 already refuses this on its own:
`evaluate_target_v4` returns `TargetV4EvaluationResult(GENERATION_INVALID, None,
…)` — the label is `None`, never 0 and never 1.

### Q4. Is a replacement replica allowed?

No. No sampling of replica `r + R`, no replacement seed, no reroll until valid —
each would create outcome-dependent replication. The candidate remains
non-labelable under the fixed prospective replica set. There is likewise no
outcome-dependent refill at any level: a dropped source event triggers no
replacement episode, no replacement selected source state, no extra event, no
extra replica and no budget refill. The 1200 / 300 source-episode manifests stay
fixed.

### Q5. What happens to the other candidate in the pair?

It is fully executed and fully audited, but **not published**. The pair is
scientifically publishable iff both candidates are labelable: either
`2 × N_event` rows, or 0. Publishing the surviving candidate alone, or a partial
robot set, is forbidden. This is already the shipped behaviour —
`reconcile_candidate_pair` returns `rows = ()` with
`training_rows_committable = False` — and gate D4 holds partial candidate-pair
publication at threshold 0.

### Q6. Are audit records retained?

Yes. Scientific invalidity blocks supervised row publication; it does not erase
evidence. Nine classes of evidence are retained: source-event identity, both
candidate-event identities, every replica-evaluation identity, every executed
replica disposition, the valid `Y_r` values that did exist, which replica indices
were invalid, Target-V4 predicates and provenance, matched stream identities, and
the pair transaction disposition. Identities created before outcomes were
observed are never mutated — outcome does not alter identity. The repository
already states the principle: *"Attempted decision states never vanish; that is
the point."*

Placeholder supervised rows (`k = null`, `label = null`, invalid flags) are
forbidden. Operational and audit ledgers stay separate from supervised row
shards.

The audit disposition is the existing repository-consistent status
`SCIENTIFICALLY_RECONCILED_GENERATION_INVALID`, which the owner explicitly
permitted in place of the suggested alias `PAIR_NOT_LABELABLE_SCIENTIFIC_INVALID`.
Adopting the existing string means no shipped V1/V2 code path has to change. It
is an audit disposition, never a Recoverability training label.

### Q7. How is infrastructure failure different?

A timeout, worker crash, process death, serialization/network/transport failure,
or unexecuted scheduled work produces **no Bernoulli observation and no
`GENERATION_INVALID` disposition**. It is handled by the frozen infrastructure
retry/resume contract and must never be converted into `Y = 0`, into
`GENERATION_INVALID`, or into candidate non-labelability.

The separation is already frozen in two independent places:

- `COUNTS_IN_SCIENTIFIC_DENOMINATOR` marks `INFRASTRUCTURE_FAILURE: False` with
  the comment *"not a scientific outcome; it is retried"*, while
  `EXECUTION_INVALID: True`.
- `reconcile_candidate_pair` returns `PENDING_INFRASTRUCTURE_RESOLUTION` with
  `scientifically_reconciled = False` — a different status from
  `SCIENTIFICALLY_RECONCILED_GENERATION_INVALID`.

The boundary is **where the exception is caught**. An exception escaping the
scientific call is caught by `_execute_candidate_with_one_infrastructure_retry`
and classified `INFRASTRUCTURE_FAILURE` after one byte-identical replay; it never
reaches `evaluate_target_v4`. `EXECUTOR_EXCEPTION` — a `GENERATION_INVALID` cause
— is a typed termination of an execution that *did* complete and report.
Implementation must preserve that catch boundary exactly.

### Q8. How does S8 protect against excessive censoring?

Because non-labelable pairs are censored from the supervised dataset, an
excessive invalid rate would leave the supervised rows no longer representative
of the intended prospective source-event distribution. S8 bounds that.

Repository authority is final and reads: **"invalid rollout rate is below 0.02
overall and below 0.05 in every family"** (frozen label-audit gate 6,
`f9171f37…`), carried into V3 unchanged as gate S8.

Exact accounting, frozen in clause C12:

- **numerator** — executed required Target-V4 replica rollouts whose disposition
  is `GENERATION_INVALID`
- **denominator** — executed required Target-V4 replica rollouts
- **unit** — the replica rollout, not the candidate aggregate and not the source
  event
- censored rollouts **remain in the denominator**; infrastructure failures are
  **excluded**, because they are not scientific outcomes
- source termination before a scheduled event is denominator evidence, not an
  executed invalid rollout

No hidden denominator changes. Reinterpreting invalid rollouts as labels to
improve retention is forbidden. For calibration, V2 measured **0** actual
`GENERATION_INVALID` rollouts across TRAIN and VALIDATION.

### Q9. Does Row Binding V3 need to change?

**No.** Row identity is left byte-for-byte unchanged at
`bdab65bd…`, sixteen fields.

The strongest case *for* changing it is real and worth stating: under a different
invalidity rule the same row identity could carry a different `(k, R)`. For
outcomes `{Y₀ = 1, INVALID, Y₂ = 0}` at R = 3, rule C would publish `k = 1,
R = 3` while rule A publishes nothing — so the rule looks semantically
load-bearing for the payload.

It does not carry, for a precise reason. Under rule A, `(k, R)` means exactly
what the **already-bound** frozen probabilistic target contract says it means:
`k` is the *"sum over replicas r of Y_{e,tau,r}"* and `R` is *"the frozen replica
count for the family and candidate"*. Rule A is the only rule under which that
frozen sentence stays literally true of every published row. Rules B and C would
have required amending the probabilistic target contract itself — and that hash
is already one of the sixteen identity fields, so the identity would have changed
through the existing binding rather than needing a new one.

Supporting reasons: rows exist only for labelable transactions, so no published
row is ambiguous; the rule determines *whether* a row exists, not *what* it is;
identity must stay outcome-independent and non-labelability is observed only
after outcomes exist; `recoverability_row_binding_v3_spec_sha256` is itself an
identity field, so changing the spec would change every V3 row id and force a
broader owner re-freeze; and the censoring effect is a property of the published
*population*, which the manifest and seal already carry.

### Q10. What new provenance object/hash must implementation bind?

The binding rule is stated once and applied mechanically: **an object binds
`recoverability_v3_required_replica_invalidity_contract_v1_sha256` if and only if
the invalidity rule determines that object's content or its admissibility.**

| Object | Binds | Why |
|---|:--:|---|
| Official rollout configuration | **no** | fixed before any disposition exists; the rule cannot change it |
| Candidate task provenance | **no** | outcome-independent, and identities are never mutated after the fact |
| Candidate supervision provenance | **yes** | whether the record exists, and the rule forming `k` and `R`, is exactly what the contract governs; the F6 record is `is_scientific_identity: false`, so this is additive payload |
| Pair transaction provenance | **yes** | its status and `training_rows_committable` flag *are* the rule applied |
| V3 dataset manifest | **yes** | declares the retained population and carries the C13 invalidity accounting |
| V3 dataset seal | **yes** | must cover the manifest so a dataset built under another rule cannot masquerade |
| V3 row identity | **no** | see Q9 |

Implementation must **fail closed**: refuse to begin official generation, and
refuse to emit any supervision record or pair transaction, if the contract hash
is absent or differs from `66bdd9ff…`. It must never silently default to a rule
and never infer one from observed data.

---

## A1 — compatibility audit

Nine axes audited: Target V4, the V3 probabilistic target, the fixed replica
protocol, row identity, pair atomicity, the event-equal loss, the Brier metric,
gate S8, and historical V1/V2 validity semantics. **Zero conflicts.** No
`OWNER_DECISION_CONTRACT_CONFLICT`.

The central finding is that the owner decision is **not a new rule**. It is the
already-shipped V1/V2 behaviour restated for a `(k, R)` observation:

- `CandidateResult.aggregate_label` returns `None` when any replica is
  `GENERATION_INVALID`
- `CandidateAggregateDisposition.__post_init__` raises *"non-labelable aggregate
  must not carry a label"*
- `reconcile_candidate_pair` returns zero rows, non-committable, with a status
  distinct from the infrastructure one
- `producer_v2` builds rows only when `labelable` is true

### Independent adversarial audit

Eight independent read-only auditors, one per frozen scope, each instructed to
*refute* compatibility and to default to "no conflict" unless able to quote text
mandating something else. **All eight completed and all eight returned
`conflict_found: false`.** Zero hard conflicts. Six tensions were raised.

The automated verification stage and the completeness critic **did not run** —
the session hit a usage limit and six verifier agents errored out. Every tension
was therefore verified by hand against the cited file. All six were resolved;
none survived.

| # | Tension | Resolution |
|---|---|---|
| TN1 | `outcome_dependent_filtering_permitted: false` forbids dropping a pair *(raised independently twice)* | those flags live inside `mixed_outcomes`, whose patterns `001…110` are **valid** outcomes and whose sibling `is_generation_invalid: false` says so. The ban is on filtering by the *value* of a valid observation — what V3D D28 calls deleting the 59 boundary events. An invalid candidate has no valid observation to filter by. |
| TN2 | `"Invalid rollout rows are masked and counted, never relabelled"` mandates in-dataset masking | *"never relabelled"* is the non-imputation rule verbatim; *"counted"* is the no-hidden-denominator rule. "Masked" means contributes nothing to the loss — publishing zero rows achieves that a fortiori, and is already how the repository realizes masking for Recoverability. In-dataset masking in the same paragraph is scoped to the **residual** term. The V3 loss contract already records `contradiction: false` against this authority. |
| TN3 | `targets.py` computes `label = int(not invalid and all(outcomes))`, giving an invalid candidate the integer 0 | that integer never reaches a published row. The official path returns `GENERATION_INVALID, None`, and the dataclass **raises** if such an aggregate carries a label. `_v2_rows` emits identity and graph payload only — no label field at all — and runs only when labelable. |
| TN4 | `"every exception becomes typed EXECUTOR_EXCEPTION"` leaves no room for infrastructure failure | separated by *where* the exception is caught — see Q7. |
| TN5 | Censoring threatens gate S4 (≥30 retained validation pairs); replica accounting may break | S4 is measured after generation, not a rule for handling invalidity; making a gate harder to pass is not a contract conflict, and S8 is the predeclared bound on exactly that risk. Replica accounting is stated over *aggregates*, not *published* aggregates, and C7 forbids early abort so the identity stays exact. |
| TN6 | `"coverage: 1.0 — every event is supervised"` | a property of the V3D design **option matrix** comparing target types, not a frozen contract, and silent about invalid rollouts. |

**The one reading that would have conflicted** is C: `k` would no longer be the
"sum over replicas r of `Y_{e,tau,r}`" the frozen target contract defines, so
`recoverability_probabilistic_target_v3_sha256` would have had to change — and
that hash is a row-identity field, so every V3 row id would have changed with it.
The owner rejected C.

---

## A2 — the frozen contract

`RECOVERABILITY_V3_REQUIRED_REPLICA_INVALIDITY_CONTRACT_V1`, fifteen clauses,
additive, superseding nothing:

C1 required-replica definition · C2 scientific-validity predicate authority ·
C3 candidate labelability rule · C4 non-imputation · C5 no shrink-R ·
C6 no replacement replica · C7 no early abort · C8 pair atomicity ·
C9 audit disposition · C10 audit-evidence retention ·
C11 infrastructure/scientific separation · C12 S8 relationship ·
C13 invalidity accounting · C14 no outcome-dependent refill ·
C15 unchanged contracts.

C7 is the one clause not stated verbatim in the owner decision; it is **derived**
from gates D5, S2, S3 and the S8 denominator, all of which break if replicas or
candidates are short-circuited once invalidity is seen. It matches existing
behaviour, where the producer aggregates over the complete replica sequence and
executes both candidates before reconciling.

C13 requires eight counters to be reported separately — required replica
evaluations, valid replicas, invalid replicas, supervision records created,
supervision blocked, pair events retained, pair events dropped for scientific
invalidity, robot rows published — plus per-family/candidate/N invalidity rates.

---

## A5 — mandatory tests for Phase 9G-V3I-Q

Eleven numbered cases, plus four additional assertions, none implemented here:

| # | Case | Required outcome |
|---|---|---|
| T1 | R=3, `111` | `(3, 3)`, rows published |
| T2 | R=3, `101` | `(2, 3)`, rows published |
| T3 | R=3, `000` | `(0, 3)`, rows published |
| T4 | R=3, valid success / **invalid** / valid failure | no `(k, R)`; not labelable; must not yield `(1,3)`, `(1,2)` or `(2,3)` |
| T5 | COMPACT labelable, LINE invalid | 0 pair rows |
| T6 | COMPACT invalid, LINE labelable | 0 pair rows |
| T7 | both invalid | 0 pair rows |
| T8 | infrastructure timeout on one replica | not scientific invalid; `PENDING_INFRASTRUCTURE_RESOLUTION`; retry/resume; no `Y` imputation |
| T9 | scientific invalid | no replacement replica; exactly `R_required` executions; no early abort |
| T10 | invalid pair | audit evidence preserved; supervised rows absent |
| T11 | S8 | numerator/denominator exact, censored rollouts in the denominator, infrastructure excluded |

Plus: T12 fail-closed on a missing or wrong contract hash; T13 no supervised row
ever carries a disposition, invalid flag, or null `k`/`R`; T14 row identity
remains the sixteen frozen fields; T15 the loss and Brier interfaces cannot
express a per-replica mask or accept a non-labelable candidate.

---

## A6 — V2 history unchanged

V2 rows modified 0, V2 contracts modified 0, both seals untouched. Gate 7 remains
**`FAILED_FOR_V2`** at TRAIN F9/LINE **59/530 = 0.11132075471698114 > 0.10**,
never marked passed, threshold never changed. For V3 it stays
`NOT_APPLICABLE_TO_V3_PROBABILISTIC_TARGET`.

## A7 — no scientific execution

V3 source episodes executed 0 · candidate rollouts 0 · Target-V4 evaluations 0 ·
V3 rows 0 · models trained 0 · HP trials 0 · images built 0 · V3 runtime code
written 0 · replica counts changed 0 · probabilistic target semantics changed 0 ·
source acquisition modified 0 · Target V4 modified 0 · V2 modified 0 · N24,
Study-B and final-test accesses 0.

The change is purely additive: seven new artifacts, one new test file, and one
narrowed glob in an existing test (see below). No existing artifact byte changed.

---

## Artifacts

- `results/rvt_fd24/phase9d_v3f_i_owner_decision_v1.json`
- `results/rvt_fd24/phase9d_v3f_i_invalidity_contract_v1.json`
- `results/rvt_fd24/phase9d_v3f_i_contract_compatibility_v1.json`
- `results/rvt_fd24/phase9d_v3f_i_provenance_binding_v1.json`
- `results/rvt_fd24/phase9d_v3f_i_required_tests_v1.json`
- `results/rvt_fd24/phase9d_v3f_i_implementation_handoff_v1.json`
- `results/rvt_fd24/phase9d_v3f_i_final_readiness_v1.json`
- `tests/test_phase9d_v3f_i_replica_invalidity_freeze.py` — 89 tests, all passing

`tests/test_phase9d_v3f_probabilistic_freeze.py` needed one narrowing edit: its
`phase9d_v3f_*.json` glob matched the new `phase9d_v3f_i_*` addendum, exactly as
it once matched `phase9d_v3f_l_*`. The exclusion list was extended so the
assertion still reads *exactly 18 Phase 9D-V3F artifacts*; the assertion was not
weakened.

Full suite: **4144 passed, 2 failed**. Both failures
(`test_phase9g0r_official_binding.py::test_command_resolve_binds_manifest_and_narrow_authorization`
and `test_phase9g_a1v_validation.py::test_a1v_runner_resolves_exact_empty_validation_boundary`)
are **pre-existing at the handoff commit** — verified by re-running them on a
clean tree — and are environmental: the spawned subprocess cannot import
`rvt_swarm` because it does not inherit `PYTHONPATH`.

## Next phase

Phase 9G-V3I-Q resumes at gate I2 and runs unchanged in every other respect,
binding `66bdd9ff…` and failing closed without it. It may implement and qualify.
It may not generate official V3 data.
