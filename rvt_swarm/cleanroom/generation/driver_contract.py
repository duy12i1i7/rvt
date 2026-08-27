"""Production-driver completeness contract.

CR-1 attempt 1 was quarantined because the driver ran Stage A only and produced
no Target-V4 label. A production driver that cannot produce the complete frozen
label artifact must never again pass pre-generation qualification.
"""
from __future__ import annotations

import ast


class DriverContractError(ValueError):
    """A production-driver completeness violation that must fail closed."""


# The frozen Stage-B entry point. Without it no (k, R) label exists.
REQUIRED_STAGE_B_CALL = "produce_recoverability_event"
REQUIRED_STAGE_A_CALLS = ("execute_v2_source_acquisition",
                          "compile_recoverability_v2_candidate_tasks")
# Scientific constants that must come from the manifest, never the driver.
FORBIDDEN_LITERALS = ("1200", "[5, 6, 8, 12, 16]", "S0_SCRIPTED_DIAGNOSTIC",
                      "episodes_per_cell = 4", "COMPACT = 5", "LINE = 2")


def assert_production_driver_complete(source: str) -> None:
    """Refuse any driver that cannot produce the complete frozen artifact."""
    tree = ast.parse(source)
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    called |= {n.func.attr for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    for name in REQUIRED_STAGE_A_CALLS:
        if name not in called:
            raise DriverContractError(
                f"driver never calls the frozen Stage-A entry point {name!r}")
    if REQUIRED_STAGE_B_CALL not in called:
        raise DriverContractError(
            f"driver never calls {REQUIRED_STAGE_B_CALL!r}: it is Stage-A only and "
            "would produce no Target-V4 label. A production driver must implement the "
            "complete frozen path from the first episode onward.")
    for literal in FORBIDDEN_LITERALS:
        if literal in source:
            raise DriverContractError(
                f"driver embeds the scientific constant {literal!r}; every scientific "
                "value must be read from the frozen manifest")
