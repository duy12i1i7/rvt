import ast
import subprocess
from pathlib import Path

from rvt_swarm.decentralized.transition_messages import (
    TRANSITION_PROTOCOL_SCHEMA_VERSION,
)
from rvt_swarm.decentralized.transition_protocol import (
    TransitionProtocolRuntimeOptions,
)


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "5f23666d872aa45258ffef78f0651b45c000fc2d"
PHASE7_MODULES = (
    ROOT / "rvt_swarm/decentralized/transition_messages.py",
    ROOT / "rvt_swarm/decentralized/transition_admissibility.py",
    ROOT / "rvt_swarm/decentralized/transition_readiness.py",
    ROOT / "rvt_swarm/decentralized/transition_protocol.py",
    ROOT / "rvt_swarm/decentralized/transition_runtime.py",
    ROOT / "rvt_swarm/decentralized/phase7_qualification.py",
)


# RB16R (owner-authorized, phase PHASE 5R / RB16R): the residual model output
# frame was repaired from the historical mission-named declaration to WORLD.
# The declaration, its supersession and the evidence live in
# results/rvt_fd24/model_residual_output_frame_v2.json. The guard keeps its
# force: every OTHER frozen mechanical file must still be untouched.
RB16R_AUTHORIZED_FILES = {
    "rvt_swarm/decentralized/ego_graph_v2.py",
    "rvt_swarm/fd24/model.py",
    "rvt_swarm/fd24/configuration.py",
    "rvt_swarm/decentralized/guards.py",
}


def test_frozen_phase6_implementation_files_are_unchanged():
    frozen = (
        "rvt_swarm/topology_registry.py",
        "rvt_swarm/runtime_configuration.py",
        "rvt_swarm/decentralized/ego_graph_v2.py",
        "rvt_swarm/decentralized/robot_local_controller.py",
        "rvt_swarm/decentralized/local_safety_projection.py",
        "rvt_swarm/decentralized/formation_metric_v3.py",
        "rvt_swarm/decentralized/local_control_types.py",
        "rvt_swarm/decentralized/forced_topology_runtime.py",
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE, "--", *frozen],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert set(filter(None, changed.splitlines())) <= RB16R_AUTHORIZED_FILES


def test_phase7_runtime_imports_no_training_or_learned_model_module():
    forbidden = {"training", "models", "fd24_shadow_adapter"}
    for path in PHASE7_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
        assert imported.isdisjoint(forbidden), (path, imported & forbidden)


def test_protocol_default_and_schema_are_frozen():
    assert not TransitionProtocolRuntimeOptions().transition_protocol_v1_enabled
    assert TRANSITION_PROTOCOL_SCHEMA_VERSION == "rvt-transition-protocol/v1"


def test_no_final_test_layout_or_scientific_training_entry_point_is_called():
    source = "\n".join(path.read_text(encoding="utf-8") for path in PHASE7_MODULES)
    assert "generate_binary_labels(" not in source
    assert "train_decentralized_selector(" not in source
    assert "results/final_test" not in source
    assert "final-test" not in source
    assert "residual_action_head(" not in source
