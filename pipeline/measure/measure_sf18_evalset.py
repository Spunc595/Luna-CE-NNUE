"""
Static-evaluation measurement on the Stockfish 18 depth-12 evaluation set (Kaggle: christofferbrandt/
stockfish-position-evaluations, CC BY-SA 4.0, one CSV: fen, move_1..move_5, evaluation). Written to REPLACE the 2,000-
position / Stockfish depth-8 eval set as the measuring instrument; NOT a training set (~460k positions is 0.05% of a
billion).

Everything here is measurement of Luna's own static `eval` (UCI `eval`, no search) against the CSV's `evaluation`
column, both from the SIDE TO MOVE's point of view. Steps, in the order the script runs them:

  1. load the CSV, drop duplicate FENs, split centipawn rows from mate rows (`M<n>`, excluded from the correlation and
     counted);
  2. VERIFY the point of view instead of trusting the documentation: on positions with a large material imbalance, the
     sign of `evaluation` must agree with which SIDE TO MOVE is ahead in material, for White-to-move AND Black-to-move
     rows alike. If it instead agrees with "White is ahead" the column is White-relative and everything below is wrong;
     the script stops in that case;
  3. evaluate every centipawn position with each engine/network pair given on the command line;
  4. Spearman rho against the CSV (full set), plus, for each subset size in --sizes, the mean and standard deviation of
     rho over random subsets (so the resolution at a given n is MEASURED, not assumed to scale as 1/sqrt(n)), and a
     bootstrap 95% CI of the full-set rho. Positions come from games and puzzles, so consecutive positions are
     correlated: the effective sample is smaller than the row count and the naive 1/sqrt(n) understates the error.

Usage:
  python measure_sf18_evalset.py --csv stockfish_position_evaluations.csv --out-dir OUT \
      --engine raw=PATH_TO_luna_v3.1.6.exe --engine scaled=PATH_TO_luna_v3.1.7.exe \
      --net embedded= --net gen1=../../nets/luna_gen1.nnue --net gen2=... --net gen3=...
  Each (engine, net) pair is run in a private temporary folder (a copy of the executable, plus `luna.nnue` when the net
  is external), so no user folder is touched and no stray `luna.nnue` can leak into another run.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

PIECE_VALUE = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900}


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


def load(path):
    seen, cp_rows, mate_rows, dup = set(), [], [], 0
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fen = r["fen"].strip()
            if fen in seen:
                dup += 1
                continue
            seen.add(fen)
            ev = r["evaluation"].strip()
            if ev.startswith("M") or ev.startswith("-M"):
                mate_rows.append((fen, ev))
            else:
                cp_rows.append((fen, int(float(ev))))
    return cp_rows, mate_rows, dup


def material_for_side_to_move(fen):
    board, stm = fen.split()[0], fen.split()[1]
    w = sum(PIECE_VALUE.get(c.lower(), 0) for c in board if c.isupper())
    b = sum(PIECE_VALUE.get(c, 0) for c in board if c.islower())
    return (w - b) if stm == "w" else (b - w), (w - b)


def check_point_of_view(cp_rows, threshold=400):
    """Returns per side-to-move colour: (n, share whose eval sign agrees with 'side to move is ahead'), and the same for
    'White is ahead'. stm-relative data: ~1.0 for the first, and ~1.0 / ~0.0 for the second on White/Black to move."""
    out = {}
    for colour in ("w", "b"):
        n = agree_stm = agree_white = 0
        for fen, cp in cp_rows:
            if fen.split()[1] != colour or cp == 0:
                continue
            m_stm, m_white = material_for_side_to_move(fen)
            if abs(m_stm) < threshold:
                continue
            n += 1
            agree_stm += (cp > 0) == (m_stm > 0)
            agree_white += (cp > 0) == (m_white > 0)
        out[colour] = dict(n=n, agree_side_to_move_ahead=agree_stm / n if n else float("nan"),
                           agree_white_ahead=agree_white / n if n else float("nan"))
    return out


def run_engine(exe_path, net_path, fens):
    tmp = tempfile.mkdtemp(prefix="luna_sf18_")
    try:
        exe = os.path.join(tmp, os.path.basename(exe_path))
        shutil.copy2(exe_path, exe)
        if net_path:
            shutil.copy2(net_path, os.path.join(tmp, "luna.nnue"))
        p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
                             encoding="utf-8", errors="replace", cwd=tmp)

        def send(s):
            p.stdin.write(s + "\n")

        def read_until(prefix):
            while True:
                line = p.stdout.readline()
                if not line:
                    raise RuntimeError("engine ended early")
                if line.startswith(prefix):
                    return line.strip()

        send("uci")
        read_until("uciok")
        out = []
        for fen in fens:
            send(f"position fen {fen}")
            send("eval")
            out.append(float(read_until("Evaluation:").split()[1]))
        send("quit")
        p.wait(timeout=10)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--engine", action="append", default=[], help="label=path (repeatable)")
    ap.add_argument("--net", action="append", default=[], help="label=path-to-luna.nnue, or label= for the embedded net")
    ap.add_argument("--sizes", default="2000,5000,10000,20000,50000,100000")
    ap.add_argument("--repeats", type=int, default=30, help="random subsets per size")
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--limit", type=int, default=None, help="use only the first N centipawn rows (tests)")
    ap.add_argument("--seed", type=int, default=20260925)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    cp_rows, mate_rows, dup = load(a.csv)
    print(f"rows: {len(cp_rows) + len(mate_rows) + dup:,}; duplicate FENs dropped: {dup:,}; centipawn rows: {len(cp_rows):,}; "
          f"mate rows excluded from the correlation: {len(mate_rows):,}")
    pov = check_point_of_view(cp_rows)
    print("point of view check (|material imbalance| >= 400 cp):")
    for colour, d in pov.items():
        print(f"  {'White' if colour == 'w' else 'Black'} to move: n={d['n']:,}  eval sign agrees with 'side to move is ahead': "
              f"{d['agree_side_to_move_ahead']:.4f}   with 'White is ahead': {d['agree_white_ahead']:.4f}")
    # The test that separates the two conventions is the CONTRAST on Black-to-move rows (side-to-move relative: agrees
    # with "side to move is ahead" and disagrees with "White is ahead"; White-relative: the opposite). A fixed absolute
    # threshold would depend on how well material alone predicts the evaluation, which it does not do perfectly.
    w, b = pov["w"], pov["b"]
    if not (w["n"] > 50 and b["n"] > 50 and w["agree_side_to_move_ahead"] > 0.7
            and b["agree_side_to_move_ahead"] - b["agree_white_ahead"] > 0.4):
        sys.exit("STOP: the evaluation column does not behave as side-to-move relative; nothing was measured")
    if a.limit:
        cp_rows = cp_rows[:a.limit]
    fens = [f for f, _ in cp_rows]
    sf = np.array([c for _, c in cp_rows], dtype=float)
    sizes = [int(s) for s in a.sizes.split(",") if int(s) <= len(fens)] + [len(fens)]
    rng = np.random.default_rng(a.seed)

    engines = dict(kv.split("=", 1) for kv in a.engine)
    nets = dict(kv.split("=", 1) for kv in a.net)
    results = {}
    for elabel, epath in engines.items():
        for nlabel, npath in nets.items():
            key = f"{elabel}/{nlabel}"
            t0 = time.time()
            ev = np.array(run_engine(epath, npath or None, fens))
            rho = spearman(ev, sf)
            np.savetxt(os.path.join(a.out_dir, f"eval_{elabel}_{nlabel}.txt"), ev, fmt="%.0f")
            per_size = {}
            for n in sizes:
                if n == len(fens):
                    per_size[n] = dict(mean=rho, sd=0.0)
                    continue
                vals = [spearman(ev[i], sf[i]) for i in (rng.choice(len(fens), n, replace=False) for _ in range(a.repeats))]
                per_size[n] = dict(mean=float(np.mean(vals)), sd=float(np.std(vals, ddof=1)))
            boots = [spearman(ev[i], sf[i]) for i in (rng.integers(0, len(fens), len(fens)) for _ in range(a.boot))]
            lo, hi = np.percentile(boots, [2.5, 97.5])
            results[key] = dict(rho=rho, ci95=[float(lo), float(hi)], per_size=per_size,
                                engine_sha256=hashlib.sha256(open(epath, "rb").read()).hexdigest(),
                                net_sha256=hashlib.sha256(open(npath, "rb").read()).hexdigest() if npath else "embedded")
            print(f"{key:20s} rho = {rho:.4f}  bootstrap 95% CI [{lo:.4f}, {hi:.4f}]   ({time.time() - t0:.0f}s)")
    print("\nstandard deviation of rho over random subsets, by subset size:")
    for key, r in results.items():
        print("  " + key.ljust(20) + "  ".join(f"n={n}: {d['sd']:.4f}" for n, d in r["per_size"].items()))
    json.dump(dict(n_cp=len(fens), n_mate=len(mate_rows), duplicates=dup, pov=pov, results=results),
              open(os.path.join(a.out_dir, "sf18_measurement.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
