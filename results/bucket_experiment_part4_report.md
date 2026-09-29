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
