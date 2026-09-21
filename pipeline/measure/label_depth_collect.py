"""
Collects the searches of the label-depth measurement (results/label_depth_decision_rule.md, registered before this
script was run): for every position of the evaluation set and every node budget, one `go nodes N` with the network of
the engine directory, 1 thread, the transposition table cleared (`ucinewgame`) before each search so that every budget
is independent and deterministic. Only the FEN column of the eval set is used. Luna against Luna: no Stockfish here.

Output (long CSV): index, fen, budget, kind (cp/mate), score, depth, nodes, bestmove. Score from the side to move's
point of view, as the engine prints it. The parent process merges the per-worker files.

The identity gate of the diagnostic runs first: with --embedded-engine (the same binary without a luna.nnue next to it)
the first 20 positions must give a different `eval` on all 20, or nothing is collected.

Usage:
  python label_depth_collect.py --eval-set results/eval_set.epd --engine DIR/luna --embedded-engine EMB/luna \
      --out label_depth_searches.csv [--workers 4] [--limit N]
"""
import argparse
import csv
import multiprocessing as mp
import os
import subprocess
import sys

BUDGETS = (20000, 50000, 100000, 200000, 400000, 1000000, 2000000)


class Engine:
    def __init__(self, path, hash_mb=256):
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1, encoding="utf-8", errors="replace")
        self.send("uci")
        self.until(lambda l: l == "uciok")
        self.send("setoption name Threads value 1")
        self.send(f"setoption name Hash value {hash_mb}")
        self.ready()

    def send(self, s):
        self.p.stdin.write(s + "\n")
        self.p.stdin.flush()

    def until(self, pred):
        lines = []
        while True:
            l = self.p.stdout.readline()
            if not l:
                raise RuntimeError("engine ended; last lines: " + " | ".join(lines[-3:]))
            l = l.strip()
            lines.append(l)
            if pred(l):
                return lines

    def ready(self):
        self.send("isready")
        self.until(lambda l: l == "readyok")

    def static_eval(self, fen):
        self.send(f"position fen {fen}")
        self.send("eval")
        return float(self.until(lambda l: l.startswith("Evaluation:"))[-1].split()[1])

    def search(self, fen, nodes):
        self.send("ucinewgame")
        self.ready()
        self.send(f"position fen {fen}")
        self.send(f"go nodes {nodes}")
        lines = self.until(lambda l: l.startswith("bestmove"))
        best = lines[-1].split()[1]
        kind = score = depth = n = None
        for l in lines:
            if l.startswith("info depth"):
                t = l.split()
                depth = int(t[t.index("depth") + 1])
                i = t.index("score")
                kind, score = t[i + 1], int(t[i + 2])
                n = int(t[t.index("nodes") + 1])
        return kind, score, depth, n, best

    def quit(self):
        try:
            self.send("quit")
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


def read_fens(path):
    fens = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 5:
                fens.append(parts[0])
    return fens


def worker(args):
    w, n_workers, engine_path, fens, part_path = args
    e = Engine(engine_path)
    with open(part_path, "w", newline="\n", encoding="utf-8") as f:
        wr = csv.writer(f)
        for i in range(w, len(fens), n_workers):
            for b in BUDGETS:
                kind, score, depth, n, best = e.search(fens[i], b)
                wr.writerow([i, fens[i], b, kind, score, depth, n, best])
            f.flush()
    e.quit()
    return part_path


def identity_gate(engine_path, embedded_path, fens):
    a, b = Engine(engine_path), Engine(embedded_path)
    gate = fens[:20]
    same = sum(1 for fen in gate if a.static_eval(fen) == b.static_eval(fen))
    a.quit()
    b.quit()
    return len(gate) - same, len(gate)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-set", required=True)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--embedded-engine", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None, help="only the first N positions (tests)")
    args = ap.parse_args()

    fens = read_fens(args.eval_set)
    if args.limit:
        fens = fens[:args.limit]
    differ, n_gate = identity_gate(args.engine, args.embedded_engine, fens)
    print(f"identity gate: {differ}/{n_gate} positions differ between external and embedded network", flush=True)
    if differ != n_gate:
        sys.exit("identity gate failed: the external network is not the one loaded; nothing collected")

    parts = [f"{args.out}.part{w}" for w in range(args.workers)]
    with mp.Pool(args.workers) as pool:
        pool.map(worker, [(w, args.workers, args.engine, fens, parts[w]) for w in range(args.workers)])
    rows = []
    for p in parts:
        with open(p, newline="", encoding="utf-8") as f:
            rows.extend(csv.reader(f))
    rows.sort(key=lambda r: (int(r[0]), int(r[2])))
    with open(args.out, "w", newline="\n", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "fen", "budget", "kind", "score", "depth", "nodes", "bestmove"])
        w.writerows(rows)
    print(f"{len(rows)} searches -> {args.out}")


if __name__ == "__main__":
    main()
