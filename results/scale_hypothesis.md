# Scale hypothesis: does the new network's eval need a different SCALE constant? (2026-09-27, PC only, Oracle untouched)

Built locally (not on Oracle, which had the fixed-length no-D3 match running): X (akimbo's network, D3 disabled) and Y
(`step_8ep.nnue`, D3 disabled), same single-line patch as this morning's Oracle build (`mat_factor` forced to 1024/1024).
Gates: tree diff X vs the v3.1.7 tag differs in exactly `src/nnue.rs`; X vs Y differs in exactly `resources/net.bin`; Y's
`resources/net.bin` is byte-identical to `step_8ep.nnue`; D3-disabled eval-ratio gate on the same two FENs as Oracle's
build gave base/X = 0.7024 (low material) and 0.9452 (full material) — identical to Oracle's numbers (same network, same
code), confirming the PC build matches.

## Measurement: 2,000 positions, seed 7, `results/eval_set.epd` (the same sample used for the akimbo comparison)
0 positions excluded (game-over check via python-chess; none of the 2,000 sampled FENs were terminal).

| indicator | value |
|---|---|
| 1. slope (Y = k*X through the origin) | **1.1164** |
| 2. std(Y)/std(X) | 1.1347 |
| 3. p90(\|Y\|)/p90(\|X\|) | 1.1270 |
| 4. median(\|Y\|/\|X\|), positions with \|eval(X)\|>50cp (n=1,781) | 1.0912 |
| 5. Spearman(X,Y) | 0.9823 |

## Reading, against the pre-registered thresholds
The four scale indicators (1.09-1.13) are outside the 0.92-1.08 "no disparity" band and reasonably concordant with each
other (spread 0.04): **scale disparity confirmed**, per the pre-registered rule.

**But the direction is the OPPOSITE of what the hypothesis predicted.** The hypothesis (52/2048 output weights at
AdamW's clip) argued the new network's outputs are *systematically smaller* than akimbo's — output_weights clipped means
the network "wanted" larger outputs and couldn't produce them. The measurement says the opposite: **Y's evaluations are
about 9-13% *larger* in magnitude than X's**, on average, not smaller. The Kiwipete anecdote quoted in the hypothesis
(akimbo -294 vs new net -251, ratio 0.854) pointed the same wrong way and should have been read as a single noisy data
point, not a trend — which is exactly what it was: at the position level the scatter is large (individual pairs range
from Y/X ~0.6 to Y/X ~1.9; see `scale_hyp_x.txt`/`scale_hyp_y.txt`), and Kiwipete happened to land on the low side.
**The clip mechanism does not explain the disparity's direction; something else does, not identified here.**
Spearman(X,Y) = 0.98, high but not near 1.00: most of what one net says relative to the other is scale, but a residual
rank disagreement remains beyond a pure rescaling (expected between two independently trained networks; this is
mentioned in the pre-registration as the confirmation that "we are looking at a scale, not a disagreement" — 0.98 supports
that reading without being definitive).

## Correction applied and verified (Part 4)
`SCALE = 400 / 1.1164 = 358.29`, rounded to **358** (`src/nnue.rs`, `const SCALE: i32 = 358;`, Y build only; X/akimbo
unchanged since it is the reference scale the search margins were tuned against). Gate: re-ran the same measurement with
the corrected Y binary.

| indicator | corrected Y vs X |
|---|---|
| slope | **0.9991** |
| std ratio | 1.0155 |
| p90 ratio | 1.0089 |
| median ratio | 0.9763 |
| Spearman | 0.9823 (unchanged, as expected: rescaling does not change rank) |

Slope lands at 1.00 as the gate requires. The correction is purely a rescaling, so Spearman is unchanged — consistent with
being blind to it by construction.

## Not done (Oracle was not touched, as instructed)
**Part 4's in-play verification match** (new net with corrected SCALE vs new net with original SCALE, fixed length, same
shape as today's no-D3 match) was NOT run: Oracle is occupied by `fixed_net8ep_vs_akimbo_noD3_tc10` (in progress). Queued
for after that match closes and the bot has been confirmed running.
