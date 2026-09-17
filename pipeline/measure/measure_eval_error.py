"""
Static evaluation error in cp against Stockfish, for a net: how well the
net guides move selection isn't verified by round-trip/symmetry/
saturation checks (they only verify the engine faithfully reproduces the
net) -- this compares the net itself against a reference ground truth
(Stockfish depth 8, already present in val_final.tsv).

Uses ONE persistent session per engine (not a subprocess per position):
"position fen X" + "eval" for the static evaluation, "go depth N" +
"bestmove" for best-move agreement.

Usage:
  python measure_eval_error.py --val val_final.tsv --n-sample 2000 \
      --engine-a candidate/luna.exe --label-a SelfTrained \
      --engine-b baseline_akimbo_fresh/luna.exe --label-b Akimbo \
      --bestmove-depth 8
"""
import argparse
import random
import statistics
import subprocess


def sample_rows(path, n, seed):
    rows = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                continue
            rows.append(parts)  # fen, eval_cp, bestmove, wdl_mover, depth
    rng = random.Random(seed)
    return rng.sample(rows, min(n, len(rows)))


def query_engine(engine_path, rows, bestmove_depth):
    """One persistent session, but SYNCHRONOUS line by line: write a
    command, read its response, then the next -- don't write every
    command in one shot before reading. With few positions the pipe
    absorbs it all and seems to work (the 20-position test passed); at
    2000 the buffer fills up and blocks: the parent process is stuck
    writing, waiting for the engine to consume, the engine is stuck
    writing to its own stdout waiting for the parent to read -- a
    classic bidirectional pipe deadlock, not a position that crashes
    the engine."""
    proc = subprocess.Popen(
        [engine_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )

    def send(cmd):
        proc.stdin.write(cmd + "\n")
        proc.stdin.flush()

    def read_until(prefix, timeout=30):
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError(f"motore terminato inaspettatamente aspettando '{prefix}'")
            line = line.strip()
            if line.startswith(prefix):
                return line
        raise TimeoutError(f"timeout aspettando '{prefix}'")

    evals, bestmoves = [], []
    for fen, eval_cp, bestmove, wdl_mover, depth in rows:
        send(f"position fen {fen}")
        send("eval")
        evals.append(float(read_until("Evaluation:").split()[1]))
        if bestmove_depth:
            send(f"go depth {bestmove_depth}")
            bestmoves.append(read_until("bestmove").split()[1])

    send("quit")
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    return evals, bestmoves


CLAMP = 2000  # same TARGET_EVAL_CLAMP_CP used to build the training target:
              # ~0.6% of positions have a mate score (+-15000) in the Stockfish
              # reference, which a STATIC eval (no search, can't "see" the
              # mate) can't approach by construction -- not a net inaccuracy,
              # and without the clamp a couple of these cases dominate the RMS.


def ranks(values):
    # Average rank on ties (standard for Spearman): sort, assign
    # positions, then average the ranks for equal values.
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


def report(label, engine_evals, stockfish_evals, engine_bestmoves, stockfish_bestmoves):
    n_clamped = sum(1 for s in stockfish_evals if abs(s) > CLAMP)
    stockfish_c = [max(-CLAMP, min(CLAMP, s)) for s in stockfish_evals]
    engine_c = [max(-CLAMP, min(CLAMP, e)) for e in engine_evals]
    errors = [e - s for e, s in zip(engine_c, stockfish_c)]
    mae = statistics.mean(abs(e) for e in errors)
    rmse = (statistics.mean(e ** 2 for e in errors)) ** 0.5
    std = statistics.pstdev(errors)
    # Spearman over the whole sample, WITHOUT clamping: it's scale/offset-
    # free by construction (depends only on ordering), so mate scores
    # don't need the same special treatment as MAE/RMS -- a genuine mate
    # should end up at the top of the ordering regardless.
    rho = spearman(engine_evals, stockfish_evals)
    print(f"=== {label} (n={len(errors):,}, {n_clamped} posizioni con |riferimento|>{CLAMP} clampate su MAE/RMS) ===")
    print(f"  errore medio assoluto: {mae:.2f} cp")
    print(f"  RMS:                   {rmse:.2f} cp")
    print(f"  deviazione standard:   {std:.2f} cp")
    print(f"  correlazione di rango (Spearman) vs Stockfish: {rho:.4f}")
    if engine_bestmoves and stockfish_bestmoves:
        agree = sum(1 for a, b in zip(engine_bestmoves, stockfish_bestmoves) if a == b)
        print(f"  concordanza mossa migliore: {agree}/{len(engine_bestmoves)} ({agree/len(engine_bestmoves)*100:.1f}%)")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", required=True)
    ap.add_argument("--n-sample", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--engine-a", required=True)
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--engine-b", required=True)
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--bestmove-depth", type=int, default=0,
                     help="0 = salta la concordanza sulla mossa migliore (piu' lento)")
    args = ap.parse_args()

    rows = sample_rows(args.val, args.n_sample, args.seed)
    stockfish_evals = [float(r[1]) for r in rows]
    stockfish_bestmoves = [r[2] for r in rows]

    for engine_path, label in [(args.engine_a, args.label_a), (args.engine_b, args.label_b)]:
        evals, bestmoves = query_engine(engine_path, rows, args.bestmove_depth)
        report(label, evals, stockfish_evals, bestmoves if args.bestmove_depth else None, stockfish_bestmoves)


if __name__ == "__main__":
    main()
