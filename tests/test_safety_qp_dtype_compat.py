import sys
import types
import unittest

import numpy as np

if "torch" not in sys.modules:
    sys.modules["torch"] = types.ModuleType("torch")

from rvt_swarm.safety import _solve_per_robot_qp


class SolvePerRobotQPDtypeCompatTest(unittest.TestCase):
    def test_qp_solver_does_not_depend_on_numpy_float64_attribute(self) -> None:
        original = getattr(np, "float64", None)
        try:
            np.float64 = None
            out = _solve_per_robot_qp(
                u_nom=np.array([0.8, 0.2], dtype=np.float32),
                constraints=[(np.array([1.0, 0.0], dtype=np.float32), 0.5)],
                progress_dir=np.array([0.0, 0.0], dtype=np.float32),
                max_accel=1.0,
                progress_weight=0.0,
            )
        finally:
            if original is None:
                delattr(np, "float64")
            else:
                np.float64 = original

        self.assertEqual(out.shape, (2,))
        self.assertEqual(out.dtype, np.float32)
        self.assertTrue(np.isfinite(out).all())
        self.assertGreaterEqual(float(out[0]), 0.5 - 1e-5)


if __name__ == "__main__":
    unittest.main()
