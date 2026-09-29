# Bucket experiment, Part 4: gates, scale, Spearman (2026-09-29)

Checkpoint: `ck_8ep_buckets/luna_pilot_buckets-480` (final, 480/480 superbatches, 8.0 G samples, 30h27m). Round-trip
(converter -> independent reference -> Luna's own eval) on 2,000 positions of the REAL trained net: **0 differences.**

## Quantisation gates
| | this net | reference: pilot | reference: 8-epoch no-bucket |
|---|---|---|---|
| max\|output weight\| | 127 (255*127=32,385 <= 32,767, PASS) | 36 | 127 |
| output weights at/near clip (\|w\|>=126/128) | 79 / 2,048 | - | 52 / 2,048 |
| accumulator worst case | +5,125 / -9,465 (limits +-32,767) | +1,821/-2,118 | +7,220/-10,201 |
| max\|feature_weight\| / max\|feature_bias\| | 378 / 160 | - | - |

## Scale coefficient (mandatory, per yesterday's SPRT finding — measured BEFORE the match, each net gets its own SCALE)
X = akimbo, D3 off (yesterday's `pc_X_nod3.exe`); Y = this net's `ReferenceBuckets`, D3 off (bucket table only, no material
scale involved). 2,000 random positions (seed 42), no game-over positions excluded (0 found).

| indicator | value |
|---|---|
| slope (Y = k*X through the origin) | **1.0539** |
| R^2 (uncentered) | **0.9815** |
| residual std (cp) | 199.63 |
| residual median \|resid\| (cp) | 94.27 |
| std(X) / std(Y) | 1377.3 / 1464.6 |

**Reading, against the pre-registered table (same one used for the no-bucket net yesterday):** coefficient outside
0.92-1.08, and this time **R^2 = 0.9815 IS above the ~0.98 threshold** for "almost all the difference is scale" (the
no-bucket net was 0.969, just under). So this net's gap from akimbo is closer to *pure* scale than the no-bucket net's
was. `SCALE = 400 / 1.0539 = 379.55`, rounded to **380**.

## Spearman (entry filter only, not a gate — per the rule)
Full SF18 evaluation set (434,897 positions), engine v3.1.6 raw (no material scale), this net as `luna.nnue`:
**rho = 0.9043** [0.9034, 0.9053]. Above the embedded akimbo network (0.9036), above gen3 (0.8253), and above the
no-bucket 8-epoch net (0.9026). **No collapse, so no reason to suspect a layout error per the pre-registered warning**
(a large drop would look the same from outside as wrong rows in the wrong bucket block; this is the opposite of a
drop). This number does not decide anything on its own; the match does.

## Next: build both match binaries with SCALE=400 (default) and SCALE=380, D3 active on both, same gates as yesterday
(tree diff exactly one line, sha differ, eval differs on a fixed position), verify the SCALE correction against a
larger sample before trusting it (re-run the scale measurement with the corrected binary, expect slope ~1.00), THEN
launch the SPRT with each net at its own correct scale.

## CORRECTION (2026-09-29, before the match): wrong position source invalidated the R^2/SCALE numbers above
The scale measurement above used `bucket_layout_check.positions()` (random self-play walks), NOT the same source as
yesterday's no-bucket measurement (`results/eval_set.epd`, seed 7). This was caught by comparing std(X) across the two
measurements: **744.8 cp yesterday vs 1377.3 cp today, for the SAME akimbo D3-off binary** — impossible unless the
position sets differ in character, which they did (self-play walks reach far more decisive/extreme positions than
`eval_set.epd`'s curated real-game/puzzle positions). The reported R^2 = 0.9815 and SCALE = 380 above are **wrong**,
an artifact of measuring on a more extreme sample, not a property of the network. **Re-measured with the correct,
homogeneous source** (`eval_set.epd`, seed 7, same 2,000 positions as yesterday's no-bucket measurement):

| indicator | bucket net (corrected) | no-bucket net (yesterday, same source) |
|---|---|---|
| std(X), akimbo D3-off | 744.8 (matches yesterday exactly — confirms the fix) | 744.8 |
| std(Y) | 840.5 | 845.2 |
| slope | **1.1156** | 1.1164 |
| R^2 (uncentered) | **0.9784** | 0.9688 |
| residual std (cp) | **122.99** | 148.96 |
| residual median \|resid\| (cp) | 61.96 | - |
| SCALE corrected | **400/1.1156 = 358.56 -> 359** | 358 |

**The two networks turn out to have almost identical scale disparity against akimbo** (slope ~1.115-1.116, SCALE
correction 358-359) — not the "0.9815, mostly scale" outlier the bad sample suggested. Reading against the
pre-registered table: R^2=0.978 is still below the ~0.98 threshold (third row: scale AND a real disagreement, same as
the no-bucket net, not the second row "almost all scale"). The match binaries below use **SCALE=359** for the bucket
net, and **B is `step_8ep.nnue` at ITS OWN measured SCALE=358** (the exact `engines/net_scale358` binary already built
and SPRT-tested yesterday, sha `8df114079ff6f81af6f0ecb5700cf88ebd62e840577cd4f09de3166b0b395355`) — not a straw-man
SCALE=400 baseline, which would have handed one side an unearned ~16 Elo (yesterday's own measured gain from the
358 correction) and made the match measure calibration instead of architecture, the exact mistake that voided the
first net8ep verdict.

## The scale inflation is a property of the training recipe, not the architecture
The two networks' coefficients against akimbo (same eval_set.epd, seed 7, homogeneous now): **1.1156 (bucket) vs
1.1164 (no-bucket)**, 0.07% apart — the same number within measurement precision. `400/1.1156 = 358.55`,
`400/1.1164 = 358.30`: the two corrected SCALE values also coincide. **Using SCALE=359 for the bucket net (distinct
from 358) would have introduced a 0.3% difference for no reason** — D4 showed even a real 16% margin retune could not
be measured cleanly; 0.3% is noise. Rebuilt with **SCALE=358 for both sides**, on a tree that is a copy of
`build_net_scale358` with only `resources/net.bin` swapped — the two trees now differ in exactly one file, the
cleanest possible single-variable comparison, and the diff gate lists one line.

**Reading:** the WDL-blend mechanism identified yesterday (bullet's convention, blend toward the discrete game result
pulling decisive-position targets to more extreme probabilities) predicted a scale inflation from the RECIPE, not from
either architecture. Two independently-trained networks landing on the same ~1.116 factor confirms it: **the correct
fix, going forward, is the WDL ramp in the bullet training script, not a per-network `SCALE` constant patched into the
engine after the fact.** A downstream `SCALE` patch works today but leaves a magic number nobody will be able to
explain in six months; it is being used here only because re-running the 30-hour training with a different ramp was
not in scope for this comparison.

## Two static indicators now agree, for the first time in four days
| | no-bucket (8ep) | bucket (8ep) |
|---|---|---|
| residual vs akimbo (same population, after removing scale) | 149 cp | **123 cp (-17%)** |
| Spearman (full SF18 set) | 0.9026 | **0.9043** |

Both point the same way (the bucket net agrees with akimbo more, after scale is factored out, and correlates better
with Stockfish 18). **Neither predicts Elo** — learned three times in four days now (D1: null Spearman, +44.8 Elo;
net8ep: -0.0011 Spearman, ~-50 Elo; both times the static number and the match disagreed). R^2 = 0.9784 for the
bucket net is still below the ~0.98 threshold, so the reading stays the third row for both networks (scale AND a real
disagreement) — not "mostly scale" for one and not the other. **The match decides.**
