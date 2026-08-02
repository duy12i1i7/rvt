"""Static and mutation guards reject joint safety optimization."""

import importlib
import inspect
import sys
from contextlib import contextmanager
from pathlib import Path

from rvt_swarm.decentralized import guards
from rvt_swarm.decentralized.local_safety_projection import RobotLocalSafetyProjection


@contextmanager
def injected_module(source):
    package = Path(guards.__file__).parent
    path = package / "_tmp_joint_safety.py"
    module_name = "rvt_swarm.decentralized._tmp_joint_safety"
    path.write_text(source, encoding="utf-8")
    importlib.invalidate_caches()
    try:
        yield importlib.import_module(module_name)
    finally:
        sys.modules.pop(module_name, None)
        path.unlink(missing_ok=True)
        importlib.invalidate_caches()


def test_projection_interface_has_one_action_decision_variable():
    signature = inspect.signature(RobotLocalSafetyProjection.project)
    assert tuple(signature.parameters) == ("self", "proposed_action", "controller_input")
    source = inspect.getsource(RobotLocalSafetyProjection)
    assert "joint_state" not in source
    assert "all_robot" not in source
    assert "cvxpy" not in source


def test_guard_detects_injected_joint_safety_optimizer():
    with injected_module(
        "def joint_safety_optimizer(joint_state):\n"
        "    return joint_state\n"
    ):
        violations = guards.audit()
    assert any(item.kind == "joint-action-output" for item in violations)


def test_clean_namespace_has_no_joint_optimizer_violation():
    assert not [
        item for item in guards.audit()
        if item.kind == "joint-action-output"
    ]
