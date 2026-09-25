"""Paired bootstrap on the DIFFERENCE of two Spearman correlations measured on the same evaluation set.
Usage: paired_bootstrap.py CSV evalA.txt evalB.txt [--n 10000]   (eval*.txt = the per-position outputs written by
measure_sf18_evalset.py, in the CSV's centipawn-row order). The same resampled row indices are used for both nets, so the
sampling noise shared by the two measurements cancels; two separate intervals do NOT show that."""
import argparse, sys
import numpy as np
sys.path.insert(0, __file__.rsplit("pipeline", 1)[0] + "pipeline/measure")
from measure_sf18_evalset import load, rank_avg

ap = argparse.ArgumentParser()
ap.add_argument("csv"); ap.add_argument("a"); ap.add_argument("b")
ap.add_argument("--n", type=int, default=10000); ap.add_argument("--seed", type=int, default=1)
x = ap.parse_args()
cp, _, _ = load(x.csv)
sf = np.array([c for _, c in cp], float)
a, b = np.loadtxt(x.a), np.loadtxt(x.b)
assert len(a) == len(b) == len(sf)
def rho(u, v):
    ru, rv = rank_avg(u), rank_avg(v); ru -= ru.mean(); rv -= rv.mean()
    return float((ru * rv).sum() / np.sqrt((ru ** 2).sum() * (rv ** 2).sum()))
d0 = rho(b, sf) - rho(a, sf)
rng = np.random.default_rng(x.seed)
ds = np.empty(x.n)
for i in range(x.n):
    idx = rng.integers(0, len(sf), len(sf))
    ds[i] = rho(b[idx], sf[idx]) - rho(a[idx], sf[idx])
lo, hi = np.percentile(ds, [2.5, 97.5])
print(f"rho(a)={rho(a,sf):.4f} rho(b)={rho(b,sf):.4f} diff(b-a)={d0:+.4f}  paired bootstrap 95% CI of the difference [{lo:+.4f}, {hi:+.4f}]  "
      f"sd={ds.std(ddof=1):.4f}  P(diff<=0)={np.mean(ds<=0):.4f}  ({x.n} resamples)")
