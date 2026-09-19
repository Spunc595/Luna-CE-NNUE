"""
Tail analysis of the static-vs-search gap, from the per-position CSVs already
produced by diagnose_static_search_gap.py. No engine, no new search: static and
search values are read from the files. The rule this analysis is judged
against was committed before the script was run:
results/gap_tail_decision_rule.md

Gap = |sigmoid(K*search) - sigmoid(K*static)|, K read from
pipeline/train/dataset.py (recomputed here from the raw static/search columns,
not taken from the rounded gap column).

Usage:
  python analyze_gap_tail.py --csv gen2=../../results/static_vs_search_gap_gen2.csv \
      --csv gen3=../../results/static_vs_search_gap_gen3.csv
"""
import argparse
import csv
import math
import random
import statistics

from diagnose_static_search_gap import load_k, sigmoid, spearman

SEED = 20260919
N_BOOT = 10000
THRESHOLDS = (0.10, 0.20, 0.30)


def load_rows(path, K):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            static, search = float(r["static_cp"]), float(r["search_cp"])
            rows.append({
                "cls": r["class"], "static": static, "search": search,
                "gap": abs(sigmoid(K * search) - sigmoid(K * static)),
            })
    return rows


def quantile(sorted_vals, q):
    """Linear interpolation between order statistics (same as numpy's default)."""
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def dist_table(rows, label, total_n, total_sq):
    g = sorted(r["gap"] for r in rows)
    n = len(g)
    sq = sum(x * x for x in g)
    fr = [sum(1 for x in g if x > t) / n for t in THRESHOLDS]
    print(f"  {label:<9}{n:>6}{statistics.mean(g):>8.4f}{quantile(g, .5):>8.4f}{quantile(g, .75):>8.4f}"
          f"{quantile(g, .90):>8.4f}{quantile(g, .95):>8.4f}{quantile(g, .99):>8.4f}{g[-1]:>8.4f}"
          f"{fr[0]*100:>8.1f}%{fr[1]*100:>7.1f}%{fr[2]*100:>7.1f}%{sq/total_sq*100:>9.1f}%")


def composition(rows, frac):
    order = sorted(range(len(rows)), key=lambda i: -rows[i]["gap"])  # stable: ties keep input order
    k = int(round(frac * len(rows)))
    top = [rows[i] for i in order[:k]]
    out = {}
    for cls in ("capture", "quiet", "promotion"):
        out[cls] = sum(1 for r in top if r["cls"] == cls)
    overall_cap = sum(1 for r in rows if r["cls"] == "capture") / len(rows)
    top_cap = out["capture"] / k
    return k, out, top_cap, overall_cap, top_cap / overall_cap


def bootstrap(rows, rng):
    cap = [r for r in rows if r["cls"] == "capture"]
    qui = [r for r in rows if r["cls"] == "quiet"]
    med_ratio, p90_ratio, rho_diff = [], [], []
    for _ in range(N_BOOT):
        c = rng.choices(cap, k=len(cap))
        q = rng.choices(qui, k=len(qui))
        cg = sorted(r["gap"] for r in c)
        qg = sorted(r["gap"] for r in q)
        med_ratio.append(quantile(cg, .5) / quantile(qg, .5))
        p90_ratio.append(quantile(cg, .9) / quantile(qg, .9))
        rho_diff.append(spearman([r["static"] for r in c], [r["search"] for r in c])
                        - spearman([r["static"] for r in q], [r["search"] for r in q]))
    ci = lambda v: (quantile(sorted(v), .025), quantile(sorted(v), .975))
    cg = sorted(r["gap"] for r in cap)
    qg = sorted(r["gap"] for r in qui)
    return {
        "med": (quantile(cg, .5) / quantile(qg, .5), ci(med_ratio)),
        "p90": (quantile(cg, .9) / quantile(qg, .9), ci(p90_ratio)),
        "rho": (spearman([r["static"] for r in cap], [r["search"] for r in cap])
                - spearman([r["static"] for r in qui], [r["search"] for r in qui]), ci(rho_diff)),
    }


def filter_comparison(rows, share):
    """Returns (threshold-filter error removed, class-filter expected error removed), both as fractions."""
    n = len(rows)
    total_sq = sum(r["gap"] ** 2 for r in rows)
    cap_share = sum(1 for r in rows if r["cls"] == "capture") / n
    cap_err = sum(r["gap"] ** 2 for r in rows if r["cls"] == "capture") / total_sq
    k = int(round(share * n))
    top = sorted((r["gap"] ** 2 for r in rows), reverse=True)[:k]
    thr = sum(top) / total_sq
    if share <= cap_share:
        cls = share / cap_share * cap_err
    else:
        cls = cap_err + (share - cap_share) / (1 - cap_share) * (1 - cap_err)
    return thr, cls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="append", required=True, help="label=path")
    args = ap.parse_args()
    K, k_line = load_k()
    print(f"K = {K!r}  (`{k_line}`)   bootstrap seed = {SEED}, resamples = {N_BOOT}")

    data = {}
    for item in args.csv:
        label, path = item.split("=", 1)
        data[label] = load_rows(path, K)

    verdict = {}
    for label, rows in data.items():
        n = len(rows)
        total_sq = sum(r["gap"] ** 2 for r in rows)
        rng = random.Random(f"{SEED}-{label}")
        print(f"\n################ {label} (n={n}) ################")

        print("\n[1] gap distribution per class")
        print(f"  {'class':<9}{'n':>6}{'mean':>8}{'median':>8}{'p75':>8}{'p90':>8}{'p95':>8}{'p99':>8}{'max':>8}"
              f"{'>0.10':>9}{'>0.20':>8}{'>0.30':>8}{'err%':>10}")
        for cls in ("capture", "quiet"):
            dist_table([r for r in rows if r["cls"] == cls], cls, n, total_sq)
        print("  (promotion, n=2, excluded from class comparisons: under-powered, n<100)")

        print("\n[2] composition of the top of the gap ranking")
        lift10 = None
        for name, frac in (("top decile", 0.10), ("top 5%", 0.05), ("top quartile", 0.25)):
            k, comp, top_cap, all_cap, lift = composition(rows, frac)
            print(f"  {name:<13} k={k:>4}  capture {comp['capture']:>4} quiet {comp['quiet']:>4} promotion {comp['promotion']:>2}"
                  f"   capture share {top_cap*100:5.1f}% vs {all_cap*100:.1f}% overall  (lift {lift:.2f}x)")
            if frac == 0.10:
                lift10 = lift

        print(f"\n[3] bootstrap 95% CIs ({N_BOOT} resamples, each class resampled within itself)")
        b = bootstrap(rows, rng)
        for key, name in (("med", "capture/quiet ratio of MEDIANS (first rule's (a))"),
                          ("p90", "capture/quiet ratio of 90th percentiles (condition B)"),
                          ("rho", "Spearman difference capture - quiet")):
            est, (lo, hi) = b[key]
            print(f"  {name:<58} {est:8.4f}   95% CI [{lo:.4f}, {hi:.4f}]")

        print("\n[4] filter by gap threshold vs filter by move class (squared error removed)")
        cap_share = sum(1 for r in rows if r["cls"] == "capture") / n
        print(f"  {'discarded share':<22}{'by gap threshold':>18}{'by move class (expected)':>28}{'difference':>13}")
        margins = []
        for share in (0.10, cap_share, 0.40):
            thr, cls = filter_comparison(rows, share)
            margins.append(thr - cls)
            print(f"  {share*100:>6.1f}%{'':<15}{thr*100:>17.1f}%{cls*100:>27.1f}%{(thr-cls)*100:>+12.1f}pp")

        cond_a = lift10 >= 2.0
        cond_b = b["p90"][1][0] > 1.2
        verdict[label] = (cond_a, cond_b, lift10, b["p90"], margins[1])  # margin at the capture share

        print("\n[5] counterfactual Spearman (NOT used to decide: removing a class changes the sample"
              " dispersion, so this is confounded by range restriction; the valid comparison is within-class)")
        allr = spearman([r["static"] for r in rows], [r["search"] for r in rows])
        noc = [r for r in rows if r["cls"] != "capture"]
        print(f"  all positions {allr:.4f}   without captures {spearman([r['static'] for r in noc], [r['search'] for r in noc]):.4f}")

    print("\n================ VERDICT ACCORDING TO THE REGISTERED RULE ================")
    for label, (a, b, lift, p90, _) in verdict.items():
        print(f"  {label}: (A) top-decile capture lift {lift:.2f}x (need >= 2.0) -> {'MET' if a else 'not met'};"
              f"  (B) p90 ratio {p90[0]:.3f}, CI [{p90[1][0]:.3f}, {p90[1][1]:.3f}] lower bound > 1.2 -> {'MET' if b else 'not met'}")
    c = all(a and b for a, b, *_ in verdict.values())
    print(f"  (C) (A) and (B) on BOTH networks -> {'MET' if c else 'not met'}")
    print(f"  => capture class is the right filtering instrument: {c}")
    print("\n  Separately registered question (threshold filter removes >= 10pp more squared error than class filter, at the capture share):")
    for label, (*_, margin) in verdict.items():
        print(f"  {label}: margin at the capture share = {margin*100:+.1f}pp -> "
              f"{'YES, wide margin' if margin >= 0.10 else 'no wide margin'}")


if __name__ == "__main__":
    main()
