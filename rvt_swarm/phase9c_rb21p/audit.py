"""Read-only RB21P diagnostics for model numerics, layouts, and RB20 replay."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import runpy
import struct
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

import torch

from ..decentralized.ego_graph_v2 import build_robot_local_ego_graph
from ..fd24.model import prepare_fd24_model_batch
from ..phase8.common import canonical_json_bytes, verify_canonical_hash
from ..phase8.splits import load_nonfinal_split_manifest
from ..phase8e.compiler import compile_nonfinal_split, mission_axes
from ..phase8e.protocol import build_executable_protocol
from ..phase9c_rb.binding import canonical_sha256, load_execution_specification
from ..phase9c_rb.counterfactual import execute_candidate, replica_count_for_family, snapshot
from ..phase9c_rb.generation_contract import candidate_evaluation_id
from ..phase9c_rb.residual_expert_v2 import (
    canonical_result_digest,
    evaluate_residual_expert_v2,
)
from ..phase9c_rb21.rb21_bench import _session_for_unit
from ..phase9c_rb21.rb21_units import DiagnosticCase, ResidualAtomicUnit
from ..topology_registry import COMPACT, KEEP, LINE


def _tensor_payload(tensor: torch.Tensor) -> Dict[str, Any]:
    value = tensor.detach().cpu().contiguous()
    raw = value.numpy().tobytes()
    return {
        "dtype": str(value.dtype),
        "shape": list(value.shape),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "values": value.tolist(),
    }


def _state_dict_report(model: torch.nn.Module) -> Dict[str, Any]:
    entries = {}
    digest = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        payload = _tensor_payload(tensor)
        entries[name] = {
            key: payload[key] for key in ("dtype", "shape", "sha256")
        }
        digest.update(name.encode("ascii"))
        digest.update(payload["sha256"].encode("ascii"))
    return {
        "parameter_count": sum(item.numel() for item in model.parameters()),
        "state_dict_keys": list(model.state_dict()),
        "state_dict_sha256": digest.hexdigest(),
        "entries": entries,
    }


def _float32(value: torch.Tensor) -> Dict[str, Any]:
    number = float(value.detach().cpu().reshape(-1)[0])
    bits = struct.unpack(">I", struct.pack(">f", number))[0]
    return {"value": number, "bits_hex": f"0x{bits:08x}"}


def _fixture_factories(root: Path):
    namespace = runpy.run_path(str(root / "tests/conftest.py"))
    return (
        namespace["ego_v2_factory"].__wrapped__(),
        namespace["fd24_graph_factory"].__wrapped__(
            namespace["ego_v2_factory"].__wrapped__()
        ),
        namespace["fd24_model_factory"].__wrapped__(),
    )


def _target_indices(local_batch, fingerprint: str):
    batch = local_batch.graph_batch
    graph_index = local_batch.graph_fingerprint_by_graph.index(fingerprint)
    nodes = batch.graph_index == graph_index
    edges = (
        batch.graph_index[batch.edge_index[0]] == graph_index
        if batch.edge_index.shape[1]
        else torch.zeros(0, dtype=torch.bool)
    )
    return graph_index, nodes, edges


def _capture_fd24_stages(model, local_batch, fingerprint: str):
    graph_index, node_mask, edge_mask = _target_indices(local_batch, fingerprint)
    captures: Dict[str, torch.Tensor] = {}
    handles = []

    def register(name, module, scope):
        def hook(_module, _inputs, output):
            if not isinstance(output, torch.Tensor):
                return
            if scope == "node":
                selected = output[node_mask]
            elif scope == "edge":
                selected = output[edge_mask]
            elif scope == "graph":
                selected = output[graph_index:graph_index + 1]
            else:
                selected = output
            captures[name] = selected.detach().cpu().clone()

        handles.append(module.register_forward_hook(hook))

    for index, projection in enumerate(model.encoder.node_type_projections):
        register(f"encoder.node_projection.{index}.linear", projection[0], "node")
    for index, projection in enumerate(model.encoder.edge_type_projections):
        register(f"encoder.edge_projection.{index}.linear", projection[0], "edge")
    for index, block in enumerate(model.encoder.message_blocks):
        register(f"encoder.message.{index}.linear0", block.message[0], "edge")
        register(f"encoder.message.{index}.linear1", block.message[2], "edge")
        register(f"encoder.message.{index}.attention", block.attention, "edge")
        register(f"encoder.message.{index}.update0", block.update[0], "node")
        register(f"encoder.message.{index}.update1", block.update[3], "node")
        register(f"encoder.message.{index}.layer_norm", block.normalization, "node")
    register("encoder.root_readout", model.encoder, "graph")
    register(
        "candidate.local_metadata.linear",
        model.candidate_conditioner.local_metadata_projection[0],
        "graph",
    )
    register("candidate.fusion.linear0", model.candidate_conditioner.fusion[0], "graph")
    register("candidate.fusion.linear1", model.candidate_conditioner.fusion[3], "graph")
    register("candidate.fusion.layer_norm", model.candidate_conditioner.fusion[4], "graph")
    register("candidate.conditioned", model.candidate_conditioner, "graph")
    register("recoverability.linear0", model.recoverability_head.network[0], "graph")
    register("recoverability.linear1", model.recoverability_head.network[2], "graph")
    register("residual.linear0", model.residual_action_head.network[0], "graph")
    register("residual.linear1", model.residual_action_head.network[2], "graph")
    model.eval()
    with torch.no_grad():
        output = model(local_batch)
    for handle in handles:
        handle.remove()
    captures["output.recoverability_logit"] = output.recoverability_logit[
        graph_index:graph_index + 1
    ].detach().cpu()
    captures["output.residual_action"] = output.residual_action[
        graph_index:graph_index + 1
    ].detach().cpu()
    return captures, output, graph_index


def _compare_stage_maps(single, batched):
    report = []
    for name in single:
        left = single[name]
        right = batched[name]
        if left.shape != right.shape:
            report.append({"stage": name, "shape_mismatch": [list(left.shape), list(right.shape)]})
            continue
        difference = (left - right).abs()
        maximum = float(difference.max()) if difference.numel() else 0.0
        first = None
        if maximum:
            flat_index = int(torch.argmax(difference).item())
            index = []
            remainder = flat_index
            for size in reversed(left.shape):
                index.append(remainder % size)
                remainder //= size
            index.reverse()
            key = tuple(index)
            first = {
                "index": index,
                "single": float(left[key]),
                "batched": float(right[key]),
            }
        report.append({
            "stage": name,
            "exact": torch.equal(left, right),
            "max_abs_difference": maximum,
            "first_max_difference": first,
        })
    return report


def _numeric_case(model, single_graph, mixed_graphs):
    fingerprint = single_graph.fingerprint()
    single_batch = prepare_fd24_model_batch((single_graph,))
    mixed_batch = prepare_fd24_model_batch(mixed_graphs)
    single, single_output, single_index = _capture_fd24_stages(
        model, single_batch, fingerprint
    )
    mixed, mixed_output, mixed_index = _capture_fd24_stages(
        model, mixed_batch, fingerprint
    )
    stages = _compare_stage_maps(single, mixed)
    first = next((item for item in stages if not item.get("exact", False)), None)
    return {
        "graph_fingerprint": fingerprint,
        "single_batch_dimensions": {
            "graphs": single_batch.n_graphs,
            "nodes": int(single_batch.graph_batch.node_x.shape[0]),
            "edges": int(single_batch.graph_batch.edge_index.shape[1]),
        },
        "mixed_batch_dimensions": {
            "graphs": mixed_batch.n_graphs,
            "nodes": int(mixed_batch.graph_batch.node_x.shape[0]),
            "edges": int(mixed_batch.graph_batch.edge_index.shape[1]),
        },
        "input_tensors": {
            "node_x": _tensor_payload(single_batch.graph_batch.node_x),
            "edge_index": _tensor_payload(single_batch.graph_batch.edge_index),
            "edge_attr": _tensor_payload(single_batch.graph_batch.edge_attr),
            "node_kind": _tensor_payload(single_batch.graph_batch.node_kind),
            "edge_type": _tensor_payload(single_batch.graph_batch.edge_type),
            "candidate_topology_id": _tensor_payload(
                single_batch.graph_batch.candidate_topology_id
            ),
            "mission_orientation_cos_sin": _tensor_payload(
                single_batch.mission_orientation_cos_sin
            ),
        },
        "single_output": {
            "recoverability_logit": _float32(
                single_output.recoverability_logit[single_index]
            ),
            "residual_action": [
                _float32(value)
                for value in single_output.residual_action[single_index]
            ],
        },
        "batched_output": {
            "recoverability_logit": _float32(
                mixed_output.recoverability_logit[mixed_index]
            ),
            "residual_action": [
                _float32(value)
                for value in mixed_output.residual_action[mixed_index]
            ],
        },
        "first_divergent_stage": first,
        "stage_comparison": stages,
    }


def audit_fd24_batch_numerics(root: Path) -> Dict[str, Any]:
    ego_factory, graph_factory, model_factory = _fixture_factories(root)
    target_case, target = graph_factory(
        n=6,
        root=0,
        candidate_topology=LINE,
        peer_ids=(1, 2),
        obstacles=((1.0, 0.2, 0.1),),
    )
    _, other_n5 = graph_factory(n=5, root=3, candidate_topology=KEEP, peer_ids=())
    _, other_n24 = graph_factory(
        n=24,
        root=12,
        candidate_topology=COMPACT,
        peer_ids=(1, 2, 3, 4),
        obstacles=((1.1, 0.0, 0.2), (1.5, -0.2, 0.1)),
        observation_step=19,
    )
    model = model_factory(target_case.config)
    unrelated = _numeric_case(model, target, (other_n24, target, other_n5))

    case = ego_factory()
    candidates = tuple(
        build_robot_local_ego_graph(
            case.view,
            case.config,
            case.local_topology,
            candidate,
            case.observation_step,
        )
        for candidate in (KEEP, COMPACT, LINE)
    )
    candidate_model = model_factory(case.config)
    candidate_cases = [
        _numeric_case(candidate_model, graph, candidates) for graph in candidates
    ]
    return {
        "schema_version": "rvt-rb21p-fd24-numeric-localization/v1",
        "torch_version": torch.__version__,
        "mkldnn_enabled": torch.backends.mkldnn.enabled,
        "parameter_provenance": _state_dict_report(model),
        "unrelated_batch_case": unrelated,
        "parallel_candidate_cases": candidate_cases,
    }


def _physical_projection(document: Mapping[str, Any]) -> Dict[str, Any]:
    projection = copy.deepcopy(document)
    projection.pop("layout_execution_specification_sha256", None)
    projection["mission_frame"].pop("heading_radians", None)
    return projection


def _ulp_distance(left: float, right: float) -> int:
    a = struct.unpack(">Q", struct.pack(">d", left))[0]
    b = struct.unpack(">Q", struct.pack(">d", right))[0]
    return abs(a - b)


def _value_differences(reference: Any, observed: Any, path: str = ""):
    differences = []
    if isinstance(reference, Mapping) and isinstance(observed, Mapping):
        keys = sorted(set(reference) | set(observed))
        for key in keys:
            child = f"{path}.{key}" if path else str(key)
            if key not in reference or key not in observed:
                differences.append({
                    "path": child,
                    "reference": reference.get(key, "MISSING"),
                    "observed": observed.get(key, "MISSING"),
                })
            else:
                differences.extend(
                    _value_differences(reference[key], observed[key], child)
                )
        return differences
    if (
        isinstance(reference, Sequence)
        and not isinstance(reference, (str, bytes))
        and isinstance(observed, Sequence)
        and not isinstance(observed, (str, bytes))
    ):
        if len(reference) != len(observed):
            return [{
                "path": path,
                "reference_length": len(reference),
                "observed_length": len(observed),
            }]
        for index, (left, right) in enumerate(zip(reference, observed)):
            differences.extend(_value_differences(left, right, f"{path}[{index}]"))
        return differences
    if reference != observed:
        item = {"path": path, "reference": reference, "observed": observed}
        if isinstance(reference, float) and isinstance(observed, float):
            item.update({
                "reference_hex": reference.hex(),
                "observed_hex": observed.hex(),
                "ulp_distance": _ulp_distance(reference, observed),
            })
        differences.append(item)
    return differences


def audit_authoritative_layouts(root: Path) -> Dict[str, Any]:
    protocol = build_executable_protocol(root)
    rows = []
    for split in ("train", "validation"):
        compiled = {
            item["source_layout"]["layout_id"]: item
            for item in compile_nonfinal_split(root, split, protocol)
        }
        manifest = load_nonfinal_split_manifest(
            root / f"results/rvt_fd24/splits/{split}_layouts.json"
        )
        for source in sorted(manifest["layout_records"], key=lambda item: item["layout_id"]):
            layout_id = source["layout_id"]
            persisted = load_execution_specification(
                root / "results/rvt_fd24", split, layout_id
            )
            fresh = compiled[layout_id]
            reference = float(persisted["mission_frame"]["heading_radians"])
            observed = float(fresh["mission_frame"]["heading_radians"])
            physical_differences = _value_differences(
                _physical_projection(persisted), _physical_projection(fresh)
            )
            rows.append({
                "split": split,
                "layout_id": layout_id,
                "source_geometry_sha256": source["geometry_sha256"],
                "authoritative_layout_sha256": persisted[
                    "layout_execution_specification_sha256"
                ],
                "authoritative_self_hash_valid": verify_canonical_hash(
                    persisted, "layout_execution_specification_sha256"
                ),
                "fresh_compiler_sha256": fresh[
                    "layout_execution_specification_sha256"
                ],
                "exact_document_match": persisted == fresh,
                "physical_projection_exact": (
                    not physical_differences
                ),
                "physical_projection_differences": physical_differences,
                "heading_reference": reference,
                "heading_observed": observed,
                "heading_reference_hex": reference.hex(),
                "heading_observed_hex": observed.hex(),
                "heading_ulp_distance": _ulp_distance(reference, observed),
            })
    return {
        "schema_version": "rvt-rb21p-layout-portability-audit/v1",
        "authority": {
            "physical_source": "frozen source geometric primitives",
            "runtime_identity": "committed compiled execution specification",
            "heading_runtime_consumers": 0,
            "mechanism": "load and verify canonical committed compiled artifact",
        },
        "total_layouts": len(rows),
        "resolved_authoritative_hash_exact_matches": sum(
            item["authoritative_self_hash_valid"] for item in rows
        ),
        "fresh_compiler_exact_matches": sum(item["exact_document_match"] for item in rows),
        "physical_projection_exact_matches": sum(
            item["physical_projection_exact"] for item in rows
        ),
        "heading_ulp_differences": [
            item for item in rows if item["heading_ulp_distance"]
        ],
        "layouts": rows,
    }


_RB20_SEEDS = {
    "initial_condition": 11,
    "communication": 22,
    "dynamic_obstacle": 33,
    "data_sampling": 7,
}


def _diagnostic_case(record: Mapping[str, Any]) -> DiagnosticCase:
    source_policy = str(record["policy"])
    return DiagnosticCase(
        str(record["case_id"]),
        str(record["split"]),
        str(record["layout_id"]),
        str(record["family"]),
        int(record["team_size"]),
        source_policy,
        _RB20_SEEDS,
        tuple(int(value) for value in record["decision_steps"]),
        tuple(int(value) for value in record["robots"]),
        ("rb20_semantic_replay",),
    )


def _candidate_sidecar(result, scientific_row_id: str):
    matched = canonical_sha256([
        list(value) for value in result.candidates[0].trace.matched_stream_identity
    ])
    records = []
    for candidate in result.candidates:
        identity = candidate_evaluation_id({
            "residual_scientific_row_id": scientific_row_id,
            "candidate_index": candidate.candidate_index,
            "replica_index": 0,
            "matched_stream_identity_sha256": matched,
        })
        records.append({
            "candidate_evaluation_id": identity,
            "control_intervals": candidate.trace.control_intervals,
            "delta_u_world": list(candidate.delta_u_world),
            "locally_feasible": candidate.locally_feasible,
            "robot_local_information_only": candidate.robot_local_information_only,
            "safety_projection_compatible": candidate.safety_projection_compatible,
            "termination": candidate.trace.termination_cause,
            "utilities": dict(candidate.utilities),
        })
    return matched, records


def audit_rb20_semantic_replay(root: Path) -> Dict[str, Any]:
    rb18 = json.loads((
        root / "results/rvt_fd24/rb18_structural_generation_canary_v1.json"
    ).read_text(encoding="ascii"))
    rb20 = json.loads((
        root / "results/rvt_fd24/rb20_clean_detached_reproduction_v1.json"
    ).read_text(encoding="ascii"))
    expected_residual = {item["case_id"]: item for item in rb18["residual"]}
    expected_recoverability = {
        item["case_id"]: item for item in rb18["recoverability"]
    }
    source_results = []
    residual_results = []
    recoverability_results = []
    identity_mismatches = []

    for record in rb20["rb18_case_manifest"]["cases"]:
        case = _diagnostic_case(record)
        decision_step = case.decision_steps[0]
        robot_id = case.robot_ids[0]
        unit = ResidualAtomicUnit(case, decision_step, robot_id)
        session = _session_for_unit(root, unit)
        source = snapshot(session)
        expected = expected_residual[case.case_id]
        source_exact = (
            session.control_step == decision_step
            and source.canonical_hash == expected["snapshot_sha256"]
        )
        source_results.append({
            "case_id": case.case_id,
            "control_step": session.control_step,
            "termination": None if session.termination is None else asdict(session.termination),
            "snapshot_sha256": source.canonical_hash,
            "expected_snapshot_sha256": expected["snapshot_sha256"],
            "exact": source_exact,
        })

        robot = next(item for item in session.robots if item.robot_id == robot_id)
        view, _, _ = session.local_decision_inputs(robot)
        graph = build_robot_local_ego_graph(
            view,
            session.runtime_config,
            robot.local_topology_metadata,
            robot.committed_topology,
            session.control_step,
        )
        result = evaluate_residual_expert_v2(session, robot_id)
        matched, sidecar = _candidate_sidecar(result, expected["scientific_row_id"])
        target = (
            None
            if result.target is None
            else list(result.target.residual_target_world_acceleration)
        )
        checks = {
            "snapshot": result.snapshot_hash == expected["snapshot_sha256"],
            "robot_view": result.robot_view_hash == expected["robot_view_sha256"],
            "graph_fingerprint": graph.fingerprint() == expected["graph_fingerprint"],
            "result_digest": canonical_result_digest(result) == expected["result_digest"],
            "disposition": ("LABELED" if result.target is not None else "NO_ELIGIBLE_ACTION")
            == expected["disposition"],
            "selected_candidate": result.selected_index == expected["selected_candidate_index"],
            "target_world": target == expected["residual_target_world_acceleration"],
            "selector_error": result.selector_error == expected["selector_error"],
            "matched_stream_identity": matched
            == expected["matched_stream_identity_sha256"],
            "candidate_ids": [item["candidate_evaluation_id"] for item in sidecar]
            == expected["candidate_evaluation_ids"],
            "candidate_records": sidecar == expected["candidate_sidecar"],
        }
        residual_results.append({
            "case_id": case.case_id,
            "checks": checks,
            "exact": all(checks.values()),
            "candidate_evaluations": len(sidecar),
        })
        for name, passed in checks.items():
            if name in {"snapshot", "robot_view", "graph_fingerprint", "candidate_ids"} and not passed:
                identity_mismatches.append({"case_id": case.case_id, "identity": name})

        if case.case_id in expected_recoverability:
            expected_branch = expected_recoverability[case.case_id]
            records = []
            aggregate = {}
            for topology in (LINE, COMPACT):
                replicas = []
                for replica_index in range(replica_count_for_family(case.family)):
                    outcome = execute_candidate(
                        source, topology, replica_index=replica_index
                    )
                    replicas.append({
                        "candidate_topology": topology,
                        "control_steps": outcome.control_steps,
                        "created_lifecycle": outcome.created_lifecycle,
                        "failed_predicates": list(outcome.failed_predicates),
                        "final_state_sha256": outcome.final_state_hash,
                        "label": outcome.label,
                        "replica_index": replica_index,
                        "safety_infeasible_robots": outcome.safety_infeasible_robots,
                        "safety_solver_failure_robots": outcome.safety_solver_failure_robots,
                        "snapshot_sha256": source.canonical_hash,
                        "target_v4_disposition": outcome.disposition,
                        "termination_cause": outcome.termination_cause,
                    })
                records.extend(replicas)
                aggregate[str(topology)] = (
                    None
                    if any(item["target_v4_disposition"] == "GENERATION_INVALID" for item in replicas)
                    else int(all(item["label"] == 1 for item in replicas))
                )
            branch = {
                "aggregate_labels": aggregate,
                "candidate_rollouts": len(records),
                "case_id": case.case_id,
                "changed_topology_lifecycle_created": any(
                    item["created_lifecycle"] for item in records
                ),
                "decision_snapshot_sha256": source.canonical_hash,
                "family": case.family,
                "replica_records": records,
                "replicas_per_candidate": replica_count_for_family(case.family),
                "team_size": case.team_size,
                "topology_candidates": [LINE, COMPACT],
            }
            recoverability_results.append({
                "case_id": case.case_id,
                "exact": branch == expected_branch,
                "candidate_rollouts": len(records),
                "aggregate_labels": aggregate,
            })

    mismatches = (
        [item["case_id"] for item in source_results if not item["exact"]]
        + [item["case_id"] for item in residual_results if not item["exact"]]
        + [item["case_id"] for item in recoverability_results if not item["exact"]]
    )
    return {
        "schema_version": "rvt-rb21p-rb20-semantic-replay/v1",
        "rb20_authority_sha256": rb20[
            "rb20_clean_detached_reproduction_sha256"
        ],
        "source_episodes": source_results,
        "recoverability": recoverability_results,
        "residual": residual_results,
        "counts": {
            "source_episodes": len(source_results),
            "recoverability_rollouts": sum(
                item["candidate_rollouts"] for item in recoverability_results
            ),
            "residual_candidate_evaluations": sum(
                item["candidate_evaluations"] for item in residual_results
            ),
            "semantic_mismatches": len(mismatches),
            "scientific_identity_mismatches": len(identity_mismatches),
        },
        "mismatches": mismatches,
        "identity_mismatches": identity_mismatches,
        "study_a_n24_access_count": 0,
        "final_test_access_count": 0,
        "official_rows": 0,
    }
