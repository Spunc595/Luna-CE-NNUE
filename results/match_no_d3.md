# Fixed-length match: the two networks with D3 disabled on both sides (pre-registered 2026-09-27, before the run)

## Why
The rejected SPRT (-53.9 Elo, `results/sprt_net8ep_preregistration.md`) had D3 (the material scale) active on both sides, but D3 is a
correction tuned on akimbo's network; it interacts with the network rather than cancelling. This match removes D3 from both engines so the
only difference left is the network itself.

## Construction (gates already run, all passed — `net_stage/nod3.log` on Oracle)
- One tree extracted from the v3.1.7 tag sources, one patch to `src/nnue.rs` (`mat_factor` forced to 1024 instead of
  `700 + material / 32`, i.e. `scaled == raw`), applied once; X built from it (akimbo's network + D3 off); Y = a copy of the same tree
  with `resources/net.bin` replaced by `step_8ep.nnue`, rebuilt.
- Tree diff X vs the D3-on akimbo build (`engines/net_base`): differs in EXACTLY `src/nnue.rs` (same original `resources/net.bin`) — pass.
- Tree diff X vs Y: differs in EXACTLY `resources/net.bin` — pass. Y's `resources/net.bin` is byte-identical to `step_8ep.nnue` (`cmp`).
- Binaries X and Y: sha256 differ (`27bc265b76...` vs a second hash logged on Oracle) — pass.
- **D3-disabled gate**, X (D3 off) vs `engines/net_base` (same network, D3 ON): low-material position (one rook, kings only) eval ratio
  base/X = **0.7024** (D3's own formula: material 650 -> `(700+650/32)/1024` ≈ 0.702); full-material (start position) ratio = **0.9452**
  (formula ≈ 0.948). Both close to the formula's prediction and the low-material ratio well below the full-material one, as the
  material-dependent shape requires: D3 is off in X and was on in net_base, cleanly. (Y was not tested separately: it shares the
  identical `nnue.rs` patch with X, verified by the tree diff.)

## Match (fixed length, no bound, no futility, no early stop for any reason)
```
A               nod3_Y = step_8ep.nnue, D3 disabled
B               nod3_X = akimbo's network, D3 disabled
games           2,000 (1,000 rounds x 2)
tc              10+0.1, concurrency 2, Hash 64, Threads 1
openings/seed   8moves_v3.pgn, srand 1207 (same as the rejected match, for comparability)
validity        one game lost on time invalidates the match
bot             off for the whole match, restarted at the end
expected time   ~8 hours at ~244 games/hour
expected CI     ±10.5 Elo at 2,000 games (draw ratio ~0.49-0.56)
```

## Reading, fixed before the run
- **~-10 or better**: the network is close to fine; most of the -54 Elo was the D3/akimbo-tuning interaction. The real work becomes
  retuning D3 for the new network, not more data or buckets.
- **~-50**: the network is genuinely weak here; D3 is not the story, and the data/capacity questions (phase 3/4 reports) stand.
- **in between**: both contribute; D3 needs retuning regardless, before any future network is judged.

**Derived quantity (X, this match's result for the new-net side) with its explicit limit**: assuming D3's effect is additive,
`D3(new net) ~= 44.8 - 54 - X = -9.2 - X` in Elo. This assumes additivity (untested) and inherits the -53.9 +/- 26.6 Elo uncertainty of the
rejected match (roughly +/-29 on the derived number): usable only to tell "D3 helps the new net" from "it doesn't", not as a value. If it
matters, the direct measurement is a separate match (new net with D3 vs new net without D3), same cost, no additivity assumption.

## Explicit limit of this match
This measures network quality in an engine WITHOUT the correction. It does not directly predict the shipped configuration, where D3 is
present. That is the price of isolating the variable, stated rather than left implicit.

## RESULT (2026-09-27, 07:26:26 -> 15:14:23 UTC, 2,000 games)
```
A (new net, D3 off)     +373 =969 -658   score 0.4288
B (akimbo, D3 off)
Elo(A-B)                -49.8 +/- 10.9   (95% CI)
draw ratio               0.4845
games lost on time       0   (match VALID)
```
SE-model check: predicted CI at N=2,000 with this draw ratio is close to the observed +/-10.9 (the model's own table used
d~0.52; here d=0.484, giving a very similar prediction) — consistent with earlier verifications on D4/G2b.

**By the pre-registered reading (three thresholds):** -49.8 falls in the "~-50" bracket, not "~-10 or better" and not
clearly "in between". **The new network is genuinely weaker here; D3 is not the main story.** Isolating D3 recovered
about 4 Elo (-53.9 with the interaction -> -49.8 without it) out of 54, not "up to 45 of the 54" as the upper bound
allowed for — the interaction turned out to be small, not large.

**Derived quantity, with its explicit limit (Part 3):** assuming additivity, `D3(new net) ~= 44.8 - 53.9 - (-49.8) = +40.7`
Elo, close to D3's own +44.8 on akimbo's network — i.e., on this reading D3 would transfer to the new network about as
well as it works on akimbo's. This number inherits the wide uncertainty of both inputs (roughly +/-29, per the
pre-registered caveat) AND assumes additivity, which is untested; it says "D3 likely still helps with this network", not
a value to use. If it matters, the direct measurement (new net with D3 vs new net without D3, same cost) is the way to get it
without the additivity assumption.

**Consequence, per Part 3 of the pre-registration and Part 8 of the original SPRT plan:** the data/capacity questions
stand. The network trained on 1 G distinct positions (8 epochs) is not close to shipping quality, D3 retuning would not
close most of the gap, and the next step is more/better data (or the capacity question, king buckets) — not a D3
retune as the primary lever. A D3 retune for the new network may still be worth a small, separate measurement later
(the derived +40.7 estimate suggests it is not obviously wasted), but it is not where the gap lives.

## Explicit limit, restated
This measures network quality without the correction. The shipped configuration (with D3) was measured directly by the
earlier SPRT (-53.9 +/- 26.6): the two numbers together (-49.8 without D3, -53.9 with D3, on the same net) are the actual
evidence about D3's effect on this net, not the additivity formula above, which is a cruder read of the same two numbers.
