# SPRT: does SCALE=358 recover Elo over SCALE=400 for the new net? RESULT (2026-09-27, D3 active both sides)

Pre-registered in `scala-della-rete.md`/`misura-scala-v2.md` Part 6: A = new net (`step_8ep.nnue`) with `SCALE=358`
(the scale-hypothesis correction, `results/scale_hypothesis_v2.md`), B = same net with `SCALE=400` (default, this is
`engines/net_patch`, the exact binary used in the rejected SPRT and the no-D3 match). D3 active on both (unlike the
no-D3 isolation match): SCALE and D3 are independent axes, and this asks whether the correction helps under the
shipped configuration.

**Note: this SPRT ran twice.** The first launch (15:49-15:50 UTC, 2 games) used the wrong bounds (`elo0=-5 elo1=5`,
a copy-paste error in the queue script calling the wrong match-runner variant); caught by reading the preamble
immediately after start, killed within a minute, results moved to
`sprt_scale358_on_scale400newnet_WRONGBOUNDS_ABANDONED_2games` (kept, not deleted), script fixed, relaunched with the
correct preamble confirmed (`elo0=0 elo1=10`). See `PROTOCOLLO.md`.

```
elo0=0 elo1=10 alpha=beta=0.05, cap 8,000 games, tc 10+0.1, concurrency 2, bot off, seed 1301
```

## Result
```
games              1,443 (started 15:51:21, ended 21:37:48 UTC, ~5h46m, ~250 games/h)
A (SCALE=358)      +353 =803 -287   score 0.5229
Elo(A-B)           +15.9 +/- 11.9   (95% CI)
LOS                99.5%
draw ratio         0.5565
games lost on time 0   (match VALID)
SPRT               llr 2.94, ubound 2.94 -> H1 ACCEPTED
```

## Reading
The correction recovers **+15.9 Elo**, solidly (LOS 99.5%, upper bound crossed). Consistent with the pre-registered
third-row reading from `scale_hypothesis_v2.md` (R^2=0.969, not the ~0.98 needed for "almost all the difference"):
the correction recovers a real, measurable chunk, not the whole -49.8 Elo gap found against akimbo without D3.
Remaining question, not measured here: how much of the -49.8 no-D3 gap this +15.9 accounts for is not a direct
subtraction (different comparison: this match has D3 on both sides and compares SCALE within the new net; the no-D3
match compared networks). What it does establish: **`SCALE=358` is a better setting than `SCALE=400` for this
network, measured, not assumed.**

## Not yet decided
- Whether/when `SCALE=358` (or a value re-derived on a larger position sample) gets adopted anywhere — this is a
  measurement, not a release.
- The residual disagreement (R^2 0.969, not 1.00) that the correction does not touch: unexplained, not investigated
  further here.
- The original data/capacity questions (`results/nnue_phase3_report.md`, `nnue_phase4_report.md`) stand: this network
  is still well short of the embedded net's quality by the measures gathered so far.
