"""
Analysis of the label-depth measurement, exactly as registered in results/label_depth_decision_rule.md. No engine here:
it reads the CSV of label_depth_collect.py.

Label at budget N: sigmoid(K * clamp(score, +/-2000)), score from the side to move's point of view, K = ln(10)/400 read
from pipeline/train/dataset.py. Valid positions: one COMMON set, those with no mate score at any budget.

Order of the output (as registered): the reference check rho(1M, 2M) first; 3a rho(n, 2M) and the median |label(n) -
label(2M)| for every budget; 3b the signed mean difference with a bootstrap 95% CI (10,000 resamples, seed 20260921);
3c the stratification of |label(20k) - label(2M)| by the class of the 2M best move and by piece count (n < 100 cells
flagged under-powered); then the verdict, mechanically.

Usage:
  python label_depth_analyze.py --searches label_depth_searches.csv --json-out label_depth_result.json
"""
import argparse
import csv
import json
import math
import statistics

import chess
import numpy as np

from diagnose_static_search_gap import load_k

BUDGETS = (20000, 50000, 100000, 200000, 400000, 1000000, 2000000)
CLAMP = 2000
SEED = 20260921
N_BOOT = 10000
N_BOOT_RHO = 1000
REF_OK = 0.99
ALIVE = 0.05


def rank_avg(x):
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    first = np.r_[True, xs[1:] != xs[:-1]]
    grp = np.cumsum(first) - 1
    starts = np.flatnonzero(first)
    ends = np.r_[starts[1:], len(xs)]
    avg = (starts + ends - 1) / 2.0 + 1.0
    r = np.empty(len(x))
    r[order] = avg[grp]
    return r


def spearman(a, b):
    ra, rb = rank_avg(a), rank_avg(b)
    ra -= ra.mean()
    rb -= rb.mean()
    den = math.sqrt(float((ra ** 2).sum() * (rb ** 2).sum()))
    return float((ra * rb).sum() / den) if den > 0 else float("nan")


def load(path, K):
    """Returns fens, per-budget arrays of labels, mate flags, 2M best moves, depths; and the discard statistics."""
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.setdefault(int(r["index"]), {})[int(r["budget"])] = r
    idx = sorted(i for i in rows if all(b in rows[i] for b in BUDGETS))
    mate_per_budget = {b: sum(1 for i in idx if rows[i][b]["kind"] == "mate") for b in BUDGETS}
    valid = [i for i in idx if all(rows[i][b]["kind"] == "cp" for b in BUDGETS)]
    clamped = sum(1 for i in valid if any(abs(int(rows[i][b]["score"])) > CLAMP for b in BUDGETS))
    labels, depths = {}, {}
    for b in BUDGETS:
        cp = np.array([max(-CLAMP, min(CLAMP, int(rows[i][b]["score"]))) for i in valid], dtype=float)
        labels[b] = 1.0 / (1.0 + np.exp(-K * cp))
        depths[b] = np.array([int(rows[i][b]["depth"]) for i in valid])
    fens = [rows[i][BUDGETS[0]]["fen"] for i in valid]
    best2m = [rows[i][BUDGETS[-1]]["bestmove"] for i in valid]
    return fens, labels, depths, best2m, dict(n_positions=len(idx), n_valid=len(valid), n_discarded=len(idx) - len(valid),
                                              mate_per_budget=mate_per_budget, positions_with_clamp=clamped)


def boot_mean_ci(d, rng):
    n = len(d)
    means = np.array([d[rng.integers(0, n, n)].mean() for _ in range(N_BOOT)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def boot_one_minus_rho(a, b, rng):
    n = len(a)
    vals = []
    for _ in range(N_BOOT_RHO):
        ix = rng.integers(0, n, n)
        vals.append(1.0 - spearman(a[ix], b[ix]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def move_class(fen, bestmove):
    if len(bestmove) == 5:
        return "promotion"
    return "capture" if chess.Board(fen).is_capture(chess.Move.from_uci(bestmove)) else "quiet"


def bucket(fen):
    n = sum(1 for c in fen.split(" ")[0] if c.isalpha())
    return "<=8" if n <= 8 else "9-12" if n <= 12 else "13-20" if n <= 20 else "21-32"


def decide(rho_1m_2m, rho20, rho100, ci_bias20):
    reference_ok = rho_1m_2m > REF_OK
    alive = (1.0 - rho20) >= ALIVE
    gain = (1.0 - rho100) <= 0.5 * (1.0 - rho20)
    justified = alive and gain
    distortion = not (ci_bias20[0] <= 0.0 <= ci_bias20[1])
    if not alive:
        text = "NOT ALIVE: the 20k label is already correlated above 0.95 with the 2M label; depth is not the bottleneck, the line is closed"
    elif justified:
        text = "RAISING THE BUDGET IS JUSTIFIED: 100k removes at least half of the residual disagreement of 20k"
    else:
        text = "ALIVE BUT NOT JUSTIFIED: 100k removes less than half of the disagreement; five times the cost does not buy enough"
    return dict(reference_ok=reference_ok, alive=alive, gain_at_least_half=gain, budget_increase_justified=justified,
                distortion_at_20k=distortion, text=text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--searches", required=True)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    K, _ = load_k()
    fens, labels, depths, best2m, stats = load(args.searches, K)
    ref = labels[2000000]
    rng = np.random.default_rng(SEED)
    out = dict(stats=stats)

    print(f"positions: {stats['n_positions']}; valid (no mate score at any budget): {stats['n_valid']}; "
          f"discarded: {stats['n_discarded']}; mate scores per budget: {stats['mate_per_budget']}; "
          f"valid positions with a clamped score at some budget: {stats['positions_with_clamp']}")
    print("median depth reached per budget: " + ", ".join(f"{b}: {int(np.median(depths[b]))}" for b in BUDGETS))

    rho_1m_2m = spearman(labels[1000000], ref)
    print(f"\nREFERENCE CHECK rho(1M, 2M) = {rho_1m_2m:.4f}  -> the 2M reference is "
          f"{'STABLE enough to use (> 0.99)' if rho_1m_2m > REF_OK else 'NOT converged (<= 0.99): everything below carries this limit'}")
    out["rho_1m_2m"] = rho_1m_2m

    print("\n3a  budget    rho(n,2M)   1-rho   1-rho 95% CI (bootstrap, info)   median|d|   depth median")
    rho, curve = {}, {}
    for b in BUDGETS[:-1]:
        rho[b] = spearman(labels[b], ref)
        lo, hi = boot_one_minus_rho(labels[b], ref, rng)
        med = float(np.median(np.abs(labels[b] - ref)))
        curve[b] = dict(rho=rho[b], one_minus_rho=1 - rho[b], ci=[lo, hi], median_abs_diff=med)
        print(f"    {b:>9}   {rho[b]:.4f}     {1 - rho[b]:.4f}   [{lo:.4f}, {hi:.4f}]                  {med:.4f}      {int(np.median(depths[b]))}")
    out["curve"] = curve

    print("\n3b  budget    signed mean of label(n) - label(2M)   95% CI (bootstrap 10,000)   excludes 0")
    bias = {}
    for b in BUDGETS[:-1]:
        d = labels[b] - ref
        lo, hi = boot_mean_ci(d, rng)
        bias[b] = dict(mean=float(d.mean()), ci=[lo, hi], excludes_zero=not (lo <= 0 <= hi))
        print(f"    {b:>9}   {d.mean():+.5f}                            [{lo:+.5f}, {hi:+.5f}]        {bias[b]['excludes_zero']}")
    print("    (label from the side to move's point of view: a positive mean = the shorter search OVERRATES the side to move)")
    out["bias"] = bias

    print("\n3c  |label(20k) - label(2M)|, class by the 2M best move / piece count")
    d20 = np.abs(labels[20000] - ref)
    classes = np.array([move_class(f, m) for f, m in zip(fens, best2m)])
    bkt = np.array([bucket(f) for f in fens])
    strat = {}
    for name, arr, keys in (("class", classes, ("capture", "quiet", "promotion")), ("pieces", bkt, ("<=8", "9-12", "13-20", "21-32"))):
        for k in keys:
            m = arr == k
            n = int(m.sum())
            cell = dict(n=n, median=float(np.median(d20[m])) if n else None, mean=float(d20[m].mean()) if n else None,
                        underpowered=n < 100)
            strat[f"{name}:{k}"] = cell
            flag = "  UNDER-POWERED (n<100)" if n < 100 else ""
            med = f"{cell['median']:.4f}" if n else "  n/a "
            mean = f"{cell['mean']:.4f}" if n else "  n/a "
            print(f"    {name}:{k:<10} n={n:>5}   median {med}   mean {mean}{flag}")
    out["stratification"] = strat

    v = decide(rho_1m_2m, rho[20000], rho[100000], bias[20000]["ci"])
    print("\nVERDICT (mechanical, as registered):")
    print(f"  reference stable (rho(1M,2M) > 0.99): {v['reference_ok']}")
    print(f"  alive, 1 - rho(20k,2M) = {1 - rho[20000]:.4f} >= 0.05: {v['alive']}")
    print(f"  1 - rho(100k,2M) = {1 - rho[100000]:.4f} <= 0.5 * {1 - rho[20000]:.4f} = {0.5 * (1 - rho[20000]):.4f}: {v['gain_at_least_half']}")
    print(f"  systematic distortion of the 20k label (CI excludes 0): {v['distortion_at_20k']}")
    print(f"  -> {v['text']}")
    out["verdict"] = v
    if args.json_out:
        json.dump(out, open(args.json_out, "w"), indent=1, default=lambda x: x if not isinstance(x, np.generic) else x.item())


if __name__ == "__main__":
    main()
