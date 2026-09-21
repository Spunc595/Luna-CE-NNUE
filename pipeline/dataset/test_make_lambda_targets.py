"""make_lambda_targets.py must give exactly the targets convert_to_binary.py would. Run with
PYTHONPATH=../train python test_make_lambda_targets.py"""
import os
import random
import subprocess
import sys
import tempfile
import unittest

import numpy as np

import convert_to_binary as C

HERE = os.path.dirname(os.path.abspath(__file__))
FENS = ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"]


class Targets(unittest.TestCase):
    def test_same_targets_as_convert_to_binary_for_every_lambda(self):
        rng = random.Random(5)
        rows = [(rng.choice(FENS), str(rng.choice([-15000, -2500, -300, -1, 0, 7, 340, 2100, 15000])),
                 "e2e4", rng.choice(["0", "0.5", "1"]), "20000") for _ in range(400)]
        with tempfile.TemporaryDirectory() as d:
            tsv = os.path.join(d, "x.tsv")
            with open(tsv, "w", newline="\n") as f:
                for r in rows:
                    f.write("\t".join(r) + "\n")
            for lam in (1.0, 0.7, 0.4, 0.0):
                out = os.path.join(d, f"t_{lam}.npy")
                subprocess.run([sys.executable, os.path.join(HERE, "make_lambda_targets.py"), "--in", tsv,
                                "--out", out, "--eval-lambda", str(lam)], check=True, capture_output=True, cwd=HERE)
                got = np.load(out)
                want = np.array([C.row_to_arrays(r[0], r[1], r[3], lam)[2] for r in rows], dtype=np.float32)
                self.assertTrue(np.array_equal(got, want), f"lambda {lam}")
                self.assertEqual(got.dtype, np.float32)

    def test_lambda_is_required(self):
        r = subprocess.run([sys.executable, os.path.join(HERE, "make_lambda_targets.py"), "--in", "x", "--out", "y"],
                           capture_output=True, text=True, cwd=HERE)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
