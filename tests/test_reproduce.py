"""The reproduction registry (scripts/paper.yaml) stays consistent with the CLI and the figure configs."""
import os
import unittest

import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import reproduce as R  # noqa: E402  (scripts/reproduce.py)


class ReproduceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.reg, self.named, self.benches = R.load()

    def test_every_arm_has_runs_and_commands(self):
        for arm, a in self.reg["arms"].items():
            self.assertIn(a["config"], self.reg["configs"], arm)
            runs = R.arm_runs(self.reg, self.named, arm)
            self.assertTrue(runs, f"{arm}: the paper reads no runs of it")
            for bench, dirs in runs.items():
                if bench not in self.benches:
                    continue
                for d in dirs:
                    cmds = R.run_cmds(self.reg, self.benches, arm, bench, R.raw_dir(bench, d), "x")
                    self.assertTrue(any(f"--out {R.raw_dir(bench, d)}" in c for c in cmds), (arm, bench, cmds))
                    self.assertNotIn("{", " ".join(cmds), (arm, bench))      # every placeholder filled

    def test_adapters_and_pools(self):
        for name, a in self.reg["adapters"].items():
            self.assertTrue(a.get("pool") or a.get("rows_dir"), name)
            if a.get("pool"):
                self.assertTrue(os.path.exists(os.path.join(R.ROOT, a["pool"])), a["pool"])
        n = sum(1 for _ in open(os.path.join(R.ROOT, "scripts/pools/pool3k_plain_ids.txt")))
        self.assertEqual(n, 3128)                                           # the paper's generated trajectories

    def test_figure_generators_exist(self):
        for f in self.reg["figures"]:
            script = f["cmd"].split()[0]
            self.assertTrue(os.path.exists(os.path.join(R.ROOT, script)), script)

    def test_rq1_agents_match_the_figure_config(self):
        cfg = yaml.safe_load(open(os.path.join(R.ROOT, "docs/figures/rq1/rq1_config.yaml")))
        judged = {os.path.basename(os.path.dirname(m["judge"])) for m in cfg["models"]}
        listed = {m["run"] for g in ("browser_use", "own_loop") for m in self.reg["rq1"][g]}
        self.assertEqual(judged, listed)


if __name__ == "__main__":
    unittest.main()
