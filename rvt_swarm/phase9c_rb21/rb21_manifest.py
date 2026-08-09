"""Predeclared RB-21 benchmark manifest and target-environment capture."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..phase8.common import attach_canonical_hash
from ..phase9c_rb.counterfactual import replica_count_for_family
from .rb21_units import DiagnosticCase, RecoverabilityAtomicUnit, ResidualAtomicUnit

RB19_PROVENANCE_ROOT = "e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571"
RB20_REPRODUCTION_HASH = "8c55f4ef40be509dc6e0bc678467873e5ebd0ce60d0195a2227555676114b95a"
TARGET_V4_HASH = "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee"
RB20_SOURCE_COMMIT = "297a94b9a7e951b9b30b14befca16a92d9c1189e"

BENCHMARK_SCHEMA_VERSION = "rvt-rb21-benchmark-manifest/v1"
ENVIRONMENT_SCHEMA_VERSION = "rvt-rb21-target-environment-qualification/v1"


def _command(*args: str) -> Optional[str]:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _integer_command(*args: str) -> Optional[int]:
    value = _command(*args)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def capture_environment(root: Path, *, declared_target_id: Optional[str] = None,
                        declared_equivalent_ids: Iterable[str] = ()) -> Dict[str, Any]:
    """Capture the current host without promoting it to an official target."""
    stat = shutil.disk_usage(root)
    temp_root = Path(os.environ.get("TMPDIR", "/tmp"))
    temp = shutil.disk_usage(temp_root)
    physical = (_integer_command("sysctl", "-n", "hw.physicalcpu")
                if platform.system() == "Darwin" else os.cpu_count())
    logical = os.cpu_count()
    memory = (_integer_command("sysctl", "-n", "hw.memsize")
              if platform.system() == "Darwin" else None)
    if memory is None and hasattr(os, "sysconf"):
        try:
            memory = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
        except (ValueError, OSError):
            memory = None
    cpu = (_command("sysctl", "-n", "machdep.cpu.brand_string")
           if platform.system() == "Darwin" else platform.processor())
    try:
        import numpy
        numpy_version = numpy.__version__
    except ImportError:
        numpy_version = None
    try:
        import torch
        torch_version = torch.__version__
        torch_threads = int(torch.get_num_threads())
        torch_interop = int(torch.get_num_interop_threads())
    except ImportError:
        torch_version = None
        torch_threads = None
        torch_interop = None

    host_id = f"{socket.gethostname()}:{platform.system()}:{platform.machine()}"
    declared = declared_target_id or os.environ.get("RVT_OFFICIAL_GENERATION_ENVIRONMENT_ID")
    equivalent = set(declared_equivalent_ids)
    target_match = declared is not None and (declared == host_id or host_id in equivalent)
    document: Dict[str, Any] = {
        "schema_version": ENVIRONMENT_SCHEMA_VERSION,
        "current_environment_id": host_id,
        "declared_official_environment_id": declared,
        "declared_equivalent_environment_ids": sorted(equivalent),
        "environment": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "cpu_model": cpu or "UNKNOWN",
            "physical_cores": physical,
            "logical_cores": logical,
            "ram_bytes": memory,
            "workspace_storage": {
                "path": str(root.resolve()), "total_bytes": stat.total,
                "used_bytes": stat.used, "available_bytes": stat.free,
                "filesystem": _command("df", "-T", str(root)) or "APFS_OR_LOCAL_UNKNOWN",
                "local_vs_network": "LOCAL" if platform.system() == "Darwin" else "UNVERIFIED",
            },
            "temporary_storage": {
                "path": str(temp_root.resolve()), "total_bytes": temp.total,
                "used_bytes": temp.used, "available_bytes": temp.free,
            },
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "torch_version": torch_version,
            "numpy_version": numpy_version,
            "multiprocessing_start_method_default": mp.get_start_method(allow_none=True),
            "multiprocessing_start_methods_available": mp.get_all_start_methods(),
            "scheduler": os.environ.get("SLURM_JOB_ID") and "SLURM" or "NONE_DETECTED",
            "container": "NONE_DETECTED",
            "nested_threads_before_control": {
                "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
                "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
                "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
                "torch_num_threads": torch_threads,
                "torch_num_interop_threads": torch_interop,
            },
        },
        "demonstrably_official_or_equivalent": target_match,
        "qualification_result": ("QUALIFIED" if target_match
                                 else "TARGET_ENVIRONMENT_NOT_QUALIFIED"),
        "final_operational_values_may_be_selected": target_match,
        "reason": ("declared official environment identity matched"
                   if target_match else
                   "no owner-declared official target identity or equivalence proof exists"),
    }
    return attach_canonical_hash(document, "target_environment_qualification_sha256")


def _seeds(offset: int) -> Mapping[str, int]:
    # Diagnostic-only fixed identities, declared before timing and independent of outcomes.
    return {
        "initial_condition": 1100 + offset,
        "communication": 2200 + offset,
        "dynamic_obstacle": 3300 + offset,
        "data_sampling": 4400 + offset,
    }


def _rb18_seeds() -> Mapping[str, int]:
    """The already-qualified RB18 diagnostic stream identities."""
    return {"initial_condition": 11, "communication": 22,
            "dynamic_obstacle": 33, "data_sampling": 7}


def benchmark_cases() -> List[DiagnosticCase]:
    return [
        DiagnosticCase("rb21-f1-n5-train", "train", "train-f1-00", "F1", 5,
                       "S1_ALWAYS_COMPACT", _seeds(1), (20, 60), (0, 4),
                       ("short_or_early_termination", "residual_labeled")),
        DiagnosticCase("rb21-f1-n16-validation", "validation", "validation-f1-00",
                       "F1", 16, "S1_ALWAYS_COMPACT", _seeds(2), (20, 60), (0, 15),
                       ("large_nonsealed_team", "long_continuation")),
        DiagnosticCase("rb21-f5-n8-train", "train", "train-f5-00", "F5", 8,
                       "S1_ALWAYS_COMPACT", _rb18_seeds(), (40, 60), (0, 3),
                       ("changed_topology", "no_eligible_action_naturally_available")),
        DiagnosticCase("rb21-f5-n16-validation", "validation", "validation-f5-00",
                       "F5", 16, "S1_ALWAYS_COMPACT", _seeds(4), (40, 60), (0, 15),
                       ("changed_topology", "large_nonsealed_team")),
        DiagnosticCase("rb21-f8-n5-validation", "validation", "validation-f8-00",
                       "F8", 5, "S1_ALWAYS_COMPACT", _rb18_seeds(), (20, 40), (0, 4),
                       ("communication_degradation", "three_replica_aggregate")),
        DiagnosticCase("rb21-f8-n16-train", "train", "train-f8-00", "F8", 16,
                       "S1_ALWAYS_COMPACT", _seeds(6), (20, 40), (0, 15),
                       ("communication_degradation", "long_continuation")),
        DiagnosticCase("rb21-f9-n12-train", "train", "train-f9-00", "F9", 12,
                       "S0_SCRIPTED_DIAGNOSTIC", _rb18_seeds(), (25, 60), (0, 11),
                       ("dynamic_obstacle", "changed_topology", "three_replica_aggregate")),
        DiagnosticCase("rb21-f9-n16-validation", "validation", "validation-f9-00",
                       "F9", 16, "S0_SCRIPTED_DIAGNOSTIC", _seeds(8), (25, 60),
                       (0, 15), ("dynamic_obstacle", "large_nonsealed_team")),
    ]


def build_benchmark_manifest() -> Dict[str, Any]:
    cases = benchmark_cases()
    residual = [
        ResidualAtomicUnit(case, step, robot).as_dict()
        for case in cases for step in case.decision_steps for robot in case.robot_ids
    ]
    recoverability = [
        RecoverabilityAtomicUnit(
            case, step, topology, tuple(range(replica_count_for_family(case.family))))
        .as_dict()
        for case in cases for step in case.decision_steps for topology in (2, 5)
    ]
    document: Dict[str, Any] = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "provenance_class": "OPERATIONAL_BENCHMARK_ONLY",
        "frozen_before_timing": True,
        "selection_depends_on_measured_speed": False,
        "scientific_roots": {
            "rb19_current_provenance_root": RB19_PROVENANCE_ROOT,
            "rb20_reproduction": RB20_REPRODUCTION_HASH,
            "target_v4": TARGET_V4_HASH,
        },
        "atomic_unit_contract": {
            "residual": "one robot expert decision containing all nine candidates",
            "recoverability": (
                "one decision state x one candidate topology containing all frozen replicas"),
            "scheduler_level_candidate_split": "PROHIBITED",
            "scheduler_level_replica_split": "PROHIBITED",
        },
        "cases": [asdict(case) for case in cases],
        "residual_atomic_units": residual,
        "recoverability_atomic_units": recoverability,
        "sample_counts": {
            "residual_atomic_units": len(residual),
            "residual_candidate_evaluations": len(residual) * 9,
            "recoverability_atomic_units": len(recoverability),
            "recoverability_replica_rollouts": sum(
                len(unit["replica_indices"]) for unit in recoverability),
            "p99_reporting_supported": False,
            "reported_quantiles": ["median", "p90", "p95", "empirical_maximum"],
        },
        "coverage": {
            "splits": sorted({case.split for case in cases}),
            "families": sorted({case.family for case in cases}),
            "team_sizes": sorted({case.team_size for case in cases}),
            "study_a_n24": "SEALED_NOT_INCLUDED",
            "final_test": "SEALED_NOT_INCLUDED",
            "structural_roles": sorted({role for case in cases
                                        for role in case.structural_roles}),
        },
        "diagnostic_host_matrices_predeclared": {
            "worker_counts": [1, 2, 4],
            "residual_chunk_sizes_atomic_units": [1, 2, 4, 8],
            "recoverability_chunk_sizes_atomic_units": [1, 2, 4, 8],
            "production_selection_permitted": False,
        },
        "h4_operational_criteria_predeclared": {
            "H4_OPERATIONALLY_FEASIBLE": (
                "qualified projection <=14 days, >=2.0x storage headroom, >=25% RAM "
                "headroom, and semantic/failure gates pass"),
            "H4_OPERATIONAL_RISK_BUT_FEASIBLE": (
                "qualified projection >14 and <=30 days, or storage headroom 1.25x-2.0x, "
                "with no hard resource or semantic failure"),
            "H4_OPERATIONALLY_INFEASIBLE": (
                "qualified projection >30 days, storage below 1.25x requirement, no safe "
                "worker configuration, or an unresolved operational failure"),
        },
    }
    # Freeze a JSON-native representation so in-memory reconstruction and
    # persisted readback compare exactly (tuples otherwise become lists on disk).
    document = json.loads(json.dumps(document, allow_nan=False, sort_keys=True))
    return attach_canonical_hash(document, "rb21_benchmark_manifest_sha256")


def write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n",
                    encoding="ascii")
