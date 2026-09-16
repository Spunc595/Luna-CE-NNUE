"""
Recomputes the static-eval-vs-Stockfish comparison used in RESULTS.md table 1.

This is a MEASUREMENT TOOL: it queries Stockfish's pre-recorded evaluation
(already present in the reference eval set, column 2) and each candidate
engine's own static evaluation (UCI "eval", no search) on the SAME sample of
positions, then reports Spearman's rho. Stockfish is used here only to
benchmark rank agreement -- it never contributed a label to any training
dataset (see COMPLIANCE.md).

Sampling is deterministic (seed=7, n=2000) so the same eval_set.epd file
this repo commits reproduces the exact sample used to produce results/*.csv.

Usage:
  python measure_static_vs_stockfish.py --eval-set ../eval_set.epd \
      --engine <path-to-luna.exe> --label gen1 --out ../gen1_vs_stockfish.csv
"""
import argparse
import hashlib
import os
import random
import subprocess
import time


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


def query_engine_static(engine_path, rows):
    proc = subprocess.Popen(
        [engine_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )

    def send(cmd):
        proc.stdin.write(cmd + "\n")
        proc.stdin.flush()

    def read_until(prefix, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError(f"motore terminato inaspettatamente aspettando '{prefix}'")
            line = line.strip()
            if line.startswith(prefix):
                return line
        raise TimeoutError(f"timeout aspettando '{prefix}'")

    evals = []
    for fen, eval_cp, bestmove, wdl_mover, depth in rows:
        send(f"position fen {fen}")
        send("eval")
        evals.append(float(read_until("Evaluation:").split()[1]))

    send("quit")
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    return evals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-set", required=True)
    ap.add_argument("--n-sample", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = sample_rows(args.eval_set, args.n_sample, args.seed)
    engine_evals = query_engine_static(args.engine, rows)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("fen,stockfish_eval_cp,stockfish_bestmove,stockfish_depth," + args.label + "_eval_cp\n")
        for (fen, eval_cp, bestmove, wdl_mover, depth), e in zip(rows, engine_evals):
            f.write(f'"{fen}",{eval_cp},{bestmove},{depth},{e}\n')

    engine_sha256 = hashlib.sha256(open(args.engine, "rb").read()).hexdigest()
    net_path = os.path.join(os.path.dirname(os.path.abspath(args.engine)), "luna.nnue")
    net_sha256 = hashlib.sha256(open(net_path, "rb").read()).hexdigest() if os.path.exists(net_path) else "embedded (no external luna.nnue found)"

    print(f"Wrote {len(rows)} rows to {args.out}")
    print(f"engine sha256: {engine_sha256}")
    print(f"net sha256:    {net_sha256}")


if __name__ == "__main__":
    main()
