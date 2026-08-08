"""DETACHED-6 -- the switching epoch count must never be the S2 mechanical counter.

The measurement defect corrected in v6: `mechanical_transition_epoch_count`
increments in exactly one place, S2's forced LINE initialization, so it is
structurally zero for the S0 switching diagnostic. Reporting it as the
switching epoch count silently turns every completed during-task
reconfiguration into "zero epochs". The authoritative field is
`completion_agreements` -- distributed lifecycle completions actually reached.
"""

from __future__ import annotations

import ast
import collections
import inspect
import json
import pathlib

from rvt_swarm.phase8e.target import evaluate_target_v4
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb import session as session_module
from rvt_swarm.phase9c_rb.binding import build_binding, load_execution_specification
from rvt_swarm.phase9c_rb.counterfactual import build_execution_summary
from rvt_swarm.phase9c_rb.session import SimulatorEpisodeSession, build_event_plan
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG

ROOT = pathlib.Path("results/rvt_fd24")
V6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
SEEDS = {"initial_condition": 11, "communication": 22, "dynamic_obstacle": 33}


def _increment_sites(module) -> list[str]:
    """Qualified names of every function that increments the mechanical counter."""
    source = inspect.getsource(module)
    tree = ast.parse(source)
    sites: list[str] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            target = node.target
            if (isinstance(target, ast.Attribute)
                    and target.attr == "mechanical_transition_epoch_count"):
                sites.append(".".join(self.stack))
            self.generic_visit(node)

    Visitor().visit(tree)
    return sites


def test_mechanical_counter_increments_only_in_the_s2_forced_initialization() -> None:
    assert _increment_sites(P) == ["FixedTopologyPolicy.observe"]
    assert _increment_sites(session_module) == []


def _execute(split: str, layout_id: str, team_size: int, policy_id: str):
    protocol = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
    target = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
    contracts = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())
    binding = build_binding(
        load_execution_specification(ROOT, split, layout_id),
        team_size=team_size, source_policy=policy_id, protocol=protocol,
        target_contract=target, source_policy_contracts=contracts,
    )
    plan = build_event_plan(binding, contracts) if policy_id == P.S0 else ()
    policy = P.build_source_policy(
        policy_id, contracts=contracts, seed=7, horizon_seconds=binding.horizon_seconds,
        team_size=team_size, family_id=binding.family,
        runtime_config=DEFAULT_RUNTIME_CONFIG, event_plan=plan,
    )
    session = SimulatorEpisodeSession(binding, protocol=protocol, target_contract=target,
                                      seeds=SEEDS, source_policy=policy)
    for _ in range(1600):
        session.step()
        if session.termination is not None:
            break
    resolved = evaluate_target_v4(
        build_execution_summary(session, session.robots[0].committed_topology))
    return session, resolved


def test_two_completed_switching_epochs_report_zero_on_the_mechanical_counter() -> None:
    """The defect, reproduced live on a cell that genuinely switches twice."""
    session, resolved = _execute("train", "train-f9-00", 8, P.S0)
    assert resolved.disposition == "RECOVERABLE_POSITIVE"
    assert len(session.completion_agreements) == 2      # COMPACT -> LINE -> COMPACT
    assert session.mechanical_transition_epoch_count == 0
    assert session.topology_selection_epoch_count == 2


def test_v6_switching_epoch_distribution_uses_completion_agreements() -> None:
    successes = [cell["switching"] for cell in V6["cells"]
                 if cell["switching"] and cell["switching"]["task_success"]]
    assert successes

    from_agreements = collections.Counter(r["completion_agreements"] for r in successes)
    from_mechanical = collections.Counter(r["mechanical_transition_epoch_count"]
                                          for r in successes)
    reported = {int(k): v for k, v in
                V6["switching_epoch_distribution_all_successes"].items()}

    assert dict(from_agreements) == reported
    # The defective field is degenerate: every switching execution reads zero.
    assert dict(from_mechanical) == {0: len(successes)}
    assert dict(from_mechanical) != reported


def test_v6_records_the_measurement_correction_explicitly() -> None:
    correction = V6["measurement_correction"]
    assert correction["field"] == "switching epoch count"
    assert "completion_agreements" in correction["authoritative_field"]
    assert "mechanical_transition_epoch_count" in correction["defect"]


def test_no_reconfiguration_cell_is_attributed_from_the_mechanical_counter() -> None:
    """Attribution must key off completed distributed epochs, not the S2 field."""
    for cell in V6["cells"]:
        if cell["category"] != "RECONFIGURATION_REQUIRED":
            continue
        switching = cell["switching"]
        assert switching["mechanical_transition_epoch_count"] == 0
        completed = switching["completion_agreements"]
        if cell.get("attribution") in ("MIXED", "LATER_TASK_DRIVEN"):
            assert completed >= 1, cell["layout_id"]
