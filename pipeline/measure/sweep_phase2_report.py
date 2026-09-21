"""
Phase 2 report of the lambda sweep, computed exactly as registered in results/lambda_sweep_decision_rule.md
(Amendment 1 and its operational definitions). No engine here: it reads the CSVs the existing measurement
scripts write.

Per network: static rho vs Stockfish, rho(e_S, e_gen2), rho(e_S, e_gen1), rho(e_S, e_akimbo) (Spearman of the
signed static-error vectors of 5.15), epoch and value of the minimum validation loss and epochs run.
Per lambda, the value of a point is the MEAN OF ITS TWO SEEDS. Then:

  Prediction A: mean rho(e_S, e_gen2)[lambda 1.0] - mean rho(e_S, e_gen2)[lambda 0.0] > 3 * 0.0070   (strict)
  Prediction B: max - min over the four lambdas of mean rho(e_S, e_akimbo)          < 3 * 0.0070   (strict)
  Reading of the combination (A yes/B yes, A yes/B no, A no), and the lambda of generation 4 by static rho:
  flat (max - min of the four means <= 0.0103) -> stay at 0.7; otherwise the best lambda is adopted only if its
  mean exceeds the mean at 0.7 by more than 0.0103.

Input: a JSON list of runs, each {name, lambda, seed, gap_csv, stockfish_csv, train_log, sha256, gate}, and the
gap CSVs of the three references.

  python sweep_phase2_report.py --runs runs.json --gen2 gen2_gap.csv --gen1 gen1_gap.csv --akimbo akimbo_gap.csv
"""
import argparse
import csv
import json
import statistics

from diagnose_static_search_gap import load_k
from inheritance_measure import correlate, load_errors
from sweep_measure import static_rho

FLOOR_STATIC = 0.0103      # Phase 1, static rho
FLOOR_INHERIT = 0.0070     # 5.15, rho(., gen2)
LAMBDAS = (1.0, 0.7, 0.4, 0.0)


def val_min(train_log):
    with open(train_log, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    best = min(rows, key=lambda r: float(r["val_loss"]))
    return int(best["epoch"]), float(best["val_loss"]), len(rows)


def mean_by_lambda(per_run, key):
    out = {}
    for lam in LAMBDAS:
        vals = [r[key] for r in per_run if r["lambda"] == lam]
        out[lam] = (statistics.mean(vals), len(vals))
    return out


def predictions(m_gen2, m_akimbo):
    a_diff = m_gen2[1.0] - m_gen2[0.0]
    a_yes = a_diff > 3 * FLOOR_INHERIT
    b_exc = max(m_akimbo.values()) - min(m_akimbo.values())
    b_yes = b_exc < 3 * FLOOR_INHERIT
    if a_yes and b_yes:
        reading = "A yes, B yes -> the inheritance goes through the label"
    elif a_yes and not b_yes:
        reading = "A yes, B no -> lower lambda makes the network noisier and less in agreement with everybody: not demonstrated"
    else:
        reading = "A no -> the weight of the label does not govern the agreement with the master: the inheritance line is closed"
    return a_diff, a_yes, b_exc, b_yes, reading


def gen4_lambda(m_rho):
    spread = max(m_rho.values()) - min(m_rho.values())
    if spread <= FLOOR_STATIC:
        return "flat", 0.7, spread
    best = max(m_rho, key=lambda k: m_rho[k])
    if best != 0.7 and m_rho[best] - m_rho[0.7] > FLOOR_STATIC:
        return "adopt", best, spread
    return "stay", 0.7, spread


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--gen2", required=True)
    ap.add_argument("--gen1", required=True)
    ap.add_argument("--akimbo", required=True)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    K, _ = load_k()
    ref = {"gen2": load_errors(args.gen2, K), "gen1": load_errors(args.gen1, K), "akimbo": load_errors(args.akimbo, K)}
    runs = json.load(open(args.runs, encoding="utf-8"))
    per_run = []
    for r in runs:
        e = load_errors(r["gap_csv"], K)
        row = dict(name=r["name"], **{"lambda": float(r["lambda"])}, seed=r["seed"], sha256=r["sha256"], gate=r["gate"])
        row["rho_static"], _ = static_rho(r["stockfish_csv"], r["name"])
        for k in ("gen2", "gen1", "akimbo"):
            c = correlate(e, ref[k])
            row["rho_" + k], row["n_" + k] = c["spearman"], c["n"]
        row["min_epoch"], row["min_val"], row["epochs"] = val_min(r["train_log"])
        per_run.append(row)

    print(f"{'run':<10}{'lambda':>7}{'seed':>6}{'static':>8}{'gen2':>8}{'gen1':>8}{'akimbo':>8}  min val (epoch)  epochs  gate  sha256")
    for r in sorted(per_run, key=lambda x: (-x["lambda"], x["seed"])):
        print(f"{r['name']:<10}{r['lambda']:>7.1f}{r['seed']:>6}{r['rho_static']:>8.4f}{r['rho_gen2']:>8.4f}"
              f"{r['rho_gen1']:>8.4f}{r['rho_akimbo']:>8.4f}  {r['min_val']:.6f} ({r['min_epoch']:>2})  {r['epochs']:>4}   {r['gate']}  {r['sha256']}")
    m = {k: mean_by_lambda(per_run, k) for k in ("rho_static", "rho_gen2", "rho_gen1", "rho_akimbo")}
    print("\nper-lambda means (two seeds each; the point 0.7 is A1 and B):")
    for lam in LAMBDAS:
        print(f"  lambda {lam:.1f}  n={m['rho_gen2'][lam][1]}  static {m['rho_static'][lam][0]:.4f}  gen2 {m['rho_gen2'][lam][0]:.4f}  "
              f"gen1 {m['rho_gen1'][lam][0]:.4f}  akimbo {m['rho_akimbo'][lam][0]:.4f}")
    g2 = {lam: v[0] for lam, v in m["rho_gen2"].items()}
    ak = {lam: v[0] for lam, v in m["rho_akimbo"].items()}
    st = {lam: v[0] for lam, v in m["rho_static"].items()}
    a_diff, a_yes, b_exc, b_yes, reading = predictions(g2, ak)
    mono = all(g2[a] >= g2[b] for a, b in zip((1.0, 0.7, 0.4), (0.7, 0.4, 0.0)))
    print(f"\nPREDICTION A: rho(e,gen2)[1.0] - [0.0] = {a_diff:+.4f} vs 3*floor = {3 * FLOOR_INHERIT:.4f}: {'MET' if a_yes else 'NOT MET'} "
          f"(monotone over the four points, reported only: {mono})")
    print(f"PREDICTION B: excursion of rho(e,akimbo) over the four lambdas = {b_exc:.4f} vs {3 * FLOOR_INHERIT:.4f}: {'MET' if b_yes else 'NOT MET'}")
    print(f"COMBINATION: {reading}")
    kind, lam4, spread = gen4_lambda(st)
    print(f"GEN4 LAMBDA (static rho): spread of the four means {spread:.4f} vs floor {FLOOR_STATIC}: {kind} -> lambda {lam4}")
    if args.json_out:
        json.dump(dict(runs=per_run, means={k: {str(l): v[0] for l, v in d.items()} for k, d in m.items()},
                       prediction_A=dict(diff=a_diff, met=a_yes), prediction_B=dict(excursion=b_exc, met=b_yes),
                       reading=reading, gen4=dict(kind=kind, lambda_=lam4, spread=spread)),
                  open(args.json_out, "w"), indent=1)


if __name__ == "__main__":
    main()
