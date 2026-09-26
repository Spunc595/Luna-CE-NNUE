# While the SPRT runs: rate, SE model, quantisation hypothesis (2026-09-26)

## 1. Where the 267 games/hour came from
Read from the match logs (`~/sprt2/results/*`, `header.txt` start/end, game counts from the PGN/report, `TimeControl` tag in the PGN,
`params.txt`). Every match, earlier ones and the current one, ran with `concurrency 2`, Hash 64, Threads 1.

| match | tc | games | wall time | games/hour |
|---|---|---|---|---|
| D3 | 10+0.1 | 390 | 1 h 31 m | 257 |
| G5 | 10+0.1 | 961 | 3 h 50 m 32 s | **250** |
| D4 | 10+0.1 | 2,202 | 8 h 43 m | 253 |
| G2b | 10+0.1 | 2,405 | 9 h 37 m | 250 |
| control base-base | 10+0.1 | 400 | 1 h 33 m (13:38:05 -> 15:11:24 UTC) | 257 |
| net8ep (running) | **20+0.2** | 80 at 19:16 UTC | 40 min | ~120 |

Outcome: the third one in the plan. **All earlier matches were at 10+0.1 and ran at ~250/h with concurrency 2; the doubling of the time
control halves the rate**, and the current match has `concurrency 2` as well. The "267/h" was (12,000 games / 45 h) a rounded estimate that
matches the measured 10+0.1 rate (~250/h, i.e. 48 h for 12,000), and it was applied to a 20+0.2 match. Consequences: the 8,000-game cap is
about 62 h; and **Elo of the net-swap SPRT (20+0.2) and of the search tests (10+0.1) are not directly comparable**.
Correction to the note in the request: the control match did not run 13:36-17:00 UTC at 118 games/h. 13:36-17:00 was the window in which the
bot's journal was checked for silence; the match itself ended at 15:11 UTC (400 games in 93 min = 257/h). No experiment with a doubled
`concurrency` was made, none is proposed for a running match. Rule written in `PROTOCOLLO.md` section 6.

## 2. SE model, checked on real logs
`SE(Elo) ~ 695 * sqrt((1-d)/4) / sqrt(N)`; with d = 0.52: 240/sqrt(N), CI95 ~ +-470/sqrt(N).
D4: N = 2,202, draw ratio 0.5595 -> model CI +-9.6 with the real draw ratio (+-10.0 with 0.52); observed +-9.6, Elo +0.3 at the stop
(rule: Elo + CI < 10). G2b: N = 2,405, draw ratio 0.5543 -> model +-9.3; observed +-9.3, Elo +0.4. The model is exact with the real draw
ratio and about 4% conservative with 0.52. The stop thresholds the model predicted (Elo < 0.0 at 2,202 and < +0.4 at 2,405 for elo1 = 10) match the
stops (0.3 with CI 9.6 -> 9.9 < 10). The pairing of openings could not be checked: cutechess reports an unpaired CI. At elo1 = +5 the
futility stop needs Elo < -5.5 (2,000 games), -2.4 (4,000), -0.3 (8,000), +1.3 (16,000); the 8,000-game cap gives +-5.3 Elo.

## 3. Hypothesis 3: does the quantisation cost rank quality?
Float forward pass (numpy, `pipeline/measure/float_vs_quantised.py`) of the bullet checkpoint `luna_pilot-480/raw.bin` with bullet's own
Chess768hm mapping (no `sq ^ 7`: the weights are bullet's), float SCReLU `clamp(x,0,1)^2`, two perspectives, output x 400, on all 434,897 rows.

Gate (float vs the outputs Luna itself produced, engine v3.1.6 raw): median |diff| **8.4 cp** (median |eval| 473 cp), 95th percentile 25 cp,
max 157 cp, mean signed -0.2 cp; on the first 2,000 rows 8.6 / 24.6 / 63.7 / -0.6. Close, unbiased, no gross error: the numpy
implementation is not visibly wrong (a wrong mapping produced differences of ~1,800 cp).

| | Spearman vs SF18 |
|---|---|
| quantised (Luna, v3.1.6 raw) | 0.9026 |
| float | 0.9025 |
| float - quantised | -0.0001, paired CI [-0.0002, -0.0001] (300 resamples) |

Reading, by the pre-registered rule: float - quantised is within ~0.001, **the quantisation costs nothing measurable; hypothesis 3
falls**, hypotheses 1 (few distinct data) and 2 (capacity) remain. Note on the rule's third branch ("float lower than quantised = the numpy
implementation is wrong"): the difference is -0.0001, two orders of magnitude below the resolution; I read it as noise of the two rank
computations (quantised outputs are integers with many ties, float ones are not) and not as evidence against the implementation, which
passed the position-by-position gate. This is a judgement, stated as such.
Caveat on scope: this says the *ranking* survives quantisation. It says nothing about the 52 output weights at the clip (that is a
property of training, tested by the float net itself: if the clip cost anything the float net, which also had the clip, would not show it;
an unclipped float net would need a separate run).

## 4. King buckets (hypothesis 2)
The training example uses **768 inputs, no king buckets**: `pipeline/bullet_pilot/luna_pilot.rs` line 38 `.inputs(Chess768hm)` and
line 41 `builder.new_affine("l0", 768, HIDDEN)`. Luna's file has 768x4 rows only because the converter replicates the same 768 rows
into the 4 buckets. So the capacity gap to akimbo's 768x4 net is real for the trained parameters (768x1024 vs 3,072x1024 distinct).

## Corrections (2026-09-26, later the same day)
- Section 3: the reading of the third branch was incomplete. The rule had no tolerance band relative to the measured floor; read with a band,
  -0.0001 against a floor of 0.0004 is nothing to explain. And **my explanation was wrong**: ties in the integer outputs predict the opposite
  direction (more ties lower rho, so the quantised net would score lower, not higher). What is consistent is that rounding is a deterministic
  perturbation that fell marginally favourably on this set. A paired CI that excludes zero does not make a difference below the floor
  significant. Rule added to `PROTOCOLLO.md`.
- Section 1: the earlier remark that "118/h" was a misreading stands, and it was mine (the 13:36-17:00 window was the bot-silence check window).
- Section 4 (buckets): akimbo (4x the input parameters) is ahead by only 0.0011 on Spearman, the resolution threshold, so on this measure the
  buckets are worth at most that; whether they are worth more in strength without showing in rank is open (rank statistic, cf. D1 and Kiwipete).
  With four buckets each row block trains on about a quarter of the data (250 M per bucket at 1 G distinct): testing four buckets on the current
  1 G would be an ambiguous experiment (a loss would not tell "buckets do not help" from "not enough data for buckets"); not to be run in isolation.

## L3 patch (conditional on the SPRT accepting the net): what the bucket index does, read from the code (nothing implemented)
`src/nnue.rs` at `main`: `get_bucket` (line 105) is used in exactly two places. (1) `feature_index` -> `get_base_index` (line 139): it picks the
768-row block (`768 * bucket + ...`) of the weight table. (2) `same_feature_mapping` (line 124, called from `board.rs` lines 521, 648, 759): it
decides whether a king move needs a refresh of that perspective's accumulator half (a bucket change forces one; so does a mirror flip).
Nothing else reads the bucket. With four identical copies of the rows (which is what the converter writes for a 768-input net), (1) selects
between equal rows, and (2) only changes how often a refresh happens: a refresh recomputes the same sum the incremental updates maintain (i16
wrapping adds are exact modular arithmetic), so the accumulator, and therefore the evaluation and the whole search, are identical. The
mirror (`perspective_flip`) must stay: it changes the square index. So collapsing to 768 rows removes only the bucket term; expected effect:
evaluation bit-identical, node counts identical, fewer refreshes when a king crosses a bucket boundary, table 1.57 MB instead of 6.29 MB.
Gate to use (not statistical): eval byte-for-byte equal on the 2,000-position set plus positions with the king in all four buckets (both
sides, after castling on both wings); one difference stops everything. Then NPS with the floor of the same run, then SPRT like any speed patch.
The 39.3% and 220 ns figures quoted in the request were not re-measured here.

## Blocks A and C: already closed in `BENCHMARKS.md`, not pending
Block A (padded accumulator cells 4 KB -> 16 KB): run and closed on 2026-09-23 (padded probe -9.8% / -10.8% vs `main`, -14.9% / -8.7% vs
`acc-a-stack`, floor 1.3% / 5.4%), section "Block A, decisive test", and the "Part 5" note repeats "Nothing pending". Block C: the question
"which variant is today's code" was answered (both `search.rs:586` and `:603` were tried and discarded) and the grouped patch
`c-improving-and-nmp-bonus` (`b76ae6b`) already exists. Step 3 of the ordering in the request therefore has nothing to run on the PC; if a
rerun is wanted it is a new decision, not the pending one.
