"""
Inheritance measure of results/inheritance_measure_decision_rule.md (registered before this script
existed). No engine here: it reads the per-position CSVs written by diagnose_static_search_gap.py.

For a network X, the static error of a position is the SIGNED
    e_X(p) = sigmoid(K*search_X(p)) - sigmoid(K*static_X(p)),   K read from pipeline/train/dataset.py.
The inheritance between a student S and a reference R is Spearman(e_S, e_R) over the positions valid
for both (join by FEN; the diagnostic drops mate scores, so the sets differ slightly). Pearson is
reported as a secondary figure and decides nothing.

Decision (the registered rule, applied mechanically): floor = max - min of rho(S, master) over the
students; the inheritance is sustained only if, for EVERY student, rho(S, master) exceeds both
rho(S, ancestor) and rho(S, unrelated) by MORE than the floor.

Usage:
  python inheritance_measure.py --students A1=A1_gap.csv B=B_gap.csv C=C_gap.csv \
      --master gen2=gen2_gap.csv --ancestor gen1=gen1_gap.csv --unrelated akimbo=akimbo_gap.csv \
      [--extra gen3=gen3_gap.csv] --json-out inheritance_result.json
"""
import argparse
import csv
import json
import math
import statistics

from diagnose_static_search_gap import load_k, sigmoid, spearman


def load_errors(path, K):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    errs = {}
    for r in rows:
        fen = r["fen"]
        assert fen not in errs, f"duplicate FEN in {path}"
        errs[fen] = sigmoid(K * float(r["search_cp"])) - sigmoid(K * float(r["static_cp"]))
    return errs


def pearson(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return cov / math.sqrt(va * vb) if va > 0 and vb > 0 else float("nan")


def correlate(ea, eb):
    common = sorted(set(ea) & set(eb))
    a, b = [ea[f] for f in common], [eb[f] for f in common]
    return dict(n=len(common), spearman=spearman(a, b), pearson=pearson(a, b))


def decide(students, master, ancestor, unrelated, rho):
    """rho[(s, r)] -> spearman. Returns (verdict, floor, per-student margins)."""
    vals = [rho[(s, master)] for s in students]
    floor = max(vals) - min(vals)
    detail = {}
    ok = True
    for s in students:
        m_anc = rho[(s, master)] - rho[(s, ancestor)]
        m_unr = rho[(s, master)] - rho[(s, unrelated)]
        detail[s] = dict(over_ancestor=m_anc, over_unrelated=m_unr,
                         holds=(m_anc > floor and m_unr > floor))
        ok = ok and detail[s]["holds"]
    return ("SUSTAINED" if ok else "NOT SUSTAINED"), floor, detail


def parse_pairs(items):
    out = []
    for it in items or []:
        label, path = it.split("=", 1)
        out.append((label, path))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", nargs="+", required=True)
    ap.add_argument("--master", required=True)
    ap.add_argument("--ancestor", required=True)
    ap.add_argument("--unrelated", required=True)
    ap.add_argument("--extra", nargs="*", default=[], help="reported against the three references, decides nothing")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    K, _ = load_k()
    students = parse_pairs(args.students)
    (mname, mpath), (aname, apath), (uname, upath) = (parse_pairs([args.master])[0], parse_pairs([args.ancestor])[0],
                                                       parse_pairs([args.unrelated])[0])
    extra = parse_pairs(args.extra)
    errs = {lab: load_errors(p, K) for lab, p in students + [(mname, mpath), (aname, apath), (uname, upath)] + extra}

    rho, table = {}, {}
    for s, _ in students + extra:
        for r in (mname, aname, uname):
            c = correlate(errs[s], errs[r])
            table[f"{s} vs {r}"] = c
            rho[(s, r)] = c["spearman"]
    verdict, floor, detail = decide([s for s, _ in students], mname, aname, uname, rho)

    siblings = {}
    names = [s for s, _ in students]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            siblings[f"{names[i]} vs {names[j]}"] = correlate(errs[names[i]], errs[names[j]])

    print(f"{'pair':<16}{'n':>6}{'Spearman':>10}{'Pearson':>9}")
    for k, c in table.items():
        print(f"{k:<16}{c['n']:>6}{c['spearman']:>10.4f}{c['pearson']:>9.4f}")
    print("siblings (same master, same lambda; yardstick only):")
    for k, c in siblings.items():
        print(f"{k:<16}{c['n']:>6}{c['spearman']:>10.4f}{c['pearson']:>9.4f}")
    print(f"floor = max - min of rho(S, {mname}) over {names}: {floor:.4f}")
    for s, d in detail.items():
        print(f"  {s}: over {aname} {d['over_ancestor']:+.4f}, over {uname} {d['over_unrelated']:+.4f}, "
              f"beats both by more than the floor: {d['holds']}")
    print(f"VERDICT: {verdict}")
    if args.json_out:
        json.dump(dict(table=table, siblings=siblings, floor=floor, detail=detail, verdict=verdict),
                  open(args.json_out, "w"), indent=1)


if __name__ == "__main__":
    main()
