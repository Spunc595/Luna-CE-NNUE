"""
Gate: the MASTER's Spearman for generation 2 —
Luna with the gen1 net loaded, in SEARCH (go nodes N, not static "eval")
against Stockfish, on the same position set as gen0/gen1/akimbo
(val_final.tsv). Measured at three node values: 10,000, 20,000, 50,000.

Stockfish here is only a measurement tool (never enters the training
data) — doesn't touch the TCEC guideline.

Usage:
  python measure_master_spearman.py --val val_final.tsv --n-sample 2000 --seed 7 \
      --engine "<path-to-candidate-engine>/luna.exe" \
      --nodes 10000 20000 50000
"""
import argparse
import random
import statistics

import chess
import chess.engine

CLAMP = 2000


def sample_rows(path, n, seed):
    rows = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                continue
            rows.append(parts)  # fen, eval_cp(stockfish), bestmove, wdl_mover, depth
    rng = random.Random(seed)
    return rng.sample(rows, min(n, len(rows)))


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    r = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg_rank
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    mean_ra, mean_rb = statistics.mean(ra), statistics.mean(rb)
    cov = sum((x - mean_ra) * (y - mean_rb) for x, y in zip(ra, rb))
    var_a = sum((x - mean_ra) ** 2 for x in ra)
    var_b = sum((y - mean_rb) ** 2 for y in rb)
    return cov / (var_a * var_b) ** 0.5 if var_a > 0 and var_b > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", required=True)
    ap.add_argument("--n-sample", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--nodes", type=int, nargs="+", default=[10000, 20000, 50000])
    args = ap.parse_args()

    rows = sample_rows(args.val, args.n_sample, args.seed)
    stockfish_evals = [float(r[1]) for r in rows]
    stockfish_c = [max(-CLAMP, min(CLAMP, s)) for s in stockfish_evals]

    engine = chess.engine.SimpleEngine.popen_uci(args.engine)
    try:
        for nodes in args.nodes:
            engine_evals = []
            for fen, eval_cp, bestmove, wdl_mover, depth in rows:
                board = chess.Board(fen)
                info = engine.analyse(board, chess.engine.Limit(nodes=nodes))
                score = info["score"].pov(board.turn)
                if score.is_mate():
                    ev = 15000 if score.mate() > 0 else -15000
                else:
                    ev = score.score()
                    if ev is None:
                        ev = 0
                engine_evals.append(ev)

            engine_c = [max(-CLAMP, min(CLAMP, e)) for e in engine_evals]
            errors = [e - s for e, s in zip(engine_c, stockfish_c)]
            mae = statistics.mean(abs(e) for e in errors)
            rmse = (statistics.mean(e ** 2 for e in errors)) ** 0.5
            rho = spearman(engine_evals, stockfish_evals)
            print(f"=== nodes={nodes} (n={len(rows):,}) ===")
            print(f"  MAE: {mae:.2f} cp   RMS: {rmse:.2f} cp")
            print(f"  Spearman vs Stockfish: {rho:.4f}")
            print()
    finally:
        engine.quit()


if __name__ == "__main__":
    main()
