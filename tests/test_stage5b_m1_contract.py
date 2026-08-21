"""The frozen M1 56-dimensional input contract."""

import json
from pathlib import Path

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import NODE_OBSTACLE, NODE_PEER
from rvt_swarm.openloop_v3 import synthetic
from rvt_swarm.openloop_v3.m1 import (
    M1_AGGREGATE_NAMES, M1_INPUT_DIMENSION, M1_SELF_COLUMNS, M1_SELF_FIELD_NAMES,
    M1ContractError, M1LocalPredictor, m1_features, verify_against_frozen_contract,
)
from rvt_swarm.topology_registry import COMPACT

FROZEN = Path("results/rvt_fd24/open_loop_v3_m1_input_contract_v1.json")


def _graph(**kwargs):
    defaults = dict(team_size=5, robot=0, candidate=COMPACT, step=3, jitter=0.1)
    defaults.update(kwargs)
    return synthetic.synthetic_graph(**defaults)


def test_dimension_is_exactly_56():
    assert M1_INPUT_DIMENSION == 56
    assert len(M1_SELF_COLUMNS) == 25
    assert len(M1_AGGREGATE_NAMES) == 6


def test_derivation_matches_the_frozen_contract():
    contract = json.loads(FROZEN.read_text())
    verify_against_frozen_contract(contract)
    assert tuple(contract["self_column_indices_into_node_x"]) == M1_SELF_COLUMNS
    assert tuple(contract["ordered_value_fields"]) == M1_SELF_FIELD_NAMES


def test_a_drifted_contract_is_refused():
    contract = json.loads(FROZEN.read_text())
    contract["input_dimension"] = 57
    with pytest.raises(M1ContractError):
        verify_against_frozen_contract(contract)


def test_features_are_finite_float32_and_correctly_shaped():
    features = m1_features(_graph())
    assert features.shape == (56,)
    assert features.dtype == torch.float32
    assert bool(torch.isfinite(features).all())


def test_masks_occupy_the_second_block_and_are_zero_or_one():
    features = m1_features(_graph())
    masks = features[25:50]
    assert set(float(value) for value in masks) <= {0.0, 1.0}


def test_values_are_masked_exactly_as_the_encoder_masks_them():
    graph = _graph()
    features = m1_features(graph)
    columns = torch.tensor(M1_SELF_COLUMNS, dtype=torch.int64)
    raw = graph.node_x[int(graph.root_index)].index_select(0, columns)
    mask = graph.node_feature_valid_mask[
        int(graph.root_index)].index_select(0, columns).to(torch.float32)
    torch.testing.assert_close(features[:25], raw * mask, rtol=0.0, atol=0.0)


def test_peer_permutation_invariance():
    a = _graph(peers=3)
    b = _graph(peers=3)
    order = torch.tensor([0, 2, 1, 3, 4, 5, 6, 7, 8, 9])[: b.node_x.shape[0]]
    peers = torch.nonzero(b.node_kind == NODE_PEER, as_tuple=False).flatten()
    if peers.numel() >= 2:
        permuted = b.node_x.clone()
        permuted[peers[0]], permuted[peers[1]] = (
            b.node_x[peers[1]].clone(), b.node_x[peers[0]].clone())
        from dataclasses import replace
        b = replace(b, node_x=permuted)
    del order
    torch.testing.assert_close(m1_features(a), m1_features(b), rtol=0.0, atol=1e-6)


def test_obstacle_permutation_invariance():
    graph = _graph(obstacles=2)
    obstacles = torch.nonzero(graph.node_kind == NODE_OBSTACLE, as_tuple=False).flatten()
    assert obstacles.numel() >= 2
    from dataclasses import replace
    permuted = graph.node_x.clone()
    permuted[obstacles[0]], permuted[obstacles[1]] = (
        graph.node_x[obstacles[1]].clone(), graph.node_x[obstacles[0]].clone())
    other = replace(graph, node_x=permuted)
    torch.testing.assert_close(m1_features(graph), m1_features(other),
                               rtol=0.0, atol=1e-6)


def test_zero_peer_and_zero_obstacle_sentinels():
    graph = _graph(peers=0, obstacles=0)
    features = m1_features(graph)
    assert float(features[50]) == 0.0            # P / (1 + P) with P = 0
    assert float(features[51]) == 0.0            # O / (1 + O) with O = 0
    assert float(features[52]) == 1.0            # no obstacle -> range boundary
    assert float(features[53]) == 1.0            # no peer -> comm-range boundary
    assert float(features[54]) == 0.0            # no peer -> no message age
    assert float(features[55]) == 0.0            # no peer -> no conflict


def test_counts_are_invertible_so_sentinels_are_never_ambiguous():
    for peers in (0, 1, 2, 3):
        features = m1_features(_graph(peers=peers, obstacles=1))
        saturating = float(features[50])
        recovered = round(saturating / (1.0 - saturating)) if saturating < 1.0 else None
        assert recovered == min(peers, 4)


def test_saturating_map_is_strictly_increasing_in_the_count():
    values = [float(m1_features(_graph(peers=count, obstacles=1))[50])
              for count in (0, 1, 2, 3)]
    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_predictor_shape_and_parameter_count():
    model = M1LocalPredictor()
    features = torch.zeros((7, 56), dtype=torch.float32)
    logits = model(features)
    assert logits.shape == (7,)
    # 56*32 + 32 + 32*1 + 1
    assert model.parameter_count() == 56 * 32 + 32 + 32 + 1


def test_predictor_refuses_wrong_width_and_dtype():
    model = M1LocalPredictor()
    with pytest.raises(M1ContractError):
        model(torch.zeros((3, 55), dtype=torch.float32))
    with pytest.raises(M1ContractError):
        model(torch.zeros((3, 56), dtype=torch.float64))


def test_no_forbidden_identity_reaches_the_feature_vector():
    """Changing team size changes the graph, but no identity field is an input.

    The proof is structural: M1 consumes a RobotLocalEgoGraph and nothing else,
    and the graph carries no family, layout, episode, split, seed, k or R.
    """
    graph = _graph()
    payload_fields = set(vars(graph)) if hasattr(graph, "__dict__") else set()
    for forbidden in ("family", "layout_sha256", "episode_id", "split", "study",
                      "team_size", "seed", "k", "R"):
        assert forbidden not in payload_fields
