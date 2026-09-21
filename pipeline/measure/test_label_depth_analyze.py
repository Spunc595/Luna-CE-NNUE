"""Tests for label_depth_analyze.py on synthetic search CSVs and for its rank/Spearman helpers."""
import csv
import os
import random
import subprocess
import sys
import tempfile
import unittest

import label_depth_analyze as A

HERE = os.path.dirname(os.path.abspath(__file__))
FENS = ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"]


def write(path, noise_by_budget, n=600, bias20=0.0, mate_rows=0, seed=1):
    rng = random.Random(seed)
    truth = [rng.gauss(0, 150) for _ in range(n)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "fen", "budget", "kind", "score", "depth", "nodes", "bestmove"])
        for i in range(n):
            for b in A.BUDGETS:
                sc = truth[i] + (0.0 if b == 2000000 else rng.gauss(0, noise_by_budget[b]))
                if b == 20000:
                    sc += bias20
                kind = "mate" if i < mate_rows else "cp"
                w.writerow([i, FENS[i % 3], b, kind, int(sc) if kind == "cp" else 3, 7, b, "e2e4"])


def run(path):
    r = subprocess.run([sys.executable, os.path.join(HERE, "label_depth_analyze.py"), "--searches", path],
                       capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0, r.stderr
    return r.stdout


class Helpers(unittest.TestCase):
    def test_spearman_matches_the_diagnostic_implementation(self):
        from diagnose_static_search_gap import spearman as ref
        rng = random.Random(3)
        a = [round(rng.gauss(0, 1), 1) for _ in range(300)]     # rounding creates ties
        b = [x + round(rng.gauss(0, 1), 1) for x in a]
        self.assertAlmostEqual(A.spearman(a, b), ref(a, b), places=10)


class Verdicts(unittest.TestCase):
    def test_not_alive_when_20k_is_already_close(self):
        noise = {20000: 3, 50000: 2, 100000: 1.5, 200000: 1, 400000: 0.7, 1000000: 0.3}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv"); write(p, noise)
            out = run(p)
            self.assertIn("NOT ALIVE", out)

    def test_alive_and_justified_when_100k_halves_the_disagreement(self):
        noise = {20000: 220, 50000: 120, 100000: 60, 200000: 40, 400000: 25, 1000000: 10}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv"); write(p, noise)
            out = run(p)
            self.assertIn("RAISING THE BUDGET IS JUSTIFIED", out)
            self.assertIn("STABLE enough to use", out)

    def test_alive_but_not_justified_when_100k_barely_helps(self):
        noise = {20000: 220, 50000: 215, 100000: 205, 200000: 150, 400000: 100, 1000000: 10}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv"); write(p, noise)
            out = run(p)
            self.assertIn("ALIVE BUT NOT JUSTIFIED", out)

    def test_systematic_bias_of_the_20k_label_is_flagged(self):
        noise = {20000: 40, 50000: 30, 100000: 20, 200000: 15, 400000: 10, 1000000: 5}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv"); write(p, noise, bias20=25.0)
            out = run(p)
            self.assertIn("systematic distortion of the 20k label (CI excludes 0): True", out)
            p2 = os.path.join(d, "s2.csv"); write(p2, noise, bias20=0.0)
            self.assertIn("systematic distortion of the 20k label (CI excludes 0): False", run(p2))

    def test_positions_with_a_mate_score_at_any_budget_are_discarded(self):
        noise = {20000: 100, 50000: 60, 100000: 40, 200000: 30, 400000: 20, 1000000: 10}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv"); write(p, noise, n=600, mate_rows=50)
            out = run(p)
            self.assertIn("valid (no mate score at any budget): 550", out)
            self.assertIn("discarded: 50", out)

    def test_unconverged_reference_is_declared(self):
        noise = {20000: 200, 50000: 150, 100000: 120, 200000: 100, 400000: 90, 1000000: 80}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv"); write(p, noise)
            self.assertIn("NOT converged", run(p))


if __name__ == "__main__":
    unittest.main(verbosity=2)
