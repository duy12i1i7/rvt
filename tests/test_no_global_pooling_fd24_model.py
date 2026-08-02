"""Non-vacuous guards against whole-swarm and cross-batch aggregation."""

import contextlib
import importlib
import inspect
from pathlib import Path
import sys

import pytest

import rvt_swarm.fd24 as fd24
from rvt_swarm.decentralized import guards
from rvt_swarm.fd24 import model as fd24_model


FD24_PACKAGE = Path(fd24.__file__).parent
TEMPORARY_MODULE = FD24_PACKAGE / "_tmp_fd24_violation.py"


@contextlib.contextmanager
def injected_fd24_module(source):
    TEMPORARY_MODULE.write_text(
        "from __future__ import annotations\nimport torch\n" + source
    )
    try:
        importlib.invalidate_caches()
        yield
    finally:
        TEMPORARY_MODULE.unlink(missing_ok=True)
        importlib.invalidate_caches()
        sys.modules.pop("rvt_swarm.fd24._tmp_fd24_violation", None)


def _kinds(violations):
    return {violation.kind for violation in violations}


def test_clean_fd24_namespace_has_no_global_pooling_path():
    assert guards.audit() == []
    assert guards.scan_global_pooling_paths() == []


def test_authoritative_model_source_uses_root_readout_not_global_pooling():
    source = inspect.getsource(fd24_model)
    forbidden = (
        "global_mean_pool(", "global_max_pool(", "global_add_pool(",
        "global_attention_pool(", "complete_swarm_attention(",
        "pooled_graph_features(", "cross_batch_mean(",
    )
    assert all(token not in source for token in forbidden)
    assert "node_hidden[batch.root_index]" in source


@pytest.mark.parametrize(
    "call",
    (
        "global_mean_pool(local_features, graph_index)",
        "global_max_pool(local_features, graph_index)",
        "global_add_pool(local_features, graph_index)",
        "global_attention_pool(local_features, graph_index)",
        "complete_swarm_attention(local_features)",
    ),
)
def test_guard_detects_injected_whole_swarm_pooling(call):
    with injected_fd24_module(
        f"def score(local_features, graph_index):\n    return {call}\n"
    ):
        violations = guards.audit()
    assert "forbidden-call" in _kinds(violations), (call, violations)


def test_guard_detects_injected_cross_batch_mean():
    with injected_fd24_module(
        "def cross_batch_reduce(local_features):\n"
        "    return local_features.mean(dim=0)\n"
    ):
        violations = guards.audit()
    assert "cross-batch-reduction" in _kinds(violations), violations


@pytest.mark.parametrize("legacy_module", ("models", "legacy_global_graph"))
def test_guard_detects_legacy_global_model_or_graph_import(legacy_module):
    with injected_fd24_module(f"from rvt_swarm import {legacy_module}\n"):
        violations = guards.audit()
    assert "global-graph-import" in _kinds(violations), violations
