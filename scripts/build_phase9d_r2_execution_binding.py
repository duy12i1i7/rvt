#!/usr/bin/env python3
"""Build the canonical source-symbol binding for the Phase 9D-R2 audit."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


AUTHORITATIVE_COMMIT = "c16f16a97dca423e4c3ce15d2f7e398f1f98607e"


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def sha256_document(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def source_binding(
    root: Path,
    *,
    stage: str,
    path: str,
    symbol: str,
    start: int,
    end: int,
    condition: str,
    result: str,
) -> Mapping[str, Any]:
    lines = (root / path).read_text(encoding="ascii").splitlines()
    if start < 1 or end > len(lines) or start > end:
        raise ValueError(f"invalid source range for {path}:{start}-{end}")
    excerpt = "\n".join(lines[start - 1:end]) + "\n"
    if symbol.rsplit(".", 1)[-1] not in excerpt:
        raise ValueError(f"symbol marker is absent from {path}:{start}-{end}")
    return {
        "stage": stage,
        "source_path": path,
        "symbol": symbol,
        "line_start": start,
        "line_end": end,
        "git_blob_sha1": git(root, "rev-parse", f"{AUTHORITATIVE_COMMIT}:{path}"),
        "source_range_sha256": hashlib.sha256(excerpt.encode("ascii")).hexdigest(),
        "stable_code_identifier": (
            f"git:{AUTHORITATIVE_COMMIT}:{path}:{symbol}:{start}-{end}:"
            f"sha256:{hashlib.sha256(excerpt.encode('ascii')).hexdigest()}"
        ),
        "condition_or_action": condition,
        "scientific_result": result,
    }


def dependency_versions() -> Mapping[str, str]:
    result = {}
    for package in ("numpy", "torch", "pytest"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "NOT_INSTALLED"
    return result


def build(root: Path) -> Mapping[str, Any]:
    if git(root, "rev-parse", "HEAD") != AUTHORITATIVE_COMMIT:
        raise RuntimeError("execution binding must be built from the authoritative commit")
    definitions = (
        dict(
            stage="experiment family/layout",
            path="rvt_swarm/phase8/scenario.py",
            symbol="SCENARIO_FAMILIES",
            start=181,
            end=263,
            condition="F1..F10 declare geometry purpose and 90..180 s source horizons.",
            result="Family and source-horizon authority exists before episode compilation.",
        ),
        dict(
            stage="event schedule construction",
            path="rvt_swarm/phase9b/identity.py",
            symbol="map_event_slots",
            start=219,
            end=256,
            condition="Study A uses five normalized slots; ceil(normalized*horizon/control_period).",
            result="Every scheduled event has a fixed control step independent of source outcome.",
        ),
        dict(
            stage="event identity materialization",
            path="rvt_swarm/phase9c/manifest.py",
            symbol="build_phase9_job_manifest",
            start=148,
            end=260,
            condition="Create every event ID with availability PENDING_SOURCE_EXECUTION.",
            result="The denominator counts scheduled identities before source-state realization.",
        ),
        dict(
            stage="official task compilation",
            path="rvt_swarm/phase9g0r/compiler.py",
            symbol="compile_recoverability_tasks",
            start=155,
            end=199,
            condition="Bind event ID, resolved control step and complete candidate-replica universe.",
            result="Executable event tasks retain the precompiled time schedule.",
        ),
        dict(
            stage="source episode creation",
            path="rvt_swarm/phase9g0r/producer.py",
            symbol="build_source_session",
            start=86,
            end=130,
            condition="Bind layout, runtime, source policy, seeds and SimulatorEpisodeSession.",
            result="A deterministic source episode is constructed for each event task.",
        ),
        dict(
            stage="source-policy execution",
            path="rvt_swarm/phase9c_rb/policies.py",
            symbol="SourcePolicy.observe",
            start=23,
            end=54,
            condition="One typed robot-local observe call per robot per control step.",
            result="S0..S5 source behavior runs inside the source simulator step.",
        ),
        dict(
            stage="source advancement/event predicate",
            path="rvt_swarm/phase9g0r/producer.py",
            symbol="_run_source_to_step",
            start=133,
            end=139,
            condition="Step while nonterminal and control_step < resolved_control_step.",
            result="Source execution stops at the scheduled step or at earlier terminal state.",
        ),
        dict(
            stage="control-step ordering and terminal detection",
            path="rvt_swarm/phase9c_rb/session.py",
            symbol="SimulatorEpisodeSession.step",
            start=473,
            end=568,
            condition=(
                "Communicate; source observe/controller/safety; integrate; increment clock; "
                "collision; progress/deadlock/goal; protocol lifecycle; horizon."
            ),
            result="Terminal state is available to the producer after each completed step.",
        ),
        dict(
            stage="collision and source terminal paths",
            path="rvt_swarm/phase9c_rb/session.py",
            symbol="_check_collisions",
            start=578,
            end=615,
            condition="Swept static/dynamic/boundary/robot clearance violation.",
            result="COLLISION or WORLD_BOUNDARY_EXIT terminal at the incremented control step.",
        ),
        dict(
            stage="goal/deadlock source terminal paths",
            path="rvt_swarm/phase9c_rb/session.py",
            symbol="_update_progress",
            start=647,
            end=700,
            condition="Deadlock window or downstream goal dwell completes.",
            result="PERSISTENT_DEADLOCK or GOAL_COMPLETE terminal after collision evaluation.",
        ),
        dict(
            stage="source snapshot acquisition",
            path="rvt_swarm/phase9g0r/producer.py",
            symbol="produce_recoverability_candidate",
            start=235,
            end=289,
            condition=(
                "Only termination.control_step < event step returns without snapshot; equality "
                "falls through to snapshot and ego-graph construction."
            ),
            result=(
                "Earlier terminal produces no candidate audit; reached/same-step state produces "
                "a canonical snapshot and N graphs."
            ),
        ),
        dict(
            stage="counterfactual snapshot serialization",
            path="rvt_swarm/phase9c_rb/counterfactual.py",
            symbol="snapshot",
            start=140,
            end=209,
            condition="Serialize execution state, hash it, and deep-copy the complete session.",
            result="Both candidates restore from one immutable source-state identity.",
        ),
        dict(
            stage="robot-local ego graph construction",
            path="rvt_swarm/decentralized/ego_graph_runtime_adapter.py",
            symbol="RobotLocalEgoGraphRuntimeAdapter.build",
            start=21,
            end=40,
            condition="Build one graph from one RobotView and explicit candidate topology.",
            result="N candidate-local graph payloads are available for row expansion.",
        ),
        dict(
            stage="COMPACT/LINE counterfactual rollout",
            path="rvt_swarm/phase9c_rb/counterfactual.py",
            symbol="execute_candidate",
            start=320,
            end=401,
            condition="Restore snapshot, apply matched disturbance stream, run to terminal, evaluate Target V4.",
            result="Each replica returns disposition, label, predicates and terminal cause.",
        ),
        dict(
            stage="Target V4 disposition",
            path="rvt_swarm/phase8e/target.py",
            symbol="evaluate_target_v4",
            start=87,
            end=114,
            condition=(
                "Generation preconditions first; otherwise positive iff goal and all "
                "predicates, else valid negative."
            ),
            result="GENERATION_INVALID remains distinct from VALID_TASK_NEGATIVE.",
        ),
        dict(
            stage="candidate aggregate",
            path="rvt_swarm/phase9g0r/producer.py",
            symbol="_candidate_disposition",
            start=180,
            end=194,
            condition="Any replica generation-invalid invalidates aggregate; otherwise all-success aggregation.",
            result="Raw COMPACT and LINE aggregate dispositions exist before pair reconciliation.",
        ),
        dict(
            stage="candidate-pair reconciliation",
            path="rvt_swarm/phase9g0r/contracts.py",
            symbol="reconcile_candidate_pair",
            start=487,
            end=530,
            condition=(
                "Infra pending; any scientific invalid yields zero rows; otherwise "
                "require N rows per candidate."
            ),
            result="The event publishes exactly 0 or 2*N rows.",
        ),
        dict(
            stage="robot-local row construction",
            path="rvt_swarm/phase9g0r/producer.py",
            symbol="reconcile_recoverability_candidate_results",
            start=363,
            end=509,
            condition="Expand rows only when both raw candidate dispositions are labelable.",
            result="No partial candidate or robot publication is constructed.",
        ),
        dict(
            stage="atomic publication",
            path="rvt_swarm/phase9g0r/writer.py",
            symbol="CanonicalGenerationWriter.write_recoverability_transaction",
            start=57,
            end=127,
            condition="Canonical duplicate check, fsync temporary file, atomic os.replace.",
            result="One complete event transaction is durable or no transaction is replaced.",
        ),
    )
    bindings = [source_binding(root, **definition) for definition in definitions]
    summary_path = root / "results/rvt_fd24/phase9d_r2_recoverability_causal_summary_v1.json"
    matrix_path = root / "results/rvt_fd24/phase9d_r2_recoverability_event_causal_matrix_v1.jsonl"
    summary = json.loads(summary_path.read_text(encoding="ascii"))
    document = {
        "schema_version": "rvt-phase9d-r2-recoverability-execution-binding/v1",
        "phase": "PHASE_9D_R2",
        "audited_commit": AUTHORITATIVE_COMMIT,
        "branch": git(root, "branch", "--show-current"),
        "initial_repository_observation": {
            "head": AUTHORITATIVE_COMMIT,
            "status": "CLEAN",
            "submodules": "NONE",
            "remote_fetch_completed": True,
        },
        "git_status_at_binding": git(root, "status", "--short"),
        "submodule_status": git(root, "submodule", "status"),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "dependencies": dependency_versions(),
        },
        "scientific_dataset_source_commits": {
            split: item["scientific_source_commit"]
            for split, item in summary["provenance"]["datasets"].items()
        },
        "target_read_only_extraction": {
            "host": "100.71.102.9",
            "environment": summary["provenance"]["audit_host"],
            "existing_dataset_root": "/home/avis/rvt-data",
            "qualified_generation_image": (
                "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
            ),
            "namespace_metadata_unchanged": summary["namespace_checkpoints"]["unchanged"],
        },
        "source_bindings": bindings,
        "execution_path": [item["stage"] for item in bindings],
        "event_semantics": {
            "recoverability_event_stages": [f"event-{index}" for index in range(5)],
            "source_policy_classes": [
                "S0_SCRIPTED_DIAGNOSTIC",
                "S1_ALWAYS_COMPACT",
                "S2_ALWAYS_LINE",
                "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR",
                "S4_FROZEN_TRANSITION_PROTOCOL",
                "S5_BOUNDED_PERTURBATION",
            ],
            "distinction": (
                "event-0..event-4 are normalized recoverability sampling stages; "
                "S0..S5 are source-policy classes, not event stages"
            ),
            "runtime_event_predicate": "session.control_step reaches resolved_control_step",
        },
        "terminal_before_capture_hypothesis": {
            "classification": "REFUTED",
            "strict_earlier_terminal_condition": "session.control_step < task.resolved_control_step",
            "same_step_behavior": "snapshot is created",
            "same_step_existing_events_observed": summary["counts"][
                "source_terminal_same_step_snapshots"
            ],
            "same_step_dropped_events": 0,
        },
        "artifact_binding": {
            "event_matrix_file_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
            "causal_summary_file_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            "causal_summary_canonical_sha256": summary[
                "phase9d_r2_recoverability_causal_summary_sha256"
            ],
        },
        "sealed_scope": summary["sealed_scope"],
    }
    result = dict(document)
    result["phase9d_r2_recoverability_execution_binding_sha256"] = sha256_document(document)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(result) + b"\n")
    print(result["phase9d_r2_recoverability_execution_binding_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
