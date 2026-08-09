#!/usr/bin/env python3
"""Validate that every predeclared diagnostic decision state exists."""

from __future__ import annotations

import argparse
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21.rb21_bench import _session_for_unit
from rvt_swarm.phase9c_rb21.rb21_manifest import write_json
from rvt_swarm.phase9c_rb21.rb21_units import ResidualAtomicUnit


def _load_runner(path: Path):
    spec = importlib.util.spec_from_file_location("rb21_target_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load target benchmark runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="ascii"))
    runner = _load_runner(args.runner)
    rows = []
    for case_document in manifest["cases"]:
        case = runner._case(case_document)
        ordered = sorted(case.decision_steps)
        previous = -1
        for original_step in ordered:
            candidates = [original_step]
            candidates.extend(
                step for step in range(original_step - 5, previous, -5)
                if step >= 0)
            observations = []
            for step in candidates:
                candidate_case = replace(case, decision_steps=(step,))
                unit = ResidualAtomicUnit(
                    candidate_case, step, candidate_case.robot_ids[0])
                try:
                    session = _session_for_unit(args.root, unit)
                    observation: Mapping[str, Any] = {
                        "step": step,
                        "reachable": True,
                        "control_step_observed": session.control_step,
                        "termination": None,
                    }
                except RuntimeError as error:
                    observation = {
                        "step": step,
                        "reachable": False,
                        "control_step_observed": None,
                        "termination": str(error),
                    }
                observations.append(observation)
                if observation["reachable"]:
                    break
            selected = next(
                (row["step"] for row in observations if row["reachable"]), None)
            rows.append({
                "case_id": case.case_id,
                "original_step": original_step,
                "selected_reachable_step": selected,
                "selection_rule": "HIGHEST_REACHABLE_FIVE_STEP_BACKOFF_ABOVE_PREVIOUS_STEP",
                "observations": observations,
            })
            previous = original_step

    document = {
        "schema_version": "rvt-rb21-target-manifest-reachability/v1",
        "provenance_class": "OPERATIONAL_MANIFEST_PREFLIGHT_ONLY",
        "source_manifest": manifest["rb21_target_benchmark_manifest_sha256"],
        "counterfactuals_executed": 0,
        "expert_decisions_executed": 0,
        "target_rows_emitted": 0,
        "rows": rows,
        "all_original_steps_reachable": all(
            row["original_step"] == row["selected_reachable_step"] for row in rows),
        "all_steps_have_reachable_replacement": all(
            row["selected_reachable_step"] is not None for row in rows),
        "study_a_n24_accesses": 0,
        "final_test_accesses": 0,
    }
    write_json(
        args.output,
        attach_canonical_hash(document, "rb21_target_manifest_reachability_sha256"),
    )


if __name__ == "__main__":
    main()
