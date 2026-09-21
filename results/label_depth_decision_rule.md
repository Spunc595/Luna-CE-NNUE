# Label depth — decision rule (registered before the script that computes it is run)

Written and committed BEFORE the collection or the analysis script is run; the commit timestamp is the proof of
ordering. Nothing below is edited after seeing numbers; any later change is a new dated amendment at the end of this
file. No training is involved: only engine searches on 2,000 positions and statistics on their results.

## Why this measure, and why now

The lambda sweep (RESULTS.md 5.16) gave a robust result: the static rho against Stockfish falls monotonically as lambda
falls (1.0: 0.7037, 0.7: 0.6979, 0.4: 0.6783, 0.0: 0.6552), i.e. the `eval` component of the label is the good part and
the WDL does harm. That component is computed by a search of median **depth 7** at 20,000 nodes. Measured on 120 positions
of the evaluation set with the current engine: 20,000 nodes -> median depth 7 (mean 7.3, min 4); 100,000 -> median 10
(mean 10.2); 400,000 -> median 12 (mean 13.5). So the signal that matters most is the one being computed worst.

"Depth 20" is not on the table: with an effective branching factor of about 2 per ply, going from depth 12 to 20 costs
about 2^8 times the nodes, roughly 10^8 nodes per position, 3*10^14 for a generation: years on this machine. The real
choice is between **20k, 100k and 400k** nodes, which cost about 9 hours, 45 hours and 7.5 days of annotation. This
measurement is to decide **before** spending those hours.

## Data

The 2,000 positions of `results/eval_set.epd` (zero overlap with the training data, already certified); **only the FEN
column is used**. The network is the published **gen3** (`nets/luna_gen3.nnue`, sha256 `82aa1bf0...320954`): it is the
network that would label generation 4, so it is its depth that is measured. Engine binary of the earlier diagnostics
(`f9edde89...`), 1 thread, transposition table cleared (`ucinewgame`) before every search, so each budget is independent
of the others and deterministic. Identity gate 20/20 as in `diagnose_static_search_gap.py` (the first 20 positions,
`eval` with the network and with the embedded network must differ on all 20).

For each position, searches at `go nodes N` with
`N in {20,000; 50,000; 100,000; 200,000; 400,000; 1,000,000; 2,000,000}`. The **label** at budget N is what the
annotator would use: the search score from the side to move's point of view, clamped to +/-2000 cp, then
`sigmoid(K * clamp(eval))` with `K = ln(10)/400` (read from `pipeline/train/dataset.py`), as `dataset.py` does.

**Valid positions:** a single common set, the positions for which **none** of the seven budgets returned a mate score
(so every row of every table is over the same positions). The number discarded, and the number of mate scores per
budget, are reported. Limit, stated in advance: this removes positions where a deeper search finds a forced mate that a
shallower one does not, i.e. it slightly favours quiet positions.

**The 2M budget is the deep reference, not the truth**: it is only a much deeper search of the same network, and is
reported as such.

## The check that validates the reference (read first, before any other number)

If the 2M reference were itself far from convergence, `rho(20k, 2M)` would be low because of the reference and not
because of the 20k label. Check: **`rho(1M, 2M)`**. If it is above **0.99** the reference is stable enough to use. If it
is not, the reference has not converged, the whole scale shifts, and the measurement is reported **with that limit
declared** and not read as if 2M were a fixed point. It is the first row of the results.

## The three questions

* **3a — how far is the 20k label.** For each budget n: `rho(label(n), label(2M))` (Spearman over the valid positions,
  on the sigmoid labels) and the median of `|label(n) - label(2M)|` in sigmoid space.
* **3b — noise or distortion.** The **signed mean difference** `label(n) - label(2M)` with its 95% confidence interval
  (bootstrap over positions, 10,000 resamples, fixed seed 20260921), for every budget. The label is from the side to
  move's point of view, so a positive mean means the shorter search **overrates** the side to move. If the interval is
  centred on zero the short search errs at random (with millions of positions the error averages out); if it is
  systematically away from zero the short search errs always the same way and no amount of data corrects it.
* **3c — where it errs.** `|label(20k) - label(2M)|` stratified by the class of the **2M best move** (capture / quiet /
  promotion) and by piece count (<= 8, 9-12, 13-20, 21-32). Cells with n < 100 are flagged under-powered and support no
  conclusion.

## The decision

**The hypothesis:** the 20,000-node label (median depth 7) is imprecise enough to limit the quality of the network, and
raising the annotation budget is a real lever.

* **The question is alive** only if `1 - rho(20k, 2M) >= 0.05`. If the 20k label is already correlated above 0.95 with
  the 2M label, even removing that difference entirely would buy very little: it is written that depth is not the
  bottleneck and **the line is closed**. (With 2,000 paired positions the standard error of a Spearman correlation in
  that region is about 0.005, so the threshold is resolvable.)
* **Raising the budget is justified** only if, besides the condition above, going from 20k to 100k removes **at least
  half** of the residual disagreement: `1 - rho(100k, 2M) <= 0.5 * (1 - rho(20k, 2M))`. Five times the cost must buy at
  least half of the distance; if it buys less, the ratio does not justify the 45 hours.
* **Independently of the two conditions above**, if 3b finds a systematic distortion of the **20k** label whose
  confidence interval **excludes zero**, it is reported as a result in its own right: it is a defect of the labels that
  no quantity of data corrects, and it changes the picture even when the thresholds above do not trigger. (The intervals
  of the other budgets are reported and decide nothing.)
* Bootstrap intervals of `1 - rho` at each budget are reported alongside, as information: the decision uses the point
  estimates as written.

**No outcome starts generation 4.** This measure decides the annotation **budget to propose**, not the generation.

## What is NOT done

Nothing here is compared with Stockfish and Stockfish is not introduced at any point: Luna is compared with Luna at
different budgets, a homogeneous comparison and the only one that answers the question asked. (Stockfish stays a
measurement tool for `rho` elsewhere.)
