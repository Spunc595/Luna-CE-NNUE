"""
Static-vs-search gap diagnostic, per position class.

For every position of the evaluation set, on ONE engine process with ONE
network: `eval` (static, no search) and `go nodes N` (search). The gap
between the two is measured in SIGMOID space, `|sigmoid(K*search) -
sigmoid(K*static)|`, because the training target is a sigmoid-space quantity
(see pipeline/train/dataset.py), so 200 cp near zero is not worth 200 cp near
+1500. Spearman(static, search) is computed within each class on raw values.

Classes: by Luna's own bestmove (capture / promotion / quiet) and by piece
count (<=8, 9-12, 13-20, 21-32), plus their cross product. The Stockfish
columns of the eval set are NOT used: this compares two quantities of the
same engine with the same network.

The decision rule this run is judged against is registered separately, and
was committed before any measurement: results/static_vs_search_gap_decision_rule.md

Identity gate (optional but required for a valid run): with --embedded-engine
pointing to a binary WITHOUT a luna.nnue next to it, `eval` is run on the
first 20 positions with both engines and must differ on all 20, proving the
external network is really the one being loaded.

Usage:
  python diagnose_static_search_gap.py --eval-set ../../results/eval_set.epd \
      --engine <dir-with-luna-and-luna.nnue>/luna --label gen3 \
      --embedded-engine <dir-with-luna-only>/luna \
      --out ../../results/static_vs_search_gap_gen3.csv
"""
import argparse
import csv
import math
import os
import re
import statistics
import subprocess
import sys
import time

import chess

MATE_THRESHOLD = 49000 - 64  # MATE_SCORE - MAX_PLY in search.rs
NNUE_EVAL_CLAMP = 15000      # nnue.rs
MIN_CELL = 100


def load_k():
    """K exactly as defined in pipeline/train/dataset.py (read, not retyped)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train", "dataset.py")
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^K = (.+)$", line.strip())
            if m:
                return eval(m.group(1), {"math": math}), line.strip()
    raise RuntimeError("K not found in dataset.py")


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


class Engine:
    def __init__(self, path):
        self.proc = subprocess.Popen(
            [path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
        )
        self.send("uci")
        self.read_until("uciok")
        self.send("setoption name Threads value 1")

    def send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def read_until(self, prefix, collect=None, timeout=600):
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError(f"engine ended while waiting for '{prefix}'")
            line = line.strip()
            if collect is not None:
                collect.append(line)
            if line.startswith(prefix):
                return line
        raise TimeoutError(f"timeout waiting for '{prefix}'")

    def static_eval(self, fen):
        self.send(f"position fen {fen}")
        self.send("eval")
        return float(self.read_until("Evaluation:").split()[1])

    def search(self, fen, nodes):
        """Returns (score_kind, score, bestmove) from the last info line."""
        self.send(f"position fen {fen}")
        self.send(f"go nodes {nodes}")
        lines = []
        best = self.read_until("bestmove", collect=lines).split()[1]
        kind, score = None, None
        for line in lines:
            if line.startswith("info") and " score " in line:
                p = line.split()
                i = p.index("score")
                kind, score = p[i + 1], int(p[i + 2])
        return kind, score, best

    def quit(self):
        self.send("quit")
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def read_fens(path):
    fens = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 5:
                fens.append(parts[0])
    return fens


def piece_count(fen):
    return sum(1 for c in fen.split(" ")[0] if c.isalpha())


def bucket(n):
    if n <= 8:
        return "<=8"
    if n <= 12:
        return "9-12"
    if n <= 20:
        return "13-20"
    return "21-32"


def move_class(fen, bestmove):
    if len(bestmove) == 5:
        return "promotion"  # promotion with capture counts as promotion
    board = chess.Board(fen)
    return "capture" if board.is_capture(chess.Move.from_uci(bestmove)) else "quiet"


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    r = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3:
        return float("nan")
    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    return cov / (va * vb) ** 0.5 if va > 0 and vb > 0 else float("nan")


def summarize(rows, total_n, total_sq):
    n = len(rows)
    if n == 0:
        return None
    sq = sum(r["gap_sig"] ** 2 for r in rows)
    return {
        "n": n,
        "med_sig": statistics.median(r["gap_sig"] for r in rows),
        "med_cp": statistics.median(r["gap_cp"] for r in rows),
        "rho": spearman([r["static"] for r in rows], [r["search"] for r in rows]),
        "pos_share": n / total_n,
        "err_share": sq / total_sq if total_sq > 0 else float("nan"),
    }


def fmt_row(label, s):
    if s is None:
        return f"  {label:<24}{0:>6}"
    flag = "  UNDER-POWERED (n<100)" if s["n"] < MIN_CELL else ""
    return (f"  {label:<24}{s['n']:>6}{s['med_sig']:>12.4f}{s['med_cp']:>10.1f}"
            f"{s['rho']:>9.4f}{s['pos_share']*100:>8.1f}%{s['err_share']*100:>9.1f}%{flag}")


HEADER = f"  {'class':<24}{'n':>6}{'med|dSig|':>12}{'med|dcp|':>10}{'Spearman':>9}{'pos%':>9}{'err%':>10}"


def report(rows, title):
    total_n = len(rows)
    total_sq = sum(r["gap_sig"] ** 2 for r in rows)
    print(f"\n=== {title} (n={total_n}) ===")
    print(HEADER)
    for cls in ("capture", "promotion", "quiet"):
        print(fmt_row(cls, summarize([r for r in rows if r["cls"] == cls], total_n, total_sq)))
    print("  -- by piece count --")
    for b in ("<=8", "9-12", "13-20", "21-32"):
        print(fmt_row(b, summarize([r for r in rows if r["bucket"] == b], total_n, total_sq)))
    print("  -- move class x piece count --")
    for cls in ("capture", "promotion", "quiet"):
        for b in ("<=8", "9-12", "13-20", "21-32"):
            sub = [r for r in rows if r["cls"] == cls and r["bucket"] == b]
            print(fmt_row(f"{cls} / {b}", summarize(sub, total_n, total_sq)))
    return total_n, total_sq


def decision(rows, label):
    total_n = len(rows)
    total_sq = sum(r["gap_sig"] ** 2 for r in rows)
    cap = summarize([r for r in rows if r["cls"] == "capture"], total_n, total_sq)
    qui = summarize([r for r in rows if r["cls"] == "quiet"], total_n, total_sq)
    a_ratio = cap["med_sig"] / qui["med_sig"] if qui["med_sig"] > 0 else float("inf")
    b_diff = qui["rho"] - cap["rho"]
    c_ratio = cap["err_share"] / cap["pos_share"]
    a, b, c = a_ratio >= 1.5, b_diff >= 0.05, c_ratio >= 1.5
    print(f"\n--- decision rule [{label}] ---")
    print(f"  (a) median gap capture/quiet = {a_ratio:.3f}  (need >= 1.5)  -> {'MET' if a else 'not met'}")
    print(f"  (b) Spearman quiet - capture = {b_diff:+.4f}  (need >= 0.05) -> {'MET' if b else 'not met'}")
    print(f"  (c) capture error share / position share = {cap['err_share']*100:.1f}% / "
          f"{cap['pos_share']*100:.1f}% = {c_ratio:.3f}  (actionable only if >= 1.5) -> {'MET' if c else 'not met'}")
    supported = a and b
    print(f"  hypothesis supported (a and b): {supported};  actionable (a, b and c): {supported and c}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-set", required=True)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--embedded-engine", default=None)
    ap.add_argument("--nodes", type=int, default=20000)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    K, k_line = load_k()
    print(f"K = {K!r}   (from dataset.py: `{k_line}`)")
    fens = read_fens(args.eval_set)
    if args.limit:
        fens = fens[:args.limit]

    if args.embedded_engine:
        ext, emb = Engine(args.engine), Engine(args.embedded_engine)
        same = 0
        for fen in fens[:20]:
            if ext.static_eval(fen) == emb.static_eval(fen):
                same += 1
        ext.quit(); emb.quit()
        print(f"identity gate: {20 - same}/20 positions differ between external and embedded network")
        if same:
            print("GATE FAILED: the external network is not being loaded. Stopping.")
            sys.exit(1)

    eng = Engine(args.engine)
    rows, mates = [], 0
    t0 = time.time()
    for i, fen in enumerate(fens):
        static = eng.static_eval(fen)
        kind, score, best = eng.search(fen, args.nodes)
        if kind != "cp" or abs(score) > MATE_THRESHOLD:
            mates += 1
            continue
        gap_sig = abs(sigmoid(K * score) - sigmoid(K * static))
        rows.append({
            "fen": fen, "static": static, "search": float(score), "bestmove": best,
            "cls": move_class(fen, best), "pieces": piece_count(fen), "bucket": bucket(piece_count(fen)),
            "gap_sig": gap_sig, "gap_cp": abs(score - static),
            "clamped": abs(static) >= NNUE_EVAL_CLAMP or abs(score) >= NNUE_EVAL_CLAMP,
        })
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(fens)} ({time.time()-t0:.0f}s)", flush=True)
    eng.quit()

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fen", "static_cp", "search_cp", "bestmove", "class", "pieces", "gap_sigmoid", "gap_cp", "clamped"])
        for r in rows:
            w.writerow([r["fen"], r["static"], r["search"], r["bestmove"], r["cls"], r["pieces"],
                        f"{r['gap_sig']:.6f}", f"{r['gap_cp']:.1f}", int(r["clamped"])])

    print(f"\nlabel={args.label}  nodes={args.nodes}  positions={len(fens)}  "
          f"discarded (mate score)={mates}  clamped (|value|>={NNUE_EVAL_CLAMP})={sum(r['clamped'] for r in rows)}")
    report(rows, f"{args.label}: all positions")
    decision(rows, f"{args.label}, all positions")
    decision([r for r in rows if not r["clamped"]], f"{args.label}, clamped excluded (sensitivity)")


if __name__ == "__main__":
    main()
