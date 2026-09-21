# How noisy is the 20,000-node label (2026-09-21)

Rule: `results/label_depth_decision_rule.md` (commit `ec8137e`), committed before the scripts (`9c439b5`) and before
any search. Network: the published gen3 (`nets/luna_gen3.nnue`, sha256 `82aa1bf0d4e0a4351d070f08b51c7ccbaa41f2c02a68ad3fbbbd1eb7e7320954`),
identity gate **20/20**. Engine binary `f9edde89...` (the one of the earlier diagnostics), 1 thread, transposition table
cleared before every search, four workers, the bot stopped during the collection. 2,000 positions of
`results/eval_set.epd` (only the FEN column), 7 budgets, 14,000 searches
(`results/label_depth/label_depth_searches.csv`, sha256 `c5aba1e29d669a7681c5d473314402c669d2ce8a338789519f437e6ac0ee3f5a`).
Luna against Luna: no Stockfish anywhere.

## Verdict under the registered rule (stated before any comment)

**NOT ALIVE: `1 - rho(20k, 2M) = 0.0358 < 0.05`.** The 20,000-node label is already correlated at 0.9642 with the 2M
label; by the rule, depth is not the bottleneck and **the line is closed**. Bootstrap 95% CI of `1 - rho(20k, 2M)`:
[0.0295, 0.0434], entirely below 0.05, so the verdict does not hang on sampling noise. (The second condition, 100k
removing at least half of the residual, is stated for completeness and is moot once the question is not alive:
`1 - rho(100k, 2M) = 0.0178 <= 0.5 * 0.0358 = 0.0179`, met by a hair.) No systematic distortion of the 20k label was
found: the CI of its signed mean difference includes zero.

## Reference check (first, as registered)

**`rho(1M, 2M) = 0.9966` > 0.99: the 2M reference is stable enough to use.** It is a much deeper search of the same
network, not the truth.

## 3a - convergence (positions: 1,973 valid of 2,000; same set in every row)

| budget | rho(n, 2M) | 1 - rho | 95% CI of 1 - rho (bootstrap, info) | median abs diff (sigmoid) | median depth reached |
|---|---|---|---|---|---|
| 20,000 | 0.9642 | 0.0358 | [0.0295, 0.0434] | 0.0341 | 6 |
| 50,000 | 0.9752 | 0.0248 | [0.0204, 0.0304] | 0.0282 | 7 |
| 100,000 | 0.9822 | 0.0178 | [0.0141, 0.0227] | 0.0237 | 8 |
| 200,000 | 0.9878 | 0.0122 | [0.0104, 0.0146] | 0.0187 | 10 |
| 400,000 | 0.9920 | 0.0080 | [0.0067, 0.0099] | 0.0142 | 11 |
| 1,000,000 | 0.9966 | 0.0034 | [0.0026, 0.0046] | 0.0062 | 12 |
| 2,000,000 (reference) | 1 | 0 | | 0 | 14 |

The median depth reached at 20,000 nodes here is **6** (the depth of the last completed iteration printed by the engine),
not the 7 quoted in the rule's motivation from a 120-position sample.

## 3b - noise or distortion: signed mean of `label(n) - label(2M)` (side to move's point of view; a positive mean = the
shorter search overrates the side to move)

| budget | mean | 95% CI (bootstrap, 10,000, seed 20260921) | excludes 0 |
|---|---|---|---|
| 20,000 | -0.00157 | [-0.00467, +0.00156] | no |
| 50,000 | -0.00272 | [-0.00531, -0.00014] | yes |
| 100,000 | -0.00208 | [-0.00429, +0.00004] | no |
| 200,000 | -0.00233 | [-0.00416, -0.00057] | yes |
| 400,000 | -0.00164 | [-0.00306, -0.00020] | yes |
| 1,000,000 | -0.00002 | [-0.00095, +0.00088] | no |

The rule decides on the 20k row only, where the interval includes zero. For information: the sign is negative at every
budget below 1M (the shorter searches **underrate** the side to move slightly), and at three of the intermediate budgets the
interval excludes zero, but the size is about 0.002 in sigmoid space, one tenth of the median absolute difference, i.e. a
small systematic offset under a much larger random scatter.

## 3c - where the 20k label errs: `|label(20k) - label(2M)|`

| cell | n | median | mean |
|---|---|---|---|
| best move (2M): capture | 463 | 0.0344 | 0.0459 |
| best move (2M): quiet | 1,508 | 0.0340 | 0.0491 |
| best move (2M): promotion (n < 100: UNDER-POWERED, no conclusion) | 2 | 0.0348 | 0.0348 |
| pieces <= 8 | 193 | 0.0241 | 0.0410 |
| pieces 9-12 | 256 | 0.0301 | 0.0450 |
| pieces 13-20 | 654 | 0.0378 | 0.0559 |
| pieces 21-32 | 870 | 0.0344 | 0.0452 |

Captures and quiet positions have the same median error (0.0344 against 0.0340); the error is largest in the 13-20 piece
band and smallest with few pieces.

## Discarded and limits

* Discarded: **27** positions with a mate score at some budget (mate scores per budget: 12, 14, 14, 17, 22, 24, 27 from
  20k to 2M); 10 of the 1,973 valid positions have a clamped score (|cp| > 2000) at some budget. The exclusion removes
  positions where a deeper search finds a forced mate that a shallower one does not (slightly favours quiet positions).
* What this does not say: the 2M search is the same network searched deeper, so the measure shows how close the 20k label
  is to what the same network converges to with depth; it does not show how close the label is to the truth. Blind spots
  of the network's own static evaluation (RESULTS 5.12, 5.15) are inside the 2M label too, and more depth does not remove
  them.

No outcome of this measure starts generation 4; it bears on the annotation budget to propose, and by the registered rule
the 20k budget is not shown to be a bottleneck.
