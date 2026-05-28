import unittest

import numpy as np

from rvt_swarm.baselines import cbf_qp
from rvt_swarm.config import Config
from rvt_swarm.safety import _build_cbf_constraints


class CbfQpBaselineTest(unittest.TestCase):
    def test_cbf_qp_returns_feasible_bounded_actions(self) -> None:
        cfg = Config()
        obs = {
            "positions": np.array([[0.0, 0.0], [0.38, 0.0]], dtype=np.float32),
            "velocities": np.zeros((2, 2), dtype=np.float32),
            "goal": np.array([3.0, 0.0], dtype=np.float32),
            "obstacles": np.array([[0.20, 0.80]], dtype=np.float32),
            "obstacle_velocities": np.zeros((1, 2), dtype=np.float32),
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

        actions, topology = cbf_qp(obs, cfg)

        self.assertEqual(topology, 0)
        self.assertEqual(actions.shape, (2, 2))
        self.assertTrue(np.isfinite(actions).all())
        self.assertLessEqual(float(np.max(np.linalg.norm(actions, axis=1))), cfg.env.max_accel + 1e-5)

        for robot_idx in range(len(actions)):
            constraints = _build_cbf_constraints(robot_idx, obs, cfg)
            for a, b in constraints:
                lhs = float(np.dot(a, actions[robot_idx]))
                self.assertGreaterEqual(lhs + 1e-5, float(b))


if __name__ == "__main__":
    unittest.main()
