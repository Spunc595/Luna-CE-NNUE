# SPRT of the first self-trained net: pre-registration (written 2026-09-26, BEFORE the match starts)

Net: `step_8ep.nnue`, sha256 `43546e8eff855fb0dda5c028b0e66507015f774a23037bfbf72dff3d298339e4`, 6,297,664 bytes (checked on both sides).
1.0 G distinct S2 positions x 8 epochs = 8.0 G samples, 19 h 43 m on Oracle. Static Spearman on the SF18 set 0.9026 [0.9017, 0.9035] vs
embedded 0.9036: -0.0011 [-0.0013, -0.0008]. Static correlation is not a prediction of playing strength (D1: null Spearman, SPRT +44.8 Elo).

## Fixed before the run
```
A (patch) : v3.1.7 (tag, b93f9d8) with resources/net.bin replaced by step_8ep.nnue   (engines/net_patch)
B (base)  : v3.1.7 (tag, b93f9d8) unchanged                                            (engines/net_base)
SPRT      : elo0 = -5, elo1 = +5, alpha = beta = 0.05
cap       : 8,000 games (4,000 rounds)
tc        : 20+0.2, Hash 64, Threads 1, concurrency 2, no book, 8moves_v3.pgn, adjudication as in every earlier match
validity  : one game lost on time invalidates the match (investigate, do not just rerun)
futility  : from 2,000 games, stop if Elo + 95% CI half-width < 5 (sprt_stop_rule2.sh); Elo and CI recorded at the stop
bot       : OFF for the whole match (control match 2026-09-21 ran with no bot activity: none between 13:36 and 17:00 UTC); restarted at the end
```
Why -5/+5 and not 0/+10: the question is "can we switch to a net of our own without losing strength?", and parity is already a reason to ship
(with a net of our own every later net is measured against the previous one, not against a frozen external target). Same width as
[0, +10], so the same cost in games. Moving the bar on the very test one wants to pass is only legitimate because the reason is written
here first; going back to [0, +10] after a failure to "retry" would be cheating. (If [0, +10] is wanted instead, only elo0/elo1 change.)

## Gates already passed (numbers)
- SIMD: max|output weight| = **127** -> 255 x 127 = 32,385 <= 32,767 (pass, margin 382; 52 of 2,048 output weights are at >= 126, i.e. at
  bullet's AdamW clip of about +-1.98 x 64). References: gen1 6, gen2 6, gen3 4, pilot 36. Mutation check: an output weight of 2.5 (160) is refused.
- Accumulator: worst case +7,220 / -10,201 vs +-32,767 (margins 25,547 / 22,567); max|feature weight| 462, max|bias| 225. Mutation check:
  32 weights of 7.0 in one column are refused (57,068).
- Converter round-trip against the independent reference: 0 differences on 2,000 positions (and the round-trip is inside the converter).
- Size 6,297,664 bytes; sha256 identical on PC and Oracle.
- Swap gates: `resources/net.bin` differs (base b3faa88a..., patch 43546e8e...); the two trees are identical apart from net.bin; engine
  binaries differ (base `f817914f...` = the bot binary built from the tag on 2026-09-25, patch `3dd87686...`); kiwipete static eval
  base -294 cp vs patch -251 cp, depth 12 base cp -123 (359,149 nodes) vs patch cp -269 (269,528 nodes): the swap took.

## Decision rules (not renegotiated after the run)
- **H1 accepted**: ship: the net becomes `resources/net.bin` on a new commit, the notes say what it is (first net trained entirely on our data,
  1 G x 8 epochs, Spearman 0.9026, SPRT at [-5, +5]); only then re-measure D3 (its factor was tuned on akimbo's net).
- **H0 accepted**: statically equal, weaker in play: Spearman stops being the gate and becomes an entry filter; the next long run increases
  the DISTINCT positions (not the epochs): three points (0.25 G 0.8870, 1 G 1 epoch 0.8952, 1 G 8 epochs 0.9026) say fresh data bought more per
  sample than repetition.
- **Futility stop**: counts as rejected for shipping; Elo and SE at the stop are recorded (a near-zero Elo with a narrow SE is a measured parity).
- **Loss on time**: match invalid, cause investigated before any rerun.

## Prediction, declared now
With -0.0011 static I expect a result between -5 and +5 Elo (parity likely). On [-5, +5] I expect acceptance; on [0, +10] I would give
it 25-30%. If wrong, it goes in the report.
