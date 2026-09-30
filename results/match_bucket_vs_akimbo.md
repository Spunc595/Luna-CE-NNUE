# Direct match: bucket net (public Leela data, SCALE=358) vs akimbo (SCALE=400) — pre-registered 2026-09-29, before the run

## Part 0: binaries, no build needed
```
A = engines/bucket_scale358   sha256 125650daa2b0f77c37cd0a4551de5a4aefb0e41a77df0fd1406318765d80fd72   D3 active, SCALE=358
B = engines/net_base          sha256 f817914f552cfbe717793ec568e2f24ba7eddfa3190e6e74a3b8a84cc6d36d38   D3 active, SCALE=400
```
Both hashes match the values recorded in earlier reports exactly (B is the v3.1.7 tag base binary, identical to the
bot's own binary). Sanity gate: same fixed position (Kiwipete), static eval **-192 cp (A) vs -294 cp (B)** — differ, as
required.

## Part 1: why 358 vs 400 is not an asymmetry
`SCALE=400` is akimbo's own author's calibration for akimbo's own network, inherited by Luna along with the network —
an internally consistent original pair. Our network's training recipe (the WDL ramp) inflates its raw outputs by a
factor of **1.116, measured twice on two different architectures** (the no-bucket 8-epoch net and this bucket net,
independently, both landing on ~1.116 against the SAME akimbo reference). `SCALE=358` restores the same eval-to-margin
relationship akimbo's own 400 restores for its network; it is not a concession, it is the correction the coefficient
(measured AGAINST akimbo, akimbo = 1.000 by construction) calls for.

**Residual uncertainty, stated, not hidden:** the optimal `SCALE` for akimbo's OWN network run through Luna's search
(not just its bare inference) has never been searched for independently; if it is not exactly 400, this match favours
whichever side is farther from ITS true optimum by less. The argument above (400 is the author's own calibration) is
an argument, not a measurement.

## Part 2: the match (fixed length, no bound, no futility, no early stop for any reason)
```
games       2,000 (1,000 rounds x 2)
tc          10+0.1, concurrency 2
openings    8moves_v3.pgn, same seed convention as the rest of the campaign
bot         off for the whole match
validity    one game lost on time invalidates the match
results     fixed_bucket358_vs_akimbo400_tc10
expected    ~8h at ~250 games/h; 95% CI at 2,000 games ~ +-10.5 Elo
```

## Part 3: shipping rule, fixed BEFORE the run
```
Elo >= 0       : SHIP. The network is at least equal, nothing to discuss.
-10 < Elo < 0  : SHIP. The CI contains parity, and owning the network is worth those few Elo: from that point on every
                 future network is measured against OUR OWN, not a frozen external artifact. Without that starting
                 point there is no iteration.
Elo <= -10     : DO NOT SHIP. The next generation (more distinct data, buckets, GPU) is the path; this network stays
                 the internal yardstick.
```
Not renegotiated after the number is seen.

## Part 4: chain vs direct measurement, to check the method
The chained estimate (D3's own +44.8, the net8ep SPRT's -53.9, the no-D3 match's -49.8, additivity assumed) gave
**-1.1 +/- 36 Elo** (see `results/match_no_d3.md`). If the direct measurement lands far outside that interval, the
information is not just about this network — it is that chaining Elo differences this way does not work reliably in
this system, and other derived estimates used in this campaign (D3's transfer estimate, prior comparisons against
3.1.6) deserve more suspicion than they have been given.

## RESULT (2026-09-29 17:48:52 -> 2026-09-30 01:56:41 UTC, 8h08m, 2,000 games)
```
A (bucket, SCALE=358)   +492 =1018 -490   score 0.5005
B (akimbo, SCALE=400)
Elo(A-B)                +0.3 +/- 10.7   (95% CI)
draw ratio               0.5090
games lost on time       0   (match VALID)
rate                      2000 games / 488 min = ~246 games/h, consistent with the campaign
```
SE-model check: draw ratio 0.509 (close to the model's 0.52 assumption) -> predicted CI ~+-10.5, observed +-10.7. Consistent.

**Decision, per the rule fixed before the run: Elo >= 0 -> SHIP.** The network trained by the author on public Leela data, with king
buckets, at the correct scale, is statistically indistinguishable from akimbo's (+0.3 +/- 10.7, essentially the center
of the CI). Not a win, not a loss: parity, which per Part 3 is worth shipping on its own — every future network is now
measured against OUR OWN, not a frozen external artifact.

## Part 4: chain vs direct measurement
Chained estimate: **-1.1 +/- 36** (`results/match_no_d3.md`, additivity assumed across D3's own SPRT, the net8ep
SPRT, and the no-D3 match). Direct measurement: **+0.3 +/- 10.7**. The direct number falls almost exactly at the
center of the chained interval (1.4 Elo from the chain's point estimate) — **the chain was right**, even though its
own uncertainty was far too wide to decide anything by itself. This is one data point in favour of the chaining
method in this system, not a general validation of every chained estimate used earlier (D3's transfer, the 3.1.6
comparisons): those remain unverified by a direct match and should keep the same "derived, not measured" caveat they
already carry.
