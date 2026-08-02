"""Tiny deterministic synthetic capacity check, not scientific training."""

import torch
import torch.nn.functional as F

from rvt_swarm.decentralized.ego_graph_v2 import build_robot_local_ego_graph
from rvt_swarm.fd24.configuration import FD24ModelConfig
from rvt_swarm.fd24.model import RVTFD24LocalModel, prepare_fd24_model_batch
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def test_tiny_candidate_mapping_can_be_overfit_mechanically(ego_v2_factory):
    torch.manual_seed(202605)
    case = ego_v2_factory(peer_ids=(), obstacles=())
    graphs = tuple(build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate,
        case.observation_step,
    ) for candidate in (KEEP, COMPACT, LINE))
    local_batch = prepare_fd24_model_batch(graphs)
    config = FD24ModelConfig(
        hidden_dimension=24,
        message_passing_blocks=1,
        candidate_embedding_dimension=8,
    )
    model = RVTFD24LocalModel(config, case.config)
    target_logit_by_id = {KEEP: -1.0, COMPACT: 0.25, LINE: 1.25}
    target_residual_by_id = {
        KEEP: (-0.05, 0.00),
        COMPACT: (0.00, 0.05),
        LINE: (0.05, -0.05),
    }
    candidate_ids = local_batch.graph_batch.candidate_topology_id.tolist()
    target_logit = torch.tensor([target_logit_by_id[item] for item in candidate_ids])
    target_residual = torch.tensor([
        target_residual_by_id[item] for item in candidate_ids
    ])
    optimizer = torch.optim.Adam(model.parameters(), lr=0.02)

    def synthetic_loss():
        output = model(local_batch)
        return (
            F.mse_loss(output.recoverability_logit, target_logit)
            + F.mse_loss(output.residual_action, target_residual)
        )

    initial = float(synthetic_loss().detach())
    for _ in range(80):
        loss = synthetic_loss()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
    final = float(synthetic_loss().detach())
    assert final < initial * 0.01
    assert final < 1.0e-3
