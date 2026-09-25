"""Round-trip test for the bullet -> Luna conversion: an independent reference (bullet's Chess768hm definition) and Luna's
own `eval` must agree EXACTLY on a seeded random network and seeded random positions. A second test proves the check has
teeth: with the mirror permutation deliberately removed, the same round-trip must FAIL.

  LUNA_EXE=path/to/luna.exe python test_mirror.py        (needs python-chess, numpy)
The engine must carry the plain `eval` UCI command and its luna.nnue loader (v3.1.x).
"""
import os
import random
import tempfile
import unittest

import chess
import numpy as np

import bullet_luna as bl

EXE = os.environ.get("LUNA_EXE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                                 "rust-chess", "target", "release", "luna.exe")


def positions(n, seed=7):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        b = chess.Board()
        for _ in range(rng.randint(6, 90)):
            m = list(b.legal_moves)
            if not m:
                break
            b.push(rng.choice(m))
        if not b.is_game_over() and not b.is_check():
            out.append(b.fen())
    return out


def random_raw(seed=3):
    r = np.random.default_rng(seed)
    raw = np.zeros(bl.RAW_FLOATS, dtype="<f4")
    raw[:768 * 1024] = r.uniform(-0.25, 0.25, 768 * 1024)
    raw[768 * 1024:769 * 1024] = r.uniform(-0.2, 0.2, 1024)
    raw[769 * 1024:771 * 1024] = r.uniform(-1.0, 1.0, 2048)
    raw[-1] = 0.1
    return raw


@unittest.skipUnless(os.path.exists(EXE), f"no engine at {EXE} (set LUNA_EXE)")
class MirrorRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.fens = random_raw(), positions(300)
        ref = bl.Reference(cls.raw)
        cls.expected = [ref.eval(f) for f in cls.fens]

    def _luna(self, mirror_fix):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "n.nnue")
            with open(p, "wb") as f:
                f.write(bl.convert(self.raw, mirror_fix=mirror_fix))
            return bl.luna_eval(EXE, p, self.fens)

    def test_zero_differences(self):
        got = self._luna(True)
        self.assertEqual([i for i, (a, b) in enumerate(zip(self.expected, got)) if a != b], [])

    def test_check_fails_without_the_mirror_permutation(self):
        got = self._luna(False)
        diffs = sum(a != b for a, b in zip(self.expected, got))
        self.assertGreater(diffs, len(self.fens) // 2, "the round-trip did not notice a wrong mirror direction")



@unittest.skipUnless(os.path.exists(EXE), f"no engine at {EXE} (set LUNA_EXE)")
class VerifiedConverter(unittest.TestCase):
    """The converter itself must refuse to write when the round-trip fails."""

    def test_writes_when_zero_differences(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "n.nnue")
            self.assertEqual(bl.convert_verified(random_raw(), out, EXE, n=100), 100)
            self.assertTrue(os.path.exists(out))

    def test_refuses_and_writes_nothing_when_the_mapping_is_wrong(self):
        real = bl.convert
        bl.convert = lambda raw, mirror_fix=True: real(raw, mirror_fix=False)   # deliberately break the mapping
        try:
            with tempfile.TemporaryDirectory() as d:
                out = os.path.join(d, "n.nnue")
                with self.assertRaises(bl.RoundTripError):
                    bl.convert_verified(random_raw(), out, EXE, n=100)
                self.assertFalse(os.path.exists(out), "a failed round-trip must not leave a file")
        finally:
            bl.convert = real


if __name__ == "__main__":
    unittest.main(verbosity=2)
