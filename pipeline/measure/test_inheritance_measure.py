"""Tests for inheritance_measure.py on synthetic CSVs. Run: python test_inheritance_measure.py"""
import csv
import os
import random
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
N = 800


def write_csv(path, search):
    # static 0 everywhere, so e = sigmoid(K*search) - 0.5 is a monotone function of `search`
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fen", "static_cp", "search_cp", "bestmove", "class", "pieces", "gap_sigmoid", "gap_cp", "clamped"])
        for i, s in enumerate(search):
            w.writerow([f"fen{i}", 0.0, s, "e2e4", "quiet", 20, 0, 0, 0])


def run(d, students, master, ancestor, unrelated):
    args = [sys.executable, os.path.join(HERE, "inheritance_measure.py"), "--students"]
    args += [f"{k}={os.path.join(d, k)}.csv" for k in students]
    args += ["--master", f"M={os.path.join(d, master)}.csv", "--ancestor", f"G1={os.path.join(d, ancestor)}.csv",
             "--unrelated", f"AK={os.path.join(d, unrelated)}.csv"]
    r = subprocess.run(args, capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0, r.stderr
    return r.stdout


class Inheritance(unittest.TestCase):
    def test_students_that_copy_the_master_are_sustained(self):
        rng = random.Random(1)
        master = [rng.gauss(0, 200) for _ in range(N)]
        with tempfile.TemporaryDirectory() as d:
            write_csv(os.path.join(d, "M.csv"), master)
            for k in ("S1", "S2", "S3"):   # master + a little noise
                write_csv(os.path.join(d, f"{k}.csv"), [m + rng.gauss(0, 40) for m in master])
            for k in ("G1", "AK"):          # independent
                write_csv(os.path.join(d, f"{k}.csv"), [rng.gauss(0, 200) for _ in range(N)])
            out = run(d, ["S1", "S2", "S3"], "M", "G1", "AK")
            self.assertIn("VERDICT: SUSTAINED", out)

    def test_when_every_reference_is_equally_close_it_is_not_sustained(self):
        rng = random.Random(2)
        common = [rng.gauss(0, 200) for _ in range(N)]     # "position difficulty" shared by everyone
        with tempfile.TemporaryDirectory() as d:
            for k in ("S1", "S2", "S3", "M", "G1", "AK"):
                write_csv(os.path.join(d, f"{k}.csv"), [c + rng.gauss(0, 60) for c in common])
            out = run(d, ["S1", "S2", "S3"], "M", "G1", "AK")
            self.assertIn("VERDICT: NOT SUSTAINED", out)

    def test_one_student_failing_is_enough_to_fail(self):
        rng = random.Random(3)
        master = [rng.gauss(0, 200) for _ in range(N)]
        with tempfile.TemporaryDirectory() as d:
            write_csv(os.path.join(d, "M.csv"), master)
            for k in ("S1", "S2"):
                write_csv(os.path.join(d, f"{k}.csv"), [m + rng.gauss(0, 40) for m in master])
            write_csv(os.path.join(d, "S3.csv"), [rng.gauss(0, 200) for _ in range(N)])   # copies nobody
            for k in ("G1", "AK"):
                write_csv(os.path.join(d, f"{k}.csv"), [rng.gauss(0, 200) for _ in range(N)])
            out = run(d, ["S1", "S2", "S3"], "M", "G1", "AK")
            self.assertIn("VERDICT: NOT SUSTAINED", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
