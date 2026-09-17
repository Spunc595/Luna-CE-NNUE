"""
Converts a 5-column TSV (fen, eval_cp, bestmove, wdl_mover, depth) into a
compact binary format, readable without row-by-row parsing: training's
bottleneck isn't the computation, it's the dataloader opening the TSV,
splitting rows, building a chess.Board() and calling active_features()
in pure Python for every single position.

Format: three memory-mappable arrays, same row order as the TSV.
  - <out>.us.npy      (N, 32) int32, indices from the side-to-move's
                        perspective, padded with -1 (the maximum number
                        of pieces on a board is 32, so 32 is an exact
                        cap, not an estimate)
  - <out>.them.npy    (N, 32) int32, indices from the opponent's
                        perspective
  - <out>.targets.npy (N,) float32, same target as dataset.py

Uses the SAME functions as dataset.py/feature_set.py to compute indices
and targets, not a reimplementation — so the equivalence check verifies
a format issue, not two different pieces of logic that happen to agree.

Usage:
  python convert_to_binary.py --in train.tsv --out train_bin
"""
import argparse
import math
import time

import chess
import numpy as np

from feature_set import active_features
from dataset import K, TARGET_EVAL_CLAMP_CP

MAX_ACTIVE = 32  # exact cap: a board never has more than 32 pieces


def row_to_arrays(fen, eval_cp_str, wdl_mover_str, eval_lambda):
    eval_cp = max(-TARGET_EVAL_CLAMP_CP, min(TARGET_EVAL_CLAMP_CP, float(eval_cp_str)))
    eval_wdl_mover = 1.0 / (1.0 + math.exp(-K * eval_cp))
    wdl_mover = float(wdl_mover_str)
    target = eval_lambda * eval_wdl_mover + (1.0 - eval_lambda) * wdl_mover

    board = chess.Board(fen)
    white_idx, black_idx = active_features(board)
    if board.turn == chess.WHITE:
        us_idx, them_idx = white_idx, black_idx
    else:
        us_idx, them_idx = black_idx, white_idx
    return us_idx, them_idx, target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True, help="prefisso di output (senza estensione)")
    ap.add_argument("--eval-lambda", type=float, default=0.7)
    args = ap.parse_args()

    with open(args.inp, "r", errors="ignore") as f:
        n_lines = sum(1 for line in f if line.strip())
    print(f"Righe da convertire: {n_lines:,}")

    us_arr = np.full((n_lines, MAX_ACTIVE), -1, dtype=np.int32)
    them_arr = np.full((n_lines, MAX_ACTIVE), -1, dtype=np.int32)
    targets_arr = np.zeros(n_lines, dtype=np.float32)

    t0 = time.time()
    i = 0
    with open(args.inp, "r", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                continue
            fen, eval_cp_str, bestmove, wdl_mover_str, depth = parts
            us_idx, them_idx, target = row_to_arrays(fen, eval_cp_str, wdl_mover_str, args.eval_lambda)

            n_us = min(len(us_idx), MAX_ACTIVE)
            n_them = min(len(them_idx), MAX_ACTIVE)
            us_arr[i, :n_us] = us_idx[:n_us]
            them_arr[i, :n_them] = them_idx[:n_them]
            targets_arr[i] = target
            i += 1

            if i % 200_000 == 0:
                rate = i / (time.time() - t0)
                print(f"  {i:,}/{n_lines:,}  ({rate:.0f} pos/s)")

    np.save(args.out + ".us.npy", us_arr[:i])
    np.save(args.out + ".them.npy", them_arr[:i])
    np.save(args.out + ".targets.npy", targets_arr[:i])

    dt = time.time() - t0
    print(f"Fatto: {i:,} posizioni convertite in {dt:.1f}s ({i/dt:.0f} pos/s)")
    print(f"Output: {args.out}.us.npy  {args.out}.them.npy  {args.out}.targets.npy")


if __name__ == "__main__":
    main()
