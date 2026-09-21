"""Tests for the decision logic of sweep_phase2_report.py (the registered predictions and the gen4 lambda rule)."""
import unittest

import sweep_phase2_report as R


def means(v10, v07, v04, v00):
    return {1.0: v10, 0.7: v07, 0.4: v04, 0.0: v00}


class Predictions(unittest.TestCase):
    def test_a_yes_b_yes(self):
        a, ay, e, by, reading = R.predictions(means(0.60, 0.55, 0.50, 0.45), means(0.40, 0.40, 0.41, 0.40))
        self.assertTrue(ay and by)
        self.assertIn("goes through the label", reading)

    def test_a_yes_b_no_when_akimbo_moves_too(self):
        a, ay, e, by, reading = R.predictions(means(0.60, 0.55, 0.50, 0.45), means(0.40, 0.38, 0.33, 0.30))
        self.assertTrue(ay)
        self.assertFalse(by)
        self.assertIn("not demonstrated", reading)

    def test_a_no_closes_the_line(self):
        a, ay, e, by, reading = R.predictions(means(0.55, 0.55, 0.54, 0.54), means(0.40, 0.40, 0.40, 0.40))
        self.assertFalse(ay)
        self.assertIn("closed", reading)

    def test_a_threshold_is_three_floors(self):
        a, ay, *_ = R.predictions(means(0.5205, 0.5, 0.5, 0.5000), means(0.4, 0.4, 0.4, 0.4))
        self.assertFalse(ay)          # 0.0205 < 0.0210
        a, ay, *_ = R.predictions(means(0.5215, 0.5, 0.5, 0.5000), means(0.4, 0.4, 0.4, 0.4))
        self.assertTrue(ay)           # 0.0215 > 0.0210


class Gen4(unittest.TestCase):
    def test_flat_stays_at_07(self):
        self.assertEqual(R.gen4_lambda(means(0.700, 0.705, 0.701, 0.698))[:2], ("flat", 0.7))

    def test_adopt_only_if_advantage_over_07_exceeds_floor(self):
        self.assertEqual(R.gen4_lambda(means(0.690, 0.700, 0.720, 0.680))[:2], ("adopt", 0.4))
        self.assertEqual(R.gen4_lambda(means(0.690, 0.700, 0.708, 0.660))[:2], ("stay", 0.7))   # best is 0.4 but +0.008 <= 0.0103

    def test_best_is_07_stays(self):
        self.assertEqual(R.gen4_lambda(means(0.680, 0.720, 0.700, 0.660))[:2], ("stay", 0.7))


if __name__ == "__main__":
    unittest.main(verbosity=2)
