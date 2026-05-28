import unittest

from run_experiments import aggregate_multiseed_by_team_size, aggregate_multiseed_summary


class MultiSeedAggregationTest(unittest.TestCase):
    def test_aggregate_summary_reports_ci_and_reference_comparison(self) -> None:
        seed_summaries = {
            0: {
                "rvt_swarm": {"success": 0.50, "collision_free": 0.60, "form_ok": 0.70},
                "orca": {"success": 0.30, "collision_free": 0.50, "form_ok": 0.40},
            },
            1: {
                "rvt_swarm": {"success": 0.70, "collision_free": 0.80, "form_ok": 0.90},
                "orca": {"success": 0.40, "collision_free": 0.55, "form_ok": 0.45},
            },
        }

        report = aggregate_multiseed_summary(
            seed_summaries,
            reference="rvt_swarm",
            permutation_draws=200,
            permutation_seed=0,
        )

        self.assertEqual(report["seeds"], [0, 1])
        self.assertAlmostEqual(report["methods"]["rvt_swarm"]["metrics"]["success"]["mean"], 0.60)
        self.assertEqual(report["methods"]["rvt_swarm"]["metrics"]["success"]["n"], 2)
        self.assertIn("ci95_low", report["methods"]["rvt_swarm"]["metrics"]["success"])
        self.assertIn("vs_reference", report["methods"]["orca"])
        self.assertAlmostEqual(
            report["methods"]["orca"]["vs_reference"]["success_mean_delta"],
            0.25,
        )

    def test_aggregate_by_team_size_groups_team_entries(self) -> None:
        seed_team_summaries = {
            0: {
                "rvt_swarm": {
                    "2": {"success": 0.5},
                    "4": {"success": 0.6},
                },
                "orca": {
                    "2": {"success": 0.3},
                    "4": {"success": 0.4},
                },
            },
            1: {
                "rvt_swarm": {
                    "2": {"success": 0.7},
                    "4": {"success": 0.8},
                },
                "orca": {
                    "2": {"success": 0.2},
                    "4": {"success": 0.5},
                },
            },
        }

        report = aggregate_multiseed_by_team_size(
            seed_team_summaries,
            reference="rvt_swarm",
            permutation_draws=200,
            permutation_seed=0,
        )

        self.assertEqual(sorted(report["team_sizes"].keys()), ["2", "4"])
        self.assertAlmostEqual(
            report["team_sizes"]["2"]["methods"]["rvt_swarm"]["metrics"]["success"]["mean"],
            0.60,
        )
        self.assertIn(
            "vs_reference",
            report["team_sizes"]["4"]["methods"]["orca"],
        )


if __name__ == "__main__":
    unittest.main()
