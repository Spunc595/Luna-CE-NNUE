# Scale hypothesis, v2: a prediction before measuring, R^2/residuals, Kiwipete's homogeneity (2026-09-27, PC only)

Supersedes `results/scale_hypothesis.md` for the reading; that report's numbers (slope, std/p90/median ratios, Spearman,
the SCALE=358 correction and its slope-1.00 gate) are unchanged and reused here, plus the two statistics that were
missing from it. Oracle was free throughout Parts 1-5; Part 6 (below) uses it for the in-play verification.

## Part 1: configuration read, and a prediction written from it BEFORE this document's own re-measurement
(Full disclosure: this morning's `scale_hypothesis.md` had already measured the disparity before this document was
written, so I am not blind to the answer. What follows is the mechanism read from the config, checked against the number
that was already known, not a blind trial.)

- `pipeline/bullet_pilot/luna_pilot.rs:54`: `eval_scale: 400.0`. `src/nnue.rs:53`: `const SCALE: i32 = 400`. **They match
  exactly** — this network was deliberately trained at the engine's own scale (see phase-2 report: "so that Luna's
  SCALE=400 inference needs no rescaling", unlike Petrel's 800). QA=255, QB=64 (`nnue.rs:54-55`) are the converter's own
  constants, used identically for every net. On this axis alone, no mismatch is predicted.
- `luna_pilot.rs:57`: `wdl_scheduler: wdl::CosineDecayWDL { start: 0.0, end: 0.1, ... }`, bullet's own convention
  (`value.rs:115`, confirmed in phase 2: bullet's blend weights the **game result**, not the eval). A blend of up to 10%
  toward the discrete result (0/0.5/1) pulls the training target for decisive positions AWAY from a moderate
  eval-implied probability and toward the more extreme actual outcome — real games are more one-sided than a calibrated
  eval alone would say for many decisive-looking positions. After the inverse-sigmoid step to centipawns, a target
  pulled toward 0 or 1 maps to a LARGER magnitude, not smaller. **Prediction: a mild amplification (coefficient somewhat
  above 1.00), not a large factor** — the blend only reaches 10% and only at the end of the ramp, averaging map to a
  small effect.
- Akimbo's own training scale is not separately documented anywhere found; it doesn't need to be here, since Luna's
  `SCALE=400` already reproduces akimbo's output bit-exact (verified earlier, 0 differences on 2,000 positions) — that
  IS akimbo's effective scale by construction.
- **Prediction, before re-running the measurement: coefficient in roughly 1.00-1.15, driven by the WDL blend, not a
  large mismatch; no reason from the config for a SMALLER output (the clip-based prediction from this morning's first
  hypothesis is not supported by the recipe itself).**

**Against the actual measurement (Part 2 below and this morning's): coefficient 1.1164.** Inside the predicted range,
and the direction (larger, not smaller) matches the WDL-blend mechanism, not the clip mechanism. The prediction is a
plausible account of the true mechanism where this morning's clip-based one was not (see `PROTOCOLLO.md`, "the clip
hypothesis had the right mechanism [for the 52 clipped weights] and the wrong direction [for the scale]").

## Part 2: the measurement, plus R^2 and residual std (the statistic missing this morning)
Same 2,000-position sample (seed 7, `results/eval_set.epd`), same X/Y binaries (D3 disabled both sides), 0 positions
excluded (no game-over FENs in the sample).

| indicator | value |
|---|---|
| 1. slope (Y = k·X through the origin) | 1.1164 (unchanged from this morning) |
| 2a. R^2 (uncentered, through-origin fit) | **0.9688** |
| 2b. residual std (cp) | **148.96** |
| 2b. residual median \|resid\| (cp) | 68.03 |
| 3. std(Y)/std(X) | 1.1347 |
| 4. p90(\|Y\|)/p90(\|X\|) | 1.1270 |
| 5. median(\|Y\|/\|X\|), \|eval(X)\|>50cp (n=1,781) | 1.0912 |
| 6. Spearman(X,Y) | 0.9823 |

std(Y)=756.4cp, std(X)=744.8cp: the residual std of 149cp is about 20% of std(Y) — not negligible next to the signal.

## Part 3: Kiwipete homogeneity check
`Evaluation:` (static, `main.rs:603`) and `info depth N score cp` (search, `search.rs:474`) both report from the point
of view of the side to move **at the position the engine was given** (verified in `search.rs`: `score` is the root
negamax value, standard UCI convention; the static-eval convention was established and tested extensively earlier in
this project). Kiwipete's FEN has White to move; both numbers (static and depth-12) are White's perspective on the same
root position — **homogeneous, not a convention artifact.** So the anomaly is real: a pure 0.854 rescaling predicts a
depth-12 Y score around -105 (0.854 x -123); the actual depth-12 Y score is -269, opposite direction in ratio and 2.6x
the predicted magnitude. **Reading: the networks genuinely disagree at Kiwipete beyond any scale factor, and the search
amplifies that disagreement** (iterative deepening compounds a per-position eval difference across the tree) — this is
one noisy anecdote, consistent with but not proof of the residual found on the full 2,000-position set (Part 2).

## Part 4: reading, against the pre-registered table
Coefficient 1.1164 (outside 0.92-1.08) and R^2=0.969 (below the ~0.98 threshold for "almost all the difference"):
**third row — a scale disparity AND a real disagreement, both present.** Correcting `SCALE` is still warranted (it
recovers the part that is scale) but should not be expected to close most of the -50 Elo gap: the residual (149cp std,
20% of the signal) is the irreducible part this correction cannot touch.

## Part 5: correction, re-verified with the residual statistic added
`SCALE = 400 / 1.1164 = 358` (unchanged from this morning). Re-measured against X:

| indicator | corrected Y vs X |
|---|---|
| slope | 0.9991 |
| R^2 (uncentered) | 0.9689 (essentially unchanged) |
| residual std (cp) | 133.30 (down from 148.96, about -10%) |
| residual median \|resid\| (cp) | 61.15 |
| Spearman | 0.9823 (unchanged, as expected) |

R^2 barely moves and the residual only shrinks modestly: confirms the third-row reading quantitatively — rescaling
removes the *slope* but leaves nearly all of the *scatter*, because R^2 was already computed relative to the fitted
slope (it does not change when the slope itself is corrected to 1; what changes is that Y's raw values are now on X's
scale, and the residual in cp shrinks only because Y's overall magnitude shrunk toward X's).
