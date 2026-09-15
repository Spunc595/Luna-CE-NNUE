"""
Recomputes the search-based comparison used in RESULTS.md table 2: the
engine's own search (UCI "go nodes N"), not the isolated network. Stockfish
here is a measurement tool only (its eval is pre-recorded in the reference
eval set) -- it never labels training data.

Single-threaded by construction: Threads defaults to 1 and is never
overridden here, so results are reproducible exactly (search-based measures
are only reproducible at 1 thread -- see RESULTS.md 5.3).

Usage:
  python measure_search_vs_stockfish.py --eval-set ../eval_set.epd \
      --engine <path-to-luna.exe> --label gen1_master \
      --nodes 10000 20000 50000 --out ../gen1_master_vs_stockfish.csv
"""
import argparse
import random

import chess
import chess.engine


def sample_rows(path, n, seed):
    rows = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                continue
            rows.append(parts)
    rng = random.Random(seed)
    return rng.sample(rows, min(n, len(rows)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-set", required=True)
    ap.add_argument("--n-sample", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--nodes", type=int, nargs="+", default=[10000, 20000, 50000])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = sample_rows(args.eval_set, args.n_sample, args.seed)

    engine = chess.engine.SimpleEngine.popen_uci(args.engine)
    # Threads intentionally left at its UCI default (1) -- not set here.
    try:
        by_nodes = {}
        for nodes in args.nodes:
            evals = []
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
                evals.append(ev)
            by_nodes[nodes] = evals
            print(f"nodes={nodes}: fatto")
    finally:
        engine.quit()

    with open(args.out, "w", encoding="utf-8") as f:
        header = "fen,stockfish_eval_cp," + ",".join(f"{args.label}_eval_cp_nodes{n}" for n in args.nodes)
        f.write(header + "\n")
        for i, (fen, eval_cp, bestmove, wdl_mover, depth) in enumerate(rows):
            vals = ",".join(str(by_nodes[n][i]) for n in args.nodes)
            f.write(f'"{fen}",{eval_cp},{vals}\n')

    print(f"Scritte {len(rows)} righe in {args.out}")


if __name__ == "__main__":
    main()
