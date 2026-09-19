"""
Tests for export.py's refusal gates. Run from this directory:

  python test_export.py

Each case builds a synthetic checkpoint (a freshly initialised LunaHalfKA
with ONE tensor element pushed out of range), runs export.py as a
subprocess, and checks the exit code and whether the output file exists.
A clean checkpoint must be exported; every other case must be refused with a
non-zero exit code and NO file written.
"""
import os
import subprocess
import sys
import tempfile
import unittest

import torch

from model import LunaHalfKA, QA, QB, QAB

HERE = os.path.dirname(os.path.abspath(__file__))


def make_checkpoint(path, mutate=None):
    torch.manual_seed(0)
    model = LunaHalfKA()
    with torch.no_grad():
        if mutate is not None:
            mutate(model)
    torch.save({"model": model.state_dict()}, path)


def run_export(ckpt, out):
    return subprocess.run(
        [sys.executable, os.path.join(HERE, "export.py"), "--checkpoint", ckpt, "--out", out],
        capture_output=True, text=True, encoding="utf-8", cwd=HERE,
    )


def set_fw(row, col, value):
    def f(m):
        m.feature_weights.weight[row, col] = value
    return f


def set_fb(idx, value):
    def f(m):
        m.feature_bias[idx] = value
    return f


def set_ow(a, b, value):
    def f(m):
        m.output_weights[a, b] = value
    return f


def set_ob(value):
    def f(m):
        m.output_bias[0] = value
    return f


# 32767 / QA(255) = 128.5; 32767 / QB(64) = 512.0; 32767 / QAB(16320) = 2.008
CASES = [
    ("feature_weights positive", set_fw(5, 7, 200.0)),
    ("feature_weights negative", set_fw(9, 1, -200.0)),
    ("feature_weights exactly at the positive limit", set_fw(5, 7, 32767.0 / QA)),
    ("feature_weights exactly at the negative limit", set_fw(5, 7, -32768.0 / QA)),
    ("feature_bias positive", set_fb(3, 200.0)),
    ("feature_bias negative", set_fb(3, -200.0)),
    ("output_weights positive", set_ow(0, 4, 600.0)),
    ("output_weights negative", set_ow(1, 4, -600.0)),
    ("output_bias positive", set_ob(3.0)),
    ("output_bias negative", set_ob(-3.0)),
]


class ExportGate(unittest.TestCase):
    def test_clean_checkpoint_is_exported(self):
        with tempfile.TemporaryDirectory() as d:
            ckpt, out = os.path.join(d, "c.pt"), os.path.join(d, "n.bin")
            make_checkpoint(ckpt)
            r = run_export(ckpt, out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(os.path.exists(out))
            self.assertEqual(os.path.getsize(out), 6_297_664)

    def test_saturating_checkpoints_are_refused_and_write_nothing(self):
        for name, mutate in CASES:
            with self.subTest(name), tempfile.TemporaryDirectory() as d:
                ckpt, out = os.path.join(d, "c.pt"), os.path.join(d, "n.bin")
                make_checkpoint(ckpt, mutate)
                r = run_export(ckpt, out)
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertFalse(os.path.exists(out), "a refused export must not leave a file")
                self.assertIn("EXPORT REFUSED", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
