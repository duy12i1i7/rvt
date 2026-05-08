import sys
import types
import unittest

import numpy as np

if "torch" not in sys.modules:
    sys.modules["torch"] = types.ModuleType("torch")

from rvt_swarm.config import Config
from rvt_swarm.controllers import expert_action
from rvt_swarm.dataset import build_graph_arrays
from rvt_swarm.environment import SwarmFormationEnv


class RuntimeWithoutNumpyDotTest(unittest.TestCase):
    def test_runtime_paths_work_without_numpy_dot_attribute(self) -> None:
        cfg = Config()
        env = SwarmFormationEnv(cfg)
        obs = env.reset(4, "open_field", seed=123)

        original = getattr(np, "dot", None)
        try:
            np.dot = None
            node_x, edge_index, edge_attr = build_graph_arrays(obs, cfg)
            actions = expert_action(obs, cfg, topology_action=0)
            next_obs, reward, done, info = env.step(actions, 0)
        finally:
            if original is None:
                delattr(np, "dot")
            else:
                np.dot = original

        self.assertEqual(node_x.shape[0], 4)
        self.assertEqual(edge_index.shape[0], 2)
        self.assertEqual(edge_attr.shape[1], 11)
        self.assertEqual(actions.shape, (4, 2))
        self.assertEqual(next_obs["positions"].shape, (4, 2))
        self.assertIsInstance(reward, float)
        self.assertIsInstance(done, bool)
        self.assertIn("success", info)


if __name__ == "__main__":
    unittest.main()
