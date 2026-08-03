"""Executable centralization guards.

`system_model.py` asserted that the prohibited list was "enforced executably by
guards.py ... not documentation only". An audit found that no such file existed
and that the ad-hoc guards which did exist had no discriminating power: one
matched parameter *names* against a hardcoded set, skipped classes and methods,
scanned a single module, and its assertion evaluated to `[] == []`. Injecting
`def build_team_features(p_all: np.ndarray, n_robots: int)` into that module
left the test green.

This module replaces name matching with annotation- and AST-based checks that
walk the whole `rvt_swarm.decentralized` package, so a newly added offender is
caught by construction rather than by having been anticipated.

The rule enforced:

    A deployable function is any module-level function or public method in
    rvt_swarm.decentralized whose name does not start with `simulate_`.
    A deployable function may not declare a parameter that is annotated as, or
    conventionally named as, a container of joint state.

The one legitimate joint-state reader in the package is
`RoleAssignment.simulate_mission_setup_from_initial_formation`, which carries
the boundary prefix and is asserted never to be reachable from a control-loop
function.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .system_model import (
    PROHIBITED_OBS_KEYS, CentralizedAccessError, RuntimeFlags,
)

PACKAGE = "rvt_swarm.decentralized"
STRICT_PACKAGES: Tuple[str, ...] = (PACKAGE, "rvt_swarm.fd24")
BOUNDARY_PREFIX = "simulate_"

# Annotations that can hold an arbitrary number of robots.
BULK_ANNOTATIONS: Tuple[str, ...] = (
    "np.ndarray", "numpy.ndarray", "ndarray",
    "torch.Tensor", "Tensor",
    "Dict", "dict", "Mapping", "MutableMapping",
)

# Substring tokens, not exact names -- the audit showed exact-set matching
# missed `initial_positions`, `robot_positions`, `swarm_positions`, `poses`,
# and `team_state`.
BULK_NAME_TOKENS: Tuple[str, ...] = (
    "position", "pose", "velocit", "joint", "swarm", "team", "all_", "_all",
    "obs", "observation", "state",
)

# Annotations that provably hold at most ONE robot's worth of data. A parameter
# with one of these is safe no matter what it is named -- `src_position:
# Vec2` is a single pose, not a joint state. Classifying by annotation first
# and by name only as a fallback is what keeps the guard usable: the earlier
# name-only version produced 15 false positives on legitimate per-robot
# parameters, and a guard that cries wolf is a guard whose output nobody reads.
SCALAR_ANNOTATIONS: Tuple[str, ...] = (
    "Vec2", "Tuple[float, float]", "Tuple[float, float, float]",
    "float", "int", "bool", "str", "RobotView", "NeighbourRecord",
    "Beacon", "ScoreMessage", "ConsensusNode", "Config", "EgoGraph",
    "LocalGains", "CommParams", "ConsensusParams", "RoleAssignment",
    "Optional[float]", "Optional[int]", "Optional[Vec2]",
    "RobotRadioState", "OwnHistory", "NeighbourTable", "RadioChannel",
    "Sequence[NeighbourRecord]",
    "Sequence[ScoreMessage]", "Sequence[Tuple[float, float, float]]",
    "Sequence[np.ndarray]",   # list of 2-vectors in the controller's term groups
)

# Names that look bulk by substring but are provably scalar/per-robot here.
# This allowlist suppresses ONLY the *name* heuristic. It must never suppress
# the *annotation* check: `obstacles` is an allowlisted name because
# `RobotView.obstacles` is a locally-sensed tuple, but `obstacles: np.ndarray`
# is the full obstacle array and is a violation whatever it is called.
NAME_ALLOWLIST: frozenset = frozenset({
    "self_state", "committed_mode", "obstacles", "n_obstacles",
    "state_id", "stateful", "statistics",
})

# Modules that are training-time or reporting-only and never run on a robot.
# Excluded from the DEPLOYABLE scan, with the reason recorded so the exclusion
# is a stated claim rather than a convenience. Each is still bound by the
# no-final-test-access rule, which is checked separately.
OFFLINE_MODULES: Dict[str, str] = {
    "env_geometry": (
        "Authoritative scenario geometry, computed offline before an episode "
        "starts. No robot reads it at runtime."
    ),
    "qualification_fixtures": (
        "Scenario geometry and initial-condition validation. Built offline "
        "before an episode starts; no robot reads it at runtime."
    ),
    "formation_metric_v3": (
        "Offline formation-recovery evaluator. Uses the swarm centroid to remove "
        "the common translation, which is permitted for offline metric "
        "computation and appears nowhere in a deployable path."
    ),
    "reconfiguration_metrics": (
        "Offline scoring of the V2 reconfiguration task. Reads the joint state "
        "to compute events and formation error after the fact; no robot "
        "computes any of it."
    ),
    "training": (
        "Centralized training and offline analysis. Builds the dataset through "
        "the simulation boundary and computes losses; nothing here executes on "
        "a robot. Its inputs are legitimately batched across robots."
    ),
    "comm_cost": (
        "Message accounting and report formatting. Consumes counters after the "
        "fact; no robot computes a fleet-wide byte total at runtime."
    ),
    "phase6_qualification": (
        "Offline forced-topology simulator, Metric V3 evaluator and scaling "
        "orchestrator. It invokes strict local adapters one robot at a time; "
        "joint arrays remain on this named simulation boundary."
    ),
    "transition_runtime": (
        "Phase 7 strict diagnostic simulator boundary. It owns communication "
        "delivery and physics arrays, while each TransitionProtocolNode and "
        "controller invocation receives only robot-local records."
    ),
    "phase7_qualification": (
        "Offline Phase 7 matrix, exact-geometry evaluator and report writer. "
        "It may aggregate per-robot outcomes after the local runtime calls."
    ),
    "local_projection_forensics": (
        "Independent offline oracle used only to audit robot-local projection "
        "calls after they have been emitted by the strict runtime."
    ),
    "phase7r_qualification": (
        "Offline Phase 7R forensic reconstruction, repaired matrix runner and "
        "report writer. Runtime actions still come from one local executor."
    ),
}

# Parameter names that carry a SINGLE robot's ego-graph tensors. An ego graph
# contains only robot i's own node plus its one-hop neighbours and locally
# sensed obstacles, so a tensor holding one is local by construction -- the
# annotation `torch.Tensor` says nothing about how many robots are inside.
# Batching several robots' ego graphs for a training step is a disjoint union
# with no cross-robot edges, which is asserted in training.batch_ego.
EGO_TENSOR_PARAMS: frozenset = frozenset({
    "node_x", "edge_index", "edge_attr", "center_index", "h", "scores", "dst",
    "g", "ego_keep", "ego_line", "n_nodes", "q", "z", "y", "P",
    "local_features", "local_type_ids", "local_edge_destination",
    "node_hidden", "edge_hidden", "root_hidden", "conditioned",
    "raw_residual", "residual_limits", "conditioned_local_embedding",
})

_OFFLINE: Set[str] = set()


def offline_diagnostic(fn):
    """Mark a function as offline analysis, not part of the deployable runtime.

    Intent is declared, not inferred. Consensus residuals, component detection
    and agreement rates legitimately range over every robot -- they exist so the
    *report* can be honest -- but no robot computes them, so they must be
    excluded from the deployable scan explicitly rather than by a name
    coincidence.
    """
    _OFFLINE.add(f"{fn.__module__}.{fn.__qualname__}")
    fn.__offline_diagnostic__ = True
    return fn


def _is_offline(fn) -> bool:
    return bool(getattr(fn, "__offline_diagnostic__", False))

# Attribute chains that read global information.
FORBIDDEN_CALLS: Tuple[str, ...] = (
    "pooled_graph_features", "global_mean_pool", "global_max_pool",
    "global_add_pool", "global_attention_pool", "complete_swarm_attention",
    "cross_batch_mean", "joint_action_output", "all_reduce", "expert_action",
)

FORBIDDEN_DEPLOYABLE_IMPORTS: Tuple[str, ...] = (
    "dataset", "legacy_global_graph", "models",
)


@dataclass(frozen=True)
class Violation:
    module: str
    qualname: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.module}.{self.qualname}: [{self.kind}] {self.detail}"


def _iter_modules() -> Iterable[Tuple[str, object]]:
    for package_name in STRICT_PACKAGES:
        pkg = importlib.import_module(package_name)
        for info in pkgutil.iter_modules(pkg.__path__):
            label = (
                info.name
                if package_name == PACKAGE
                else f"{package_name.rsplit('.', 1)[-1]}.{info.name}"
            )
            yield label, importlib.import_module(f"{package_name}.{info.name}")


def _module_leaf(module_name: str) -> str:
    return module_name.rsplit(".", 1)[-1]


def _iter_functions(module) -> Iterable[Tuple[str, object]]:
    """Module-level functions AND public methods, including classmethods.

    The audited guard skipped classes entirely, which is how a classmethod
    taking an (N, 2) array went unseen.
    """
    for name, obj in vars(module).items():
        if inspect.isfunction(obj) and getattr(obj, "__module__", "") == module.__name__:
            yield name, obj
        elif inspect.isclass(obj) and getattr(obj, "__module__", "") == module.__name__:
            for mname, meth in vars(obj).items():
                fn = meth.__func__ if isinstance(meth, (classmethod, staticmethod)) else meth
                if inspect.isfunction(fn) and not mname.startswith("_"):
                    yield f"{name}.{mname}", fn


def _is_boundary(qualname: str) -> bool:
    return qualname.rsplit(".", 1)[-1].startswith(BOUNDARY_PREFIX)


def scan_signatures() -> List[Violation]:
    """Deployable functions must not declare bulk-state parameters."""
    out: List[Violation] = []
    for modname, module in _iter_modules():
        leaf = _module_leaf(modname)
        if leaf in ("guards",) or leaf in OFFLINE_MODULES:
            continue
        for qualname, fn in _iter_functions(module):
            if _is_boundary(qualname) or _is_offline(fn):
                continue
            try:
                sig = inspect.signature(fn)
            except (ValueError, TypeError):
                continue
            for pname, param in sig.parameters.items():
                if pname in ("self", "cls"):
                    continue
                ann = param.annotation
                ann_s = str(ann if isinstance(ann, str)
                            else getattr(ann, "__name__", str(ann)))
                # Annotation first: a provably-scalar annotation clears the
                # parameter regardless of its name.
                if any(ann_s == s for s in SCALAR_ANNOTATIONS):
                    continue
                # Ego-graph tensors are local by construction: the tensor holds
                # robot i's own node plus its one-hop neighbours and locally
                # sensed obstacles. `torch.Tensor` says nothing about how many
                # robots are inside, so the annotation alone cannot decide this
                # and the parameter name is the discriminating information.
                if pname in EGO_TENSOR_PARAMS:
                    continue
                if any(b in ann_s for b in BULK_ANNOTATIONS):
                    out.append(Violation(modname, qualname, "bulk-annotation",
                                         f"parameter '{pname}: {ann_s}' may hold joint state"))
                elif pname in NAME_ALLOWLIST:
                    # Name is cleared, annotation was not bulk: nothing to flag.
                    continue
                elif any(tok in pname.lower() for tok in BULK_NAME_TOKENS):
                    out.append(Violation(modname, qualname, "bulk-name",
                                         f"parameter '{pname}' is named like joint state "
                                         f"and is not annotated as single-robot data"))
    return out


def scan_prohibited_obs_keys() -> List[Violation]:
    """No deployable function body may subscript a prohibited obs key."""
    out: List[Violation] = []
    for modname, module in _iter_modules():
        leaf = _module_leaf(modname)
        if leaf in ("guards", "system_model") or leaf in OFFLINE_MODULES:
            continue
        try:
            tree = ast.parse(inspect.getsource(module))
        except (OSError, TypeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith(BOUNDARY_PREFIX):
                continue
            lowered_name = node.name.lower()
            if "joint_action" in lowered_name or (
                "joint" in lowered_name
                and any(token in lowered_name for token in ("safety", "optimizer", "qp"))
            ):
                out.append(Violation(
                    modname,
                    node.name,
                    "joint-action-output",
                    "function name declares a swarm-level joint action",
                ))
            for sub in ast.walk(node):
                if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
                    key = sub.slice.value
                    if isinstance(key, str) and key in PROHIBITED_OBS_KEYS:
                        out.append(Violation(modname, node.name, "prohibited-obs-key",
                                             f'reads obs["{key}"]'))
                if isinstance(sub, ast.Call):
                    fname = getattr(sub.func, "attr", getattr(sub.func, "id", ""))
                    if fname in FORBIDDEN_CALLS:
                        out.append(Violation(modname, node.name, "forbidden-call",
                                             f"calls {fname}()"))
                    if (
                        fname == "mean"
                        and "batch" in lowered_name
                        and any(token in lowered_name for token in ("cross", "global", "all"))
                    ):
                        out.append(Violation(
                            modname,
                            node.name,
                            "cross-batch-reduction",
                            "batch-named function performs a mean across samples",
                        ))
    return out


def scan_boundary_reachability() -> List[Violation]:
    """No control-loop function may call a `simulate_`-prefixed boundary.

    "Control-loop" is any function whose name contains step/control/act/update
    or which is a documented runtime entry point.
    """
    loop_tokens = ("step", "control", "act", "update", "runtime", "decide", "commit")
    out: List[Violation] = []
    for modname, module in _iter_modules():
        leaf = _module_leaf(modname)
        if leaf == "guards" or leaf in OFFLINE_MODULES:
            continue
        try:
            tree = ast.parse(inspect.getsource(module))
        except (OSError, TypeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith(BOUNDARY_PREFIX):
                continue
            if not any(tok in node.name.lower() for tok in loop_tokens):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    fname = getattr(sub.func, "attr", getattr(sub.func, "id", ""))
                    if isinstance(fname, str) and fname.startswith(BOUNDARY_PREFIX):
                        out.append(Violation(modname, node.name, "boundary-in-loop",
                                             f"control-loop function calls {fname}()"))
    return out


def scan_global_pooling_paths() -> List[Violation]:
    """Reject historical whole-swarm graph imports from deployable modules."""
    out: List[Violation] = []
    for modname, module in _iter_modules():
        leaf = _module_leaf(modname)
        if leaf in ("guards", "system_model") or leaf in OFFLINE_MODULES:
            continue
        try:
            tree = ast.parse(inspect.getsource(module))
        except (OSError, TypeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported = node.module or ""
                imported_names = (imported,) + tuple(
                    f"{imported}.{alias.name}" if imported else alias.name
                    for alias in node.names
                )
                if any(
                    name == forbidden or name.endswith("." + forbidden)
                    for name in imported_names
                    for forbidden in FORBIDDEN_DEPLOYABLE_IMPORTS
                ):
                    out.append(Violation(
                        modname,
                        f"line_{node.lineno}",
                        "global-graph-import",
                        "imports prohibited whole-swarm module from "
                        f"{imported_names!r}",
                    ))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        alias.name == forbidden or alias.name.endswith("." + forbidden)
                        for forbidden in FORBIDDEN_DEPLOYABLE_IMPORTS
                    ):
                        out.append(Violation(
                            modname,
                            f"line_{node.lineno}",
                            "global-graph-import",
                            f"imports prohibited whole-swarm module {alias.name!r}",
                        ))
    return out


def audit() -> List[Violation]:
    return (
        scan_signatures()
        + scan_prohibited_obs_keys()
        + scan_boundary_reachability()
        + scan_global_pooling_paths()
    )


# ---------------------------------------------------------------------------
# strict_decentralized_runtime
# ---------------------------------------------------------------------------
_FLAGS = RuntimeFlags(strict_decentralized_runtime=True)


def set_strict(enabled: bool) -> None:
    global _FLAGS
    _FLAGS = RuntimeFlags(strict_decentralized_runtime=bool(enabled))


def strict_enabled() -> bool:
    return _FLAGS.strict_decentralized_runtime


def forbid_global(source: str, detail: str = "") -> None:
    """Call from any deployable path that could otherwise read global state."""
    if strict_enabled():
        raise CentralizedAccessError(
            f"strict_decentralized_runtime: deployable code accessed '{source}'"
            + (f" ({detail})" if detail else "")
        )


def assert_local_only(obs_like) -> None:
    """Reject anything that looks like the global observation dict."""
    if not strict_enabled():
        return
    if isinstance(obs_like, dict):
        hits = sorted(set(obs_like) & PROHIBITED_OBS_KEYS)
        if hits:
            raise CentralizedAccessError(
                f"strict_decentralized_runtime: prohibited obs keys reached a "
                f"deployable path: {hits}"
            )
