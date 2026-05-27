import unittest

import numpy as np

from rvt_swarm.baselines import orca
from rvt_swarm.config import Config


class OrcaBaselineTest(unittest.TestCase):
    def test_orca_returns_finite_actions(self) -> None:
        cfg = Config()
        obs = {
            "positions": np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.float32),
            "velocities": np.zeros((2, 2), dtype=np.float32),
            "goal": np.array([3.0, 0.0], dtype=np.float32),
            "obstacles": np.zeros((0, 2), dtype=np.float32),
            "obstacle_velocities": np.zeros((0, 2), dtype=np.float32),
            "bottleneck": 0.0,
            "progress": 0.0,
            "recovery_progress": 0.0,
            "split_active": 0.0,
            "topology_mode": 0,
            "formation_scale": 1.0,
            "corridor_dx": 1.0,
            "corridor_dy": 0.0,
            "subteam_ids": np.zeros((2,), dtype=np.int64),
        }

        actions, topology = orca(obs, cfg)

        self.assertEqual(topology, 0)
        self.assertEqual(actions.shape, (2, 2))
        self.assertTrue(np.isfinite(actions).all())
        self.assertLessEqual(float(np.max(np.linalg.norm(actions, axis=1))), cfg.env.max_accel + 1e-5)


if __name__ == "__main__":
    unittest.main()
