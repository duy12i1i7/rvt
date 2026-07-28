"""Executable consistency assertions for a benchmark run (Step 5).

Every check returns a `CheckResult`; `run_all_checks` aggregates them. The runner
refuses to interpret results unless all checks pass. Each function is unit-tested
against synthetic rows in `tests/test_smoke_consistency.py`, so the checks
themselves are verified independently of any benchmark output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .metrics import EVALUATION_SCHEMA_VERSION
from .splits import TEST, VALIDATION, seed_split


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    n_checked: int = 0

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name} (n={self.n_checked}) {self.detail}".rstrip()


def _fin(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


# 1 ---------------------------------------------------------------------------
def check_schema_version(rows: Sequence[Dict]) -> CheckResult:
    bad = [r for r in rows if int(r.get("evaluation_schema_version", -1)) != EVALUATION_SCHEMA_VERSION]
    return CheckResult(
        "1. every result carries evaluation_schema_version == 2",
        not bad,
        f"{len(bad)} row(s) with a wrong or missing version" if bad else "",
        len(rows),
    )


# 2 ---------------------------------------------------------------------------
def check_matched_episode_signatures(rows: Sequence[Dict]) -> CheckResult:
    """Every method must see byte-identical episodes for each matched cell."""
    by_episode: Dict[tuple, Dict[str, str]] = {}
    for r in rows:
        key = (r["scenario"], int(r["team_size"]), int(r["episode_index"]))
        by_episode.setdefault(key, {})[r["method"]] = r["episode_signature"]
    mismatched = {k: v for k, v in by_episode.items() if len(set(v.values())) > 1}
    return CheckResult(
        "2. episode signatures identical across methods",
        not mismatched,
        f"{len(mismatched)} cell(s) differ, e.g. {list(mismatched)[:2]}" if mismatched else "",
        len(by_episode),
    )


# 3 ---------------------------------------------------------------------------
def check_no_test_episode_in_selection(
    test_seeds: Iterable[int], validation_seeds: Iterable[int]
) -> CheckResult:
    test_seeds = list(test_seeds)
    validation_seeds = list(validation_seeds)
    leaked = [s for s in validation_seeds if seed_split(s) == TEST]
    wrong_ns = [s for s in test_seeds if seed_split(s) != TEST]
    overlap = set(test_seeds) & set(validation_seeds)
    ok = not leaked and not wrong_ns and not overlap
    detail = ""
    if not ok:
        detail = f"leaked={len(leaked)} wrong_namespace={len(wrong_ns)} overlap={len(overlap)}"
    return CheckResult(
        "3. no final-test episode used for validation / selection",
        ok,
        detail,
        len(test_seeds) + len(validation_seeds),
    )


# 4 ---------------------------------------------------------------------------
def check_success_implications(rows: Sequence[Dict]) -> CheckResult:
    bad = [
        r for r in rows
        if float(r["success"]) > float(r["goal_reached"]) + 1e-9
        or float(r["success"]) > float(r["collision_free"]) + 1e-9
    ]
    return CheckResult(
        "4. success <= goal_reached and success <= collision_free",
        not bad,
        f"{len(bad)} violating episode(s)" if bad else "",
        len(rows),
    )


# 5 ---------------------------------------------------------------------------
def check_collision_counts_imply_unsafe(rows: Sequence[Dict]) -> CheckResult:
    bad = [
        r for r in rows
        if (float(r["robot_robot_collision_steps"]) > 0 or float(r["robot_obstacle_collision_steps"]) > 0)
        and float(r["collision_free"]) != 0.0
    ]
    return CheckResult(
        "5. any collision step implies collision_free == 0",
        not bad,
        f"{len(bad)} violating episode(s)" if bad else "",
        len(rows),
    )


# 6 ---------------------------------------------------------------------------
def check_safe_implies_zero_counts(rows: Sequence[Dict]) -> CheckResult:
    bad = [
        r for r in rows
        if float(r["collision_free"]) == 1.0
        and (float(r["robot_robot_collision_steps"]) > 0 or float(r["robot_obstacle_collision_steps"]) > 0)
    ]
    return CheckResult(
        "6. collision_free == 1 implies both collision-step counts are zero",
        not bad,
        f"{len(bad)} violating episode(s)" if bad else "",
        len(rows),
    )


# 7 ---------------------------------------------------------------------------
def check_episode_wide_never_exceeds_terminal(rows: Sequence[Dict]) -> CheckResult:
    """Episode-wide safety is a conjunction that includes the terminal step."""
    bad = [
        r for r in rows
        if float(r["collision_free"]) > float(r["collision_free_terminal"]) + 1e-9
    ]
    return CheckResult(
        "7. episode-wide collision_free <= terminal collision_free",
        not bad,
        f"{len(bad)} violating episode(s)" if bad else "",
        len(rows),
    )


# 8 ---------------------------------------------------------------------------
def check_initial_states(records: Sequence[Dict]) -> CheckResult:
    """`records` carry the validity flags computed at reset time."""
    bad = [
        r for r in records
        if not (
            r["initial_min_rr_clearance"] >= r["min_rr_distance"]
            and r["initial_min_ro_clearance"] >= r["min_ro_distance"]
            and r["initial_in_bounds"]
            and r["initial_formation_valid"]
            and r["initial_obstacles_valid"]
        )
    ]
    return CheckResult(
        "8. all initial states valid (no collision, in bounds, valid geometry)",
        not bad,
        f"{len(bad)} invalid initial state(s)" if bad else "",
        len(records),
    )


# 9 ---------------------------------------------------------------------------
NUMERIC_EXEMPT = {"completion_time", "first_goal_step", "min_rr_clearance", "min_ro_clearance"}


def check_no_nan_or_inf(rows: Sequence[Dict], extra_exempt: Optional[set] = None) -> CheckResult:
    """`completion_time` is legitimately NaN when censored; clearances when N < 2."""
    exempt = NUMERIC_EXEMPT | (extra_exempt or set())
    offenders: List[str] = []
    for r in rows:
        for k, v in r.items():
            if k in exempt or isinstance(v, str) or isinstance(v, bool):
                continue
            if isinstance(v, (int, float)) and not _fin(v):
                offenders.append(f"{r.get('method')}/{r.get('scenario')}/{k}={v}")
    return CheckResult(
        "9. no NaN or infinity in metrics or runtime values",
        not offenders,
        f"{len(offenders)} offender(s), e.g. {offenders[:3]}" if offenders else "",
        len(rows),
    )


# 10 --------------------------------------------------------------------------
def check_timing_excludes_checkpoint_io(rows: Sequence[Dict]) -> CheckResult:
    bad = [r for r in rows if int(r["timed_control_steps"]) != int(r["steps"])]
    return CheckResult(
        "10. runtime measurement covers exactly the control steps",
        not bad,
        f"{len(bad)} episode(s) where timed steps != control steps" if bad else "",
        len(rows),
    )


# 11 --------------------------------------------------------------------------
def check_fresh_checkpoints(checkpoint_meta: Dict[str, Dict]) -> CheckResult:
    bad = []
    for method, meta in checkpoint_meta.items():
        if int(meta.get("evaluation_schema_version", -1)) != EVALUATION_SCHEMA_VERSION:
            bad.append(f"{method}: schema {meta.get('evaluation_schema_version')}")
        elif not meta.get("is_fresh", False):
            bad.append(f"{method}: not trained in this run")
    return CheckResult(
        "11. every learned method uses a fresh schema-2 checkpoint",
        not bad,
        "; ".join(bad),
        len(checkpoint_meta),
    )


# 12 --------------------------------------------------------------------------
def check_equal_budgets(budget_report: Dict[str, Dict], methods: Sequence[str]) -> CheckResult:
    import json

    fields = [
        "epochs", "max_optimizer_steps", "validation_interval_epochs",
        "max_validation_calls", "checkpoints_considered", "early_stopping_patience",
        "checkpoint_selection_rule", "hyperparameter_trials",
        "validation_scenarios", "validation_team_sizes",
    ]
    unequal = []
    for f in fields:
        values = {m: budget_report[m][f] for m in methods if m in budget_report}
        if len({json.dumps(v, sort_keys=True) for v in values.values()}) > 1:
            unequal.append(f"{f}={values}")
    return CheckResult(
        "12. training and model-selection budgets equal across learned methods",
        not unequal,
        "; ".join(unequal),
        len(methods),
    )


# -----------------------------------------------------------------------------
@dataclass
class ConsistencyReport:
    results: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> List[CheckResult]:
        return [r for r in self.results if not r.passed]

    def __str__(self) -> str:
        return "\n".join(str(r) for r in self.results)


def run_all_checks(
    rows: Sequence[Dict],
    initial_records: Sequence[Dict],
    test_seeds: Iterable[int],
    validation_seeds: Iterable[int],
    checkpoint_meta: Dict[str, Dict],
    budget_report: Dict[str, Dict],
    learned_methods: Sequence[str],
) -> ConsistencyReport:
    return ConsistencyReport([
        check_schema_version(rows),
        check_matched_episode_signatures(rows),
        check_no_test_episode_in_selection(test_seeds, validation_seeds),
        check_success_implications(rows),
        check_collision_counts_imply_unsafe(rows),
        check_safe_implies_zero_counts(rows),
        check_episode_wide_never_exceeds_terminal(rows),
        check_initial_states(initial_records),
        check_no_nan_or_inf(rows),
        check_timing_excludes_checkpoint_io(rows),
        check_fresh_checkpoints(checkpoint_meta),
        check_equal_budgets(budget_report, learned_methods),
    ])
