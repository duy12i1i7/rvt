"""Phase 2 deployable/offline configuration isolation."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import rvt_swarm.runtime_configuration as runtime_configuration
from rvt_swarm.configuration import ExperimentConfiguration
from rvt_swarm.configuration_serialization import canonical_runtime_source
from rvt_swarm.decentralized import guards


def deployable_module_paths():
    package = Path(guards.__file__).parent
    for path in sorted(package.glob("*.py")):
        if path.stem in guards.OFFLINE_MODULES or path.stem in {"guards", "__init__"}:
            continue
        yield path


def test_runtime_configuration_module_defines_no_training_or_evaluation_type() -> None:
    source = inspect.getsource(runtime_configuration)
    assert "class TrainingConfig" not in source
    assert "class EvaluationConfig" not in source


def test_deployable_modules_do_not_import_offline_config_types() -> None:
    offenders = []
    for path in deployable_module_paths():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            names = [alias.name for alias in node.names]
            if "TrainingConfig" in names or "EvaluationConfig" in names:
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


def test_robot_local_modules_do_not_import_legacy_broad_config() -> None:
    robot_local = {
        "comms.py",
        "consensus.py",
        "ego_graph.py",
        "epoch.py",
        "local_controller.py",
        "models.py",
        "runtime.py",
    }
    offenders = []
    for path in deployable_module_paths():
        if path.name not in robot_local:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = {alias.name for alias in node.names}
                if node.module and node.module.endswith("config") and "Config" in names:
                    offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


def test_serialized_runtime_source_contains_no_offline_sections() -> None:
    source = canonical_runtime_source(ExperimentConfiguration().runtime)
    assert "training" not in source
    assert "evaluation" not in source
    assert "final_test_seed" not in repr(source)


def test_offline_wrapper_cannot_mutate_runtime_nested_state() -> None:
    wrapper = ExperimentConfiguration()
    with pytest.raises(FrozenInstanceError):
        wrapper.runtime.communication.communication_range_meters = 9.0  # type: ignore[misc]


def test_strict_decentralization_guard_remains_clean() -> None:
    assert guards.audit() == []

