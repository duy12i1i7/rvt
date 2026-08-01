"""Task G8 — reject unexplained decision thresholds in deployable runtime code.

This guard is deliberately NOT a blanket ban on numeric literals. It targets
*semantically unexplained decision thresholds*: a literal compared against a
sensed or derived physical quantity, in code that gates mode selection, event
triggering, communication, safety or formation control.

Allowed: mathematical identities with an explicit role, enum values,
serialization constants whose wire role is documented, values sourced from
typed configuration, and values returned by documented derivations.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import pathlib
import sys

import pytest

from rvt_swarm.decentralized import guards

PKG = pathlib.Path(guards.__file__).parent
TMP = PKG / "_tmp_constant.py"

# Literals whose mathematical / structural role is explicit.
MATH_OK = {0, 1, 2, -1, 0.0, 1.0, 2.0, 0.5, 1e-6, 1e-9, 1e-12}
# Serialization field-width masks, documented in the wire schema tables.
WIRE_OK = {255, 65535, 4294967295, 2147483647, 8, 4, 16, 20, 21, 49, 64}


def _is_arity_check(node: ast.Compare) -> bool:
    """`len(x) == k` is a STRUCTURAL arity check, not a decision threshold.

    `ego_graph` uses `len(entry) == 3` / `== 5` to distinguish a 3-tuple
    obstacle record (dx, dy, radius) from a 5-tuple that also carries relative
    velocity. Flagging those would be crying wolf, and a guard whose output
    must be ignored is worse than no guard.
    """
    for side in [node.left] + list(node.comparators):
        if isinstance(side, ast.Call) and \
                getattr(side.func, "id", None) in ("len", "abs", "int"):
            return True
    return False


def _comparison_literals(tree: ast.AST):
    """Literals appearing on either side of a comparison — decision thresholds."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if _is_arity_check(node):
                continue
            for side in [node.left] + list(node.comparators):
                if isinstance(side, ast.Constant) and \
                        isinstance(side.value, (int, float)) and \
                        not isinstance(side.value, bool):
                    out.append((node.lineno, side.value))
    return out


def deployable_modules():
    off = set(guards.OFFLINE_MODULES) | {"guards", "__init__", "parameters"}
    for p in sorted(PKG.glob("*.py")):
        if p.stem not in off:
            yield p


def unexplained_thresholds():
    bad = []
    for p in deployable_modules():
        tree = ast.parse(p.read_text())
        for lineno, value in _comparison_literals(tree):
            if value in MATH_OK or value in WIRE_OK:
                continue
            bad.append(f"{p.name}:{lineno} threshold {value!r}")
    return bad


# ---------------------------------------------------------------------------
def test_no_unexplained_decision_threshold_remains() -> None:
    bad = unexplained_thresholds()
    assert bad == [], "unexplained decision thresholds:\n  " + "\n  ".join(bad)


def test_the_four_audited_literals_are_gone() -> None:
    """Each was a class-7 finding in the generality audit."""
    from rvt_swarm.decentralized import epoch as E
    from rvt_swarm.decentralized import runtime as rt
    import inspect

    assert not hasattr(E, "FORWARD_SECTOR_HALF_WIDTH")
    assert not hasattr(E, "PEER_SUPPORT_FRACTION")
    assert not hasattr(E, "REARM_OPEN_STEPS")
    assert "2.0 * cfg.env.nominal_spacing" not in inspect.getsource(rt)


def test_derivations_replace_them() -> None:
    from rvt_swarm.decentralized import epoch as E
    from rvt_swarm.decentralized.parameters import (
        default_parameters, derived_forward_sector_half_width,
        derived_k_trigger, derived_lookahead_distance)
    p, m, c = default_parameters()
    assert derived_forward_sector_half_width((0.45, 0.9), (-2.25, 0.0), p, m) > 0
    assert derived_lookahead_distance(p, m, c) > 0
    assert derived_k_trigger(c) == c.max_team_size - 1
    assert callable(E.forward_sector_half_width_for)
    assert callable(E.evidence_persistence_steps)
    assert callable(E.rearm_open_steps)


# ---------------------------------------------------------------------------
# Mutation tests — the guard must catch an injected threshold
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def injected(source: str):
    TMP.write_text("from __future__ import annotations\n" + source)
    try:
        importlib.invalidate_caches()
        yield
    finally:
        TMP.unlink(missing_ok=True)
        importlib.invalidate_caches()
        sys.modules.pop("rvt_swarm.decentralized._tmp_constant", None)


@pytest.mark.parametrize("src,label", [
    ("def gate(clearance):\n    return clearance < 1.37\n", "mode-selection threshold"),
    ("def should_fire(streak):\n    return streak >= 7\n", "persistence threshold"),
    ("def is_safe(margin):\n    return margin > 0.42\n", "safety threshold"),
    ("def in_range(d):\n    return d <= 2.75\n", "communication threshold"),
])
def test_guard_catches_an_injected_threshold(src, label) -> None:
    before = unexplained_thresholds()
    with injected(src):
        after = unexplained_thresholds()
    assert len(after) > len(before), f"guard MISSED an injected {label}"
    assert unexplained_thresholds() == before, "injection not cleaned up"


def test_guard_does_not_ban_legitimate_literals() -> None:
    """Non-vacuity in the other direction: it must not cry wolf."""
    with injected("def half(x):\n    return x / 2\n"
                  "def mask(v):\n    return v & 65535\n"
                  "def nonneg(x):\n    return x >= 0\n"):
        assert unexplained_thresholds() == []
