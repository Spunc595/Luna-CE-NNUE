"""
Rebuilds ONLY the targets file of a binary dataset for a given lambda, from the same 5-column TSV the
binary was converted from. Why it exists: convert_to_binary.py bakes `lambda*sigmoid(K*eval) + (1-lambda)*WDL`
into <prefix>.targets.npy (default lambda 0.7), and train.py with --format binary reads those targets: its
--eval-lambda has NO effect on a binary dataset. To train at another lambda the targets must be rebuilt; the
feature arrays (.us.npy / .them.npy) do not depend on lambda and are shared.

The computation is row for row the one of convert_to_binary.row_to_arrays (same K, same clamp, double math,
cast to float32), and the file is written with np.save exactly as there, so that at lambda 0.7 the output is
byte-identical to the published <prefix>.targets.npy (checked in checksums/gen3/dataset.txt).

Usage (PYTHONPATH must contain pipeline/train, for K and the clamp):
  python make_lambda_targets.py --in gen3_train.tsv --out lam_0.4/gen3_train_bin.targets.npy --eval-lambda 0.4
"""
import argparse
import math

import numpy as np

from dataset import K, TARGET_EVAL_CLAMP_CP


def target_of(eval_cp_str, wdl_mover_str, eval_lambda):
    eval_cp = max(-TARGET_EVAL_CLAMP_CP, min(TARGET_EVAL_CLAMP_CP, float(eval_cp_str)))
    eval_wdl_mover = 1.0 / (1.0 + math.exp(-K * eval_cp))
    wdl_mover = float(wdl_mover_str)
    return eval_lambda * eval_wdl_mover + (1.0 - eval_lambda) * wdl_mover


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True, help="path of the .targets.npy to write")
    ap.add_argument("--eval-lambda", type=float, required=True,
                    help="no default on purpose: it changes the output")
    args = ap.parse_args()

    with open(args.inp, "r", errors="ignore") as f:
        n_lines = sum(1 for line in f if line.strip())
    targets = np.zeros(n_lines, dtype=np.float32)
    i = 0
    with open(args.inp, "r", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                continue
            _fen, eval_cp_str, _bestmove, wdl_mover_str, _depth = parts
            targets[i] = target_of(eval_cp_str, wdl_mover_str, args.eval_lambda)
            i += 1
    np.save(args.out, targets[:i])
    print(f"lambda {args.eval_lambda}: {i:,} targets -> {args.out}")


if __name__ == "__main__":
    main()
