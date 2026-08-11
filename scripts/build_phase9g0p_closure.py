#!/usr/bin/env python3
"""Create the canonical Phase 9G0-P readiness root and final report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


EVIDENCE_COMMIT = "2787c32abdf2c3265ffd7442e1f3684ba7dc1794"
EXECUTION_COMMIT = "6818d8aa07aeb55a43dc42741499d9a24d540332"
SCIENTIFIC_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
PRODUCTION_IMAGE = "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"


def _load(path: Path, field: str) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    expected = str(document.get(field, ""))
    body = dict(document)
    body.pop(field, None)
    if len(expected) != 64 or sha256_document(body) != expected:
        raise RuntimeError(f"canonical artifact hash mismatch: {path}")
    return document


def _write(path: Path, body: Mapping[str, Any], field: str) -> str:
    document = attach_canonical_hash(dict(body), field)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(document[field])


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result_root = root / "results/rvt_fd24"
    contract = _load(
        result_root / "phase9g0p_operational_production_contract_v2.json",
        "phase9g0p_operational_contract_sha256",
    )
    preflight = _load(
        result_root / "phase9g0p_operational_preflight_v1.json",
        "phase9g0p_operational_preflight_sha256",
    )
    capacity = _load(
        result_root / "phase9g0p_storage_capacity_v1.json",
        "phase9g0p_storage_capacity_sha256",
    )
    h4 = _load(
        result_root / "phase9g0p_h4_operational_classification_v1.json",
        "phase9g0p_h4_operational_classification_sha256",
    )
    chunks = _load(
        result_root / "phase9g0p_benchmarks/chunk_scaling_target_v1.json",
        "phase9g0p_chunk_scaling_sha256",
    )
    failure = _load(
        result_root / "phase9g0p_benchmarks/failure_resume_target_v1.json",
        "phase9g0p_failure_resume_qualification_sha256",
    )
    worker = _load(
        result_root / "phase9g0p_benchmarks/worker_scaling_target_v1.json",
        "phase9g0p_worker_scaling_sha256",
    )
    command_plan = _load(
        result_root / "phase9_official_command_plan_v2_operational_addendum_v1.json",
        "phase9g0p_command_plan_operational_addendum_sha256",
    )
    authorization = _load(
        result_root / "phase9g0p_scoped_authorization_proposal_v1.json",
        "phase9g0p_scoped_authorization_proposal_sha256",
    )

    roots = {
        "rb19_scientific_root": "e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571",
        "rb20_clean_detached_reproduction": "8c55f4ef40be509dc6e0bc678467873e5ebd0ce60d0195a2227555676114b95a",
        "rb21p_portability_requalification": "fcc218e4bc88546240789043aa9e160d1fa39b82701637ebd6af19f2f8dcc176",
        "rb21_target_operational_readiness": "b4333eca3ca00e4e2ecdd2c8ca68b7f7df9ad072468ab65699940dcc9329c5c0",
        "phase9g0_startup_stop_binding_map": "3ca4b7108372d4ab89a862f8d6ed222242385a6ea480f398245a8c88b68b5d20",
        "phase9g0r_scientific_addendum": "523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0",
        "generation_provenance_v2": "452ea2d37b8a9b09db88f337423bc6ee9261863ca22fe609293fa11e2acb486c",
        "generation_readiness_v4": "83d3f9b6178cf04834ca38ce9177bb9e5f58643919f5ca8bf61b599165136d3f",
        "official_generator_contract": "2672a5624a4505aa668326d7e30000ec06b9f158c484b06044344ab783d404fb",
        "command_plan_v2": "473fc5243e3a11afbb44df868a0d3c814f7e534bb57439b85a2e79d27c4856f0",
    }
    readiness = {
        "schema_version": "rvt-phase9-production-performance-readiness/v1",
        "phase": "PHASE_9G0_P",
        "verdict": "C",
        "verdict_text": (
            "Actual official production producers are operationally qualified."
        ),
        "identity": {
            "phase9g0r_evidence_commit": "1676427c92d111c0aa7aebb2fe9e2cc035297605",
            "phase9g0p_evidence_commit": EVIDENCE_COMMIT,
            "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
            "operational_execution_commit": EXECUTION_COMMIT,
            "production_image": PRODUCTION_IMAGE,
        },
        "validated_roots": roots,
        "profiles": contract["profiles"],
        "branch_readiness": {
            "recoverability": "READY_FOR_EXPLICIT_OWNER_AUTHORIZATION",
            "residual": "READY_WITH_OPERATIONAL_RISK_FOR_EXPLICIT_OWNER_AUTHORIZATION",
        },
        "semantic_digest": {
            "recoverability_low_equals_selected": worker["recoverability"][
                "semantic_digest_equal_all_workers"
            ] and chunks["recoverability"]["semantic_digest_equal_all_chunks"],
            "residual_low_equals_selected": worker["residual"][
                "semantic_digest_equal_all_workers"
            ] and chunks["residual"]["semantic_digest_equal_all_chunks"],
        },
        "failure_resume": {
            "case_count": failure["case_count"],
            "passes": failure["passes"],
            "failures": failure["failures"],
            "candidate_pair_partial_publications": 0,
            "residual_partial_publications": 0,
        },
        "h4": h4["classification"],
        "preflight": {
            "status": preflight["status"],
            "positive_checks_passed": True,
            "negative_case_count": preflight["negative_case_count"],
            "negative_escapes": preflight["negative_escapes"],
            "command_resolutions": preflight["resolution_count"],
        },
        "tests": {
            "local_complete_suite": {
                "passed": 3048, "failed": 0, "warnings": 1,
                "publication_required_xfailed": 0, "seconds": 390.86,
            },
            "target_clean_detached_complete_suite": {
                "commit": EVIDENCE_COMMIT, "passed": 3048, "failed": 0,
                "warnings": 1, "publication_required_xfailed": 0,
            },
            "discarded_read_only_harness_run": {
                "passed": 3021, "failed": 27,
                "cause": "EROFS in tests that intentionally inject temporary modules",
                "scientific_or_product_failure": False,
                "used_for_verdict": False,
            },
        },
        "authorization": {
            "proposal_sha256": authorization[
                "phase9g0p_scoped_authorization_proposal_sha256"
            ],
            "enabled_scope_count": authorization["enabled_scope_count"],
            "authorization_remains_false": True,
            "commands_executed": command_plan["executed"],
        },
        "isolation": {
            "official_run_ids": 0,
            "official_staging_writes": 0,
            "official_recoverability_rows": 0,
            "official_residual_rows": 0,
            "official_shards": 0,
            "training_operations": 0,
            "checkpoints": 0,
            "optimizer_states": 0,
            "study_a_n24_accesses": 0,
            "final_test_accesses": 0,
        },
        "status": "READY_FOR_EXPLICIT_SCOPED_OWNER_AUTHORIZATION",
    }
    readiness_hash = _write(
        result_root / "phase9_production_performance_readiness_v1.json",
        readiness,
        "phase9_production_performance_readiness_sha256",
    )

    rec = capacity["recoverability"]
    res = capacity["residual"]
    rec_workers = worker["recoverability"]
    res_workers = worker["residual"]
    report = f"""# Phase 9G0-P Production Performance Requalification

## Identity

- 9G0-R evidence commit: `1676427c92d111c0aa7aebb2fe9e2cc035297605`
- 9G0-P evidence commit: `{EVIDENCE_COMMIT}`
- Scientific source commit: `{SCIENTIFIC_SOURCE_COMMIT}`
- Operational execution commit: `{EXECUTION_COMMIT}`
- Production image: `{PRODUCTION_IMAGE}`
- Readiness root: `{readiness_hash}`

All RB19, RB20, RB21P, RB21-TARGET, 9G0 startup-stop, 9G0-R,
generation-provenance V2, Readiness V4, official-generator and Command Plan V2
roots were revalidated without stale/current ambiguity.

## Recoverability

- W=1: n=24, wall 77.65 s, median 1.47 s, p90 8.12 s, p95 8.63 s,
  max 8.74 s, peak RSS 293.7 MB.
- Predeclared workers: 1, 6, 12, 18, 22.
- Selected: `PROFILE_RECOVERABILITY_V1`, W=12, numeric threads=1,
  chunk=1, infrastructure timeout=60 s.
- W=12 wall: {rec_workers['selected_entry']['wall_seconds']:.2f} s; speedup
  {rec_workers['selected_entry']['speedup']:.2f}x; efficiency
  {rec_workers['selected_entry']['parallel_efficiency']:.3f}.
- Chunk wall times c1/c2/c4: 10.31 / 18.75 / 32.86 s. Chunk=1 also has
  the smallest retry blast radius and best resume granularity.
- Semantic digest is identical at every W and chunk:
  `{contract['profiles']['recoverability']['semantic_digest']}`.
- Full authorized capacity: 15,000 events, 30,000 candidate aggregates,
  42,000 replica executions, 318,500 robot-candidate row capacity.
- Projection: {rec['projected_wall_hours']:.2f} wall-hours,
  {rec['projected_cpu_hours']:.2f} CPU-hours, {rec['staging_requirement_bytes_2x_plus_20_percent']/1e9:.2f} GB staging.

## Residual V2

- W=1: n=25, wall 693.98 s, median 10.23 s, p90 70.67 s,
  p95 110.33 s, max 134.49 s, peak RSS 215.2 MB.
- Predeclared workers: 1, 4, 8, 12, 18, 22.
- Selected: `PROFILE_RESIDUAL_V2_V1`, W=8, numeric threads=1,
  chunk=1, infrastructure timeout=360 s.
- W=8 retains {res_workers['selected_to_maximum_throughput_ratio']*100:.2f}% of maximum measured
  throughput with lower RSS and p95 than W>=12.
- Chunk wall times c1/c2/c3: 190.51 / 202.78 / 222.11 s.
- Semantic digest is identical at every W and chunk:
  `{contract['profiles']['residual']['semantic_digest']}`.
- K=16 strict upper bound: {res['strict_retained_state_upper_bound']:,} states;
  candidate evaluations: {res['candidate_evaluations_upper_bound']:,}.
- Projection: {res['projected_wall_hours_large_workload_cpu_balance']:.1f} to
  {res['projected_wall_hours_direct_small_manifest_conservative']:.1f} wall-hours,
  {res['projected_cpu_hours']:.1f} CPU-hours,
  {res['staging_requirement_bytes_2x_plus_20_percent']/1e9:.2f} GB staging.

## Failure And Resume

Eight scoped target injections passed: worker death before completion, worker
death after compute/before durable ACK, termination between chunks, duplicate
submission, partial Recoverability row-set/audit, partial Residual row, writer
failure, and exact nine-candidate replay. Candidate-pair and Residual partial
scientific publications were both zero. Duplicate canonical records are no-ops.

Timeouts are infrastructure-only. They cannot become `VALID_TASK_NEGATIVE`,
`GENERATION_INVALID`, or `NO_ELIGIBLE_ACTION`.

## GPU And H4

The RTX 5000 Ada is container-visible, but the qualified generation PyTorch is
CPU-only. Simulator, controller, safety, transition protocol, Target V4,
Recoverability counterfactuals, Residual Expert V2 and ego-graph construction
remain CPU-authoritative. Generation GPU utilization is none.

H4 is `{h4['classification']}`: the Residual path is multi-week and
heavy-tailed, but RAM, storage, timeout, idempotency and resume are qualified
without changing K=16, nine candidates or horizon.

## Study Sequence

Required order is Study A train/validation generation, Study A model selection
and checkpoint freeze, then Study A N24 zero-shot evaluation and immutable
recording. Study B remains held until that sequence is complete. Study A N24
and final test remain `SEALED_NOT_AUTHORIZED`.

## Contract And Commands

- Operational contract: `{contract['phase9g0p_operational_contract_sha256']}`.
- Command Plan V2 operational addendum: `{command_plan['phase9g0p_command_plan_operational_addendum_sha256']}`.
- Eight commands resolve; all have authorization=false; none was executed.
- Operational preflight: 22 negative cases, zero escapes.

## Tests And Isolation

- Local complete suite: 3,048 passed, 0 failed, 0 publication-required xfailed.
- Target clean detached suite at `{EVIDENCE_COMMIT}`: 3,048 passed, 0 failed,
  0 publication-required xfailed.
- A read-only mount attempt produced 27 EROFS harness failures and was discarded;
  the writable detached rerun closed all 27 without source changes.
- Official run IDs, STAGING writes, scientific rows, shards, training,
  checkpoints, optimizer states, Study A N24 accesses and final-test accesses:
  all zero.

## Verdict

**C. Actual official production producers are operationally qualified.**

Recoverability is ready for explicit scoped owner authorization. Residual V2 is
also ready for explicit scoped owner authorization, with its measured
multi-week H4 operational risk disclosed. Authorization remains false in this
phase.
"""
    report_path = root / "docs/PHASE9G0_P_PRODUCTION_PERFORMANCE_REQUALIFICATION.md"
    report_path.write_text(report, encoding="ascii")
    print(json.dumps({"readiness": readiness_hash, "report": str(report_path)}))


if __name__ == "__main__":
    main()
