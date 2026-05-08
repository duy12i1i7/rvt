import unittest

import numpy as np

from rvt_swarm.config import Config
from rvt_swarm.dataset import EDGE_DIM, NODE_DIM, build_graph_arrays
from rvt_swarm.environment import SwarmFormationEnv


class BuildGraphRuntimeCompatTest(unittest.TestCase):
    def test_missing_runtime_scalars_fall_back_to_defaults(self) -> None:
        cfg = Config()
        env = SwarmFormationEnv(cfg)
        obs = env.reset(4, "open_field", seed=123)
        for key in [
            "formation_scale",
            "bottleneck",
            "progress",
            "split_active",
            "corridor_dx",
            "corridor_dy",
            "topology_mode",
        ]:
            obs.pop(key, None)

        node_x, edge_index, edge_attr = build_graph_arrays(obs, cfg)

        self.assertEqual(node_x.shape, (4, NODE_DIM))
        self.assertEqual(edge_index.shape[0], 2)
        self.assertEqual(edge_attr.shape[1], EDGE_DIM)
        self.assertTrue(np.isfinite(node_x).all())
        self.assertTrue(np.isfinite(edge_attr).all())


if __name__ == "__main__":
    unittest.main()
