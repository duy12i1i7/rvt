"""Phase 6 does not activate learning, transitions, labels, or final layouts."""

import inspect

from rvt_swarm.decentralized import (
    forced_topology_runtime,
    guards,
    local_safety_projection,
    robot_local_controller,
)


def test_strict_runtime_guard_has_zero_violation():
    assert guards.audit() == []


def test_controller_stack_has_no_phase5_model_or_training_import():
    source = "\n".join(
        inspect.getsource(module)
        for module in (
            forced_topology_runtime,
            local_safety_projection,
            robot_local_controller,
        )
    )
    forbidden = (
        "rvt_swarm.fd24",
        "RVTFD24",
        "TrainingConfig",
        "recoverability_logit",
        "residual_action",
        "optimizer",
        "DataLoader",
        "final_test",
    )
    assert not [token for token in forbidden if token in source]


def test_forced_runtime_has_no_transition_or_consensus_protocol():
    source = inspect.getsource(forced_topology_runtime)
    forbidden = (
        "transition_intent",
        "readiness",
        "consensus",
        "confirmation",
        "EpochState",
        "choose_topology",
    )
    assert not [token for token in forbidden if token in source]


def test_existing_robot_decision_remains_model_free():
    from rvt_swarm.decentralized import runtime

    source = inspect.getsource(runtime._robot_decision)
    assert "RVTFD24" not in source
    assert "fd24_shadow" not in source
