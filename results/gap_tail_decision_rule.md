# Gap tail analysis — decision rule (registered before running the analysis)

Written and committed BEFORE the analysis script was run; the commit
timestamp is the proof of ordering. Nothing below was edited after seeing
numbers.

## Disclosure: this analysis is NOT independent of the first one

It was decided AFTER seeing that conditions (a) and (c) of the first rule
(`static_vs_search_gap_decision_rule.md`, commit `2ab5773`) diverged: (a)
compared MEDIANS of the gap (capture/quiet = 1.362, threshold 1.5, not met),
while (c) — share of squared error over share of positions — read 1.657.
Squared error lives in the tail, not the median, so (a) measured the wrong
thing. The first verdict ("do not filter") stands for the decision taken at
that time. This analysis is a follow-up prompted by data, not a fresh
independent test, and must not be presented as one.

Whatever comes out, it does NOT by itself authorize filtering. At most it
authorizes DESIGNING the gen4 experiment; the proof that filtering helps is a
training run, not a statistic.

## Data

Only the per-position CSVs already produced (`results/static_vs_search_gap_gen2.csv`,
`..._gen3.csv`). No new engine computation. Gap = `|sigmoid(K*search) -
sigmoid(K*static)|`, `K = ln(10)/400`. Classes: capture vs quiet (promotion,
n=2, is excluded from the class comparisons and kept only in totals).

## Decision rule

The "capture" class is the right filtering instrument only if ALL THREE hold:

- (A) among the positions in the top decile by gap, the share of captures is
  at least TWICE their share in the whole sample;
- (B) the 95% bootstrap confidence interval of the capture/quiet ratio of the
  90th percentile of the gap EXCLUDES 1.2;
- (C) (A) and (B) both hold on BOTH networks, gen2 and gen3.

If the rule is not satisfied, the verdict of the first diagnostic is
confirmed twice and the question of a per-class filter is closed.

Operational details fixed in advance: "excludes 1.2" means the lower bound of
the interval is above 1.2; bootstrap = 10,000 resamples with replacement,
each class resampled within itself, percentile method, fixed seed reported by
the script; the top decile is the top 10% of all classified positions by gap
(ties broken by input order).

## Separately registered question

Regardless of (A)-(C): at equal data loss — discarding the same share of
positions — does a filter by GAP THRESHOLD remove more squared error than a
filter by MOVE CLASS? Answered on gen3, and also reported for gen2, at
discard shares of 10%, the capture share of that network (24.6% for gen3),
and 40%.

Definitions fixed in advance. Gap-threshold filter at share s: discard the
top s of positions by gap; error removed = their share of total squared
error (exact). Class filter at share s: if s <= capture share, discard a
random subset of captures, and the expected error removed is
(s / capture share) x (capture error share), computed analytically (no
randomness); if s > capture share, discard all captures and a random subset
of the other positions, expected error removed = capture error share +
((s - capture share) / (1 - capture share)) x (non-capture error share).
"Wide margin" is fixed as: the threshold filter removes at least 10
percentage points more squared error than the class filter at the matching
share. If yes, the move class is the wrong tool whatever (A)-(C) say, and the
gen4 question changes shape.

Honesty note recorded in advance: a gap-threshold filter is defined using the
STATIC evaluation of the network about to be replaced — a circular dependency
(a curriculum choice, not an error) that must be declared, not hidden.

## Also reported, not used to decide

- The distribution of the gap per class (mean, median, p75, p90, p95, p99,
  max; share of positions with gap > 0.10 / 0.20 / 0.30), the class
  composition of the top decile / top 5% / top quartile.
- Bootstrap CIs for the capture/quiet ratio of the MEDIANS (the first rule's
  condition (a), closing the question of whether 1.362 vs 1.5 was
  distinguishable) and for the Spearman difference between classes.
- A counterfactual Spearman with vs without captures is confounded (removing
  a class changes the sample dispersion — range restriction) and is NOT used
  to decide; the valid comparison is the within-class one already reported.
- Any cell with n < 100 is flagged under-powered and supports no conclusion.
