"""
The two numbers the lambda sweep reports for every network, computed from the CSVs the
existing measurement scripts write (no engine here):

  rho    Spearman between Stockfish's recorded eval and the network's STATIC eval on the
         2,000-position sample of RESULTS.md table 1 (measure_static_vs_stockfish.py). All
         2,000 rows, raw values: the same computation that gives 0.7005 for gen3.
  ratio  median static-vs-search gap of the CAPTURE class over the median gap of the QUIET
         class, gap = |sigmoid(K*search) - sigmoid(K*static)| (diagnose_static_search_gap.py,
         classes by Luna's own best move). The same computation that gives 1.385 for gen2 and
         1.362 for gen3 in RESULTS.md 5.12.

Usage:
  python sweep_measure.py --label run_a1 --stockfish-csv a1_vs_stockfish.csv --diag-csv a1_gap.csv
"""
import argparse
import csv
import json

from analyze_gap_tail import load_rows, quantile
from diagnose_static_search_gap import load_k, spearman


def static_rho(path, label):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    sf = [float(r["stockfish_eval_cp"]) for r in rows]
    en = [float(r[f"{label}_eval_cp"]) for r in rows]
    return spearman(sf, en), len(rows)


def capture_quiet_ratio(path):
    K, _ = load_k()
    rows = load_rows(path, K)
    cap = sorted(r["gap"] for r in rows if r["cls"] == "capture")
    qui = sorted(r["gap"] for r in rows if r["cls"] == "quiet")
    return quantile(cap, .5) / quantile(qui, .5), len(cap), len(qui)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="column prefix in the stockfish csv (<label>_eval_cp)")
    ap.add_argument("--stockfish-csv", required=True)
    ap.add_argument("--diag-csv", required=True)
    args = ap.parse_args()
    rho, n = static_rho(args.stockfish_csv, args.label)
    ratio, nc, nq = capture_quiet_ratio(args.diag_csv)
    out = dict(label=args.label, rho=round(rho, 4), n_rho=n, ratio=round(ratio, 4), n_capture=nc, n_quiet=nq)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
