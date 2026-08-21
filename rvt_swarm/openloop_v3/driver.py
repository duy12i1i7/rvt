"""The open-loop V3 training driver.

It orchestrates frozen contracts and defines none of its own. The loss is
``loss_v3.dataset_loss``; the Brier is ``metrics_v3.brier_split``; event
membership is ``loader_v3.V3EventGroup``; the model is ``RVTFD24LocalModel``.
Where a formula already exists, this module calls it rather than restating it,
because a second copy of the V3 loss inside a training loop is exactly the kind
of duplicate that drifts.

The minimum scientific unit is the decision event. Rows are never minibatched.

Optimizer construction is routed through :mod:`authorization`, which defaults to
deny. ``inspect`` mode cannot reach that gate at all because it never builds an
optimizer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import torch

from ..fd24 import loss_v3, metrics_v3
from ..fd24.loader_v3 import (
    V3EventGroup, batch_event_groups, deterministic_event_order,
    load_v3_event_groups,
)
from ..fd24.configuration import FD24ModelConfig
from ..fd24.model import RVTFD24LocalModel, prepare_fd24_model_batch
from ..runtime_configuration import DEFAULT_RUNTIME_CONFIG, RuntimeConfig
from ..topology_registry import COMPACT, LINE
from .authorization import (
    MECHANICAL_SEED, MODE_INSPECT, MODE_MECHANICAL, MODE_SCIENTIFIC,
    DatasetClassification, ScientificTrainingAuthorization,
    require_optimization_authorization, require_training_dataset,
)
from .m1 import M1LocalPredictor, m1_feature_batch
from .rehydrate import rehydrate_row
from .schedule import (
    EVENTS_PER_BATCH, EVALUATION_INTERVAL_STEPS, GRADIENT_NORM_CLIP,
    MAXIMUM_STEPS, WARMUP_STEPS, EarlyStopping, learning_rate_at,
)

FAMILY_M1 = "M1"
FAMILY_M2 = "M2"


class DriverContractError(ValueError):
    """A driver-contract violation that must fail closed."""


def enable_determinism(seed: int) -> None:
    """Everything a fit consumes randomness from, seeded explicitly."""
    torch.manual_seed(int(seed))
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


# ---------------------------------------------------------------------------
# dataset loading
# ---------------------------------------------------------------------------
def load_transactions(namespace: Path) -> Tuple[Mapping[str, Any], ...]:
    directory = Path(namespace)
    if not directory.is_dir():
        raise DriverContractError(f"no transaction directory at {directory}")
    return tuple(json.loads(path.read_text(encoding="ascii"))
                 for path in sorted(directory.glob("event-*.json")))


def load_events(namespace: Path, *, split: str) -> Tuple[V3EventGroup, ...]:
    return load_v3_event_groups(load_transactions(namespace), split=split)


@dataclass
class GraphCache:
    """Rehydrated graphs, keyed by scientific row id.

    Rehydration is deterministic and pure, so caching changes nothing scientific;
    it only avoids re-hashing every payload on every epoch.

    The runtime configuration is NOT held globally. Each row declares its own
    team size and the generator used ``RuntimeConfig.for_team_size(N)``, so the
    configuration is resolved per row and memoized per team size.
    """

    _graphs: Dict[str, Any] = field(default_factory=dict)
    _configs: Dict[int, RuntimeConfig] = field(default_factory=dict)
    rehydrations: int = 0

    def config_for(self, team_size: int) -> RuntimeConfig:
        config = self._configs.get(int(team_size))
        if config is None:
            config = RuntimeConfig.for_team_size(int(team_size))
            self._configs[int(team_size)] = config
        return config

    def graphs_for(self, candidate: Any) -> Tuple[Any, ...]:
        out = []
        for row in candidate.rows:
            key = str(row["scientific_row_id"])
            graph = self._graphs.get(key)
            if graph is None:
                config = self.config_for(
                    int(row["scientific_identity"]["team_size"]))
                graph = rehydrate_row(row, config)
                self._graphs[key] = graph
                self.rehydrations += 1
            out.append(graph)
        return tuple(out)


# ---------------------------------------------------------------------------
# forward
# ---------------------------------------------------------------------------
def _m2_logits_by_group(model: RVTFD24LocalModel, graphs: Sequence[Any],
                        group_of_input: Sequence[int], groups: int,
                        ) -> List[torch.Tensor]:
    """One batched forward, then split logits back to their candidate groups.

    ``prepare_fd24_model_batch`` reorders graphs canonically and reports the
    permutation, so the mapping back is exact. The frozen loss takes an unordered
    mean over the N robots of a candidate, so within-group order is immaterial.
    """
    batch = prepare_fd24_model_batch(tuple(graphs))
    conditioned = model.conditioned_representation(batch)
    logits = model.recoverability_head(conditioned)
    order = batch.graph_batch.canonical_to_input_order
    canonical_group = torch.tensor(
        [group_of_input[order[position]] for position in range(len(order))],
        dtype=torch.int64)
    out = []
    for index in range(groups):
        selected = torch.nonzero(canonical_group == index, as_tuple=False).flatten()
        if selected.numel() == 0:
            raise DriverContractError("a candidate group lost all of its robot rows")
        out.append(logits.index_select(0, selected))
    return out


def event_terms(model: torch.nn.Module, family: str,
                groups: Sequence[V3EventGroup], cache: GraphCache,
                ) -> List[Mapping[str, Any]]:
    """Build exactly the record ``loss_v3.dataset_loss`` consumes."""
    if family not in (FAMILY_M1, FAMILY_M2):
        raise DriverContractError(f"unknown model family {family!r}")
    flat_graphs: List[Any] = []
    group_of_input: List[int] = []
    ordered_candidates: List[Tuple[int, Any]] = []
    for event_index, group in enumerate(groups):
        for candidate in (group.compact, group.line):
            slot = len(ordered_candidates)
            ordered_candidates.append((event_index, candidate))
            for graph in cache.graphs_for(candidate):
                flat_graphs.append(graph)
                group_of_input.append(slot)
    if not flat_graphs:
        raise DriverContractError("a batch must carry at least one robot row")

    if family == FAMILY_M2:
        per_group = _m2_logits_by_group(
            model, flat_graphs, group_of_input, len(ordered_candidates))
    else:
        features = m1_feature_batch(flat_graphs)
        logits = model(features)
        index = torch.tensor(group_of_input, dtype=torch.int64)
        per_group = []
        for slot in range(len(ordered_candidates)):
            selected = torch.nonzero(index == slot, as_tuple=False).flatten()
            per_group.append(logits.index_select(0, selected))

    terms: List[Dict[str, Any]] = [{} for _ in groups]
    for slot, (event_index, candidate) in enumerate(ordered_candidates):
        prefix = "compact" if int(candidate.candidate_topology_id) == COMPACT else "line"
        if int(candidate.candidate_topology_id) not in (COMPACT, LINE):
            raise DriverContractError("a candidate must be COMPACT or LINE")
        terms[event_index][f"{prefix}_logits"] = per_group[slot]
        terms[event_index][f"{prefix}_k"] = int(candidate.k)
        terms[event_index][f"{prefix}_R"] = int(candidate.R)
    for term in terms:
        if set(term) != {"compact_logits", "compact_k", "compact_R",
                         "line_logits", "line_k", "line_R"}:
            raise DriverContractError("an event did not produce both candidates")
    return terms


def dataset_nll(model: torch.nn.Module, family: str,
                groups: Sequence[V3EventGroup], cache: GraphCache,
                *, events_per_batch: int = EVENTS_PER_BATCH) -> float:
    """Event-equal NLL over a whole split, evaluated without gradients.

    Batches are averaged by EVENT COUNT, not by batch count, so a short final
    batch cannot silently up-weight its events.
    """
    model.eval()
    total = 0.0
    counted = 0
    with torch.no_grad():
        for batch in batch_event_groups(tuple(groups), events_per_batch=events_per_batch):
            terms = event_terms(model, family, batch, cache)
            total += float(loss_v3.dataset_loss(terms)) * len(batch)
            counted += len(batch)
    if counted == 0:
        raise DriverContractError("an evaluation split must contain events")
    return total / float(counted)


def dataset_brier(model: torch.nn.Module, family: str,
                  groups: Sequence[V3EventGroup], cache: GraphCache,
                  *, events_per_batch: int = EVENTS_PER_BATCH) -> float:
    model.eval()
    total = 0.0
    counted = 0
    with torch.no_grad():
        for batch in batch_event_groups(tuple(groups), events_per_batch=events_per_batch):
            terms = event_terms(model, family, batch, cache)
            scored = [{
                "compact_probabilities": torch.sigmoid(term["compact_logits"]),
                "compact_k": term["compact_k"], "compact_R": term["compact_R"],
                "line_probabilities": torch.sigmoid(term["line_logits"]),
                "line_k": term["line_k"], "line_R": term["line_R"],
            } for term in terms]
            total += float(metrics_v3.brier_split(scored)) * len(batch)
            counted += len(batch)
    return total / float(counted)


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------
def build_model(family: str, *, runtime_config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG,
                ) -> torch.nn.Module:
    if family == FAMILY_M2:
        return RVTFD24LocalModel(FD24ModelConfig(), runtime_config)
    if family == FAMILY_M1:
        return M1LocalPredictor()
    raise DriverContractError(f"unknown model family {family!r}")


def optimized_parameters(model: torch.nn.Module, family: str,
                         ) -> List[torch.nn.Parameter]:
    """Only the recoverability path. The residual head is frozen out entirely.

    Two independent mechanisms, because one would be a single point of failure:
    the head's parameters get ``requires_grad_(False)`` AND are absent from the
    optimizer's parameter list. AdamW's decoupled weight decay only touches
    parameters it holds, so an excluded parameter cannot drift either.
    """
    if family == FAMILY_M1:
        return list(model.parameters())
    if not isinstance(model, RVTFD24LocalModel):
        raise DriverContractError("M2 requires RVTFD24LocalModel")
    for parameter in model.residual_action_head.parameters():
        parameter.requires_grad_(False)
    trainable = []
    for module in (model.encoder, model.candidate_conditioner,
                   model.recoverability_head):
        trainable.extend(module.parameters())
    return trainable


@dataclass
class MechanicalRunResult:
    steps: int
    metric_trace: Tuple[Tuple[int, float], ...]
    event_order: Tuple[str, ...]
    best_step: Optional[int]
    best_value: Optional[float]
    stopped_early: bool
    state_dict_sha256: str
    residual_state_sha256_before: Optional[str]
    residual_state_sha256_after: Optional[str]


def _residual_hash(model: torch.nn.Module, family: str) -> Optional[str]:
    if family != FAMILY_M2:
        return None
    from ..fd24.checkpoint import canonical_state_dict_hash
    return canonical_state_dict_hash({
        name: tensor.detach().cpu().clone()
        for name, tensor in model.residual_action_head.state_dict().items()})


def run_training(
    *, family: str, mode: str, fit_groups: Sequence[V3EventGroup],
    held_out_groups: Sequence[V3EventGroup], cache: GraphCache,
    dataset_root: Path, seed: int, learning_rate: float, weight_decay: float,
    maximum_steps: int = MAXIMUM_STEPS,
    evaluation_interval: int = EVALUATION_INTERVAL_STEPS,
    warmup_steps: int = WARMUP_STEPS,
    events_per_batch: int = EVENTS_PER_BATCH,
    classification: Optional[DatasetClassification] = None,
    authorization: Optional[ScientificTrainingAuthorization] = None,
    declared_split: Optional[str] = None,
    model: Optional[torch.nn.Module] = None,
) -> MechanicalRunResult:
    """One fit. The authorization gate runs BEFORE anything is constructed."""
    if mode == MODE_INSPECT:
        raise DriverContractError("inspect mode does not train")
    require_optimization_authorization(
        mode=mode, dataset_root=Path(dataset_root), seed=int(seed),
        classification=classification, authorization=authorization,
        declared_split=declared_split)

    enable_determinism(seed)
    model = model if model is not None else build_model(family)
    parameters = optimized_parameters(model, family)
    residual_before = _residual_hash(model, family)
    optimizer = torch.optim.AdamW(parameters, lr=learning_rate,
                                  weight_decay=weight_decay)

    ordered = deterministic_event_order(tuple(fit_groups), seed=int(seed))
    event_order = tuple(group.decision_event_id for group in ordered)
    batches = batch_event_groups(ordered, events_per_batch=events_per_batch)
    stopper = EarlyStopping()

    step = 0
    position = 0
    trace: List[Tuple[int, float]] = []
    while step < maximum_steps:
        model.train()
        batch = batches[position % len(batches)]
        position += 1
        for group in optimizer.param_groups:
            group["lr"] = learning_rate_at(
                step, base_learning_rate=learning_rate, warmup_steps=warmup_steps)
        optimizer.zero_grad(set_to_none=True)
        loss = loss_v3.dataset_loss(event_terms(model, family, batch, cache))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, GRADIENT_NORM_CLIP)
        optimizer.step()
        step += 1
        if step % evaluation_interval == 0:
            value = dataset_nll(model, family, held_out_groups, cache,
                                events_per_batch=events_per_batch)
            trace.append((step, value))
            if stopper.update(step, value):
                break

    from ..fd24.checkpoint import canonical_state_dict_hash
    state_hash = canonical_state_dict_hash({
        name: tensor.detach().cpu().clone()
        for name, tensor in model.state_dict().items()})
    return MechanicalRunResult(
        steps=step, metric_trace=tuple(trace), event_order=event_order,
        best_step=stopper.best_step, best_value=stopper.best_value,
        stopped_early=stopper.stopped_early, state_dict_sha256=state_hash,
        residual_state_sha256_before=residual_before,
        residual_state_sha256_after=_residual_hash(model, family))


# ---------------------------------------------------------------------------
# inspect mode -- structural, read-only, no optimizer anywhere in this path
# ---------------------------------------------------------------------------
def inspect_dataset(namespace: Path, *, split: str, dataset_root: Path,
                    folds: Optional[Any] = None,
                    forward_untrained_m2: bool = False,
                    ) -> Mapping[str, Any]:
    """Structural census. Loads, rehydrates, extracts features, never optimizes."""
    classification = require_training_dataset(Path(dataset_root),
                                              declared_split=split)
    groups = load_events(namespace, split=split)
    cache = GraphCache()
    rows = 0
    m1_failures = 0
    m2_failures = 0
    team_sizes: Dict[int, int] = {}
    replica_counts: Dict[int, int] = {}
    fold_counts: Dict[str, int] = {}
    fold_failures = 0
    model = build_model(FAMILY_M2) if forward_untrained_m2 else None

    for group in groups:
        team_sizes[group.team_size] = team_sizes.get(group.team_size, 0) + 1
        for candidate in (group.compact, group.line):
            replica_counts[int(candidate.R)] = replica_counts.get(int(candidate.R), 0) + 1
            graphs = cache.graphs_for(candidate)
            rows += len(graphs)
            try:
                features = m1_feature_batch(graphs)
                if features.shape[1] != 56 or features.dtype != torch.float32:
                    m1_failures += 1
                elif not bool(torch.isfinite(features).all()):
                    m1_failures += 1
            except Exception:                                    # noqa: BLE001
                m1_failures += 1
            try:
                batch = prepare_fd24_model_batch(graphs)
                if batch.n_graphs != len(graphs):
                    m2_failures += 1
                elif model is not None:
                    with torch.no_grad():
                        conditioned = model.conditioned_representation(batch)
                        logits = model.recoverability_head(conditioned)
                    if logits.shape != (len(graphs),) or not bool(
                            torch.isfinite(logits).all()):
                        m2_failures += 1
            except Exception:                                    # noqa: BLE001
                m2_failures += 1
        if folds is not None:
            try:
                digests = {str(row["scientific_identity"]["layout_sha256"])
                           for candidate in (group.compact, group.line)
                           for row in candidate.rows}
                if len(digests) != 1:
                    fold_failures += 1
                else:
                    name = folds.fold_of(next(iter(digests)))
                    fold_counts[name] = fold_counts.get(name, 0) + 1
            except Exception:                                    # noqa: BLE001
                fold_failures += 1
    return {
        "mode": MODE_INSPECT,
        "dataset_origin": classification.origin,
        "dataset_split": classification.v3_split,
        "events": len(groups),
        "rows_rehydrated": rows,
        "rehydration_failures": 0,
        "m1_feature_failures": m1_failures,
        "m2_batch_failures": m2_failures,
        "fold_assignment_failures": fold_failures,
        "events_by_fold": dict(sorted(fold_counts.items())),
        "events_by_team_size": dict(sorted(team_sizes.items())),
        "candidates_by_replica_count": dict(sorted(replica_counts.items())),
        "optimizer_steps": 0,
        "optimizers_constructed": 0,
        "untrained_forward_scores_reported": False,
    }
