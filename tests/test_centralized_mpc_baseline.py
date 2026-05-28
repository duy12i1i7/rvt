import unittest

import numpy as np

from rvt_swarm.baselines import centralized_mpc
from rvt_swarm.config import Config


class CentralizedMpcBaselineTest(unittest.TestCase):
    def test_centralized_mpc_returns_finite_actions(self) -> None:
        cfg = Config()
        obs = {
            "positions": np.array(
                [[-0.6, -0.3], [-0.6, 0.3], [-1.4, -0.3], [-1.4, 0.3]],
                dtype=np.float32,
            ),
            "velocities": np.zeros((4, 2), dtype=np.float32),
            "goal": np.array([3.0, 0.0], dtype=np.float32),
            "obstacles": np.array([[0.0, 1.2], [0.0, -1.2]], dtype=np.float32),
            "obstacle_velocities": np.zeros((2, 2), dtype=np.float32),
            "scenario": "narrow_passage",
            "goal_distance": 4.0,
            "bottleneck": 0.8,
            "progress": 0.0,
            "recovery_progress": 0.0,
            "split_active": 0.0,
            "topology_mode": 0,
            "formation_scale": 1.0,
            "stall_counter": 0,
            "topology_switches": 0,
            "time_since_switch": 0,
            "formation_scale_motion": 0.0,
            "corridor_dx": 1.0,
            "corridor_dy": 0.0,
            "subteam_ids": np.zeros((4,), dtype=np.int64),
        }

        actions, topology = centralized_mpc(obs, cfg)

        self.assertIn(topology, {0, 1, 2, 3, 4})
        self.assertEqual(actions.shape, (4, 2))
        self.assertTrue(np.isfinite(actions).all())
        self.assertLessEqual(float(np.max(np.linalg.norm(actions, axis=1))), cfg.env.max_accel + 1e-5)


if __name__ == "__main__":
    unittest.main()
