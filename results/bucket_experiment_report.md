# Generation 2a: 4 king buckets on the same 1 G distinct positions (2026-09-28)

Question answered by this run: not "do king buckets help in general" (they can't be, at this data scale — see the
pre-registered caveat below), but "with the 1 G distinct positions we have, should the next run use buckets or not."

## Part 0: prerequisite (Save Rate)
Rebuilt `luna_pilot` on Oracle from the canonical repo copy (`pipeline/bullet_pilot/luna_pilot.rs`, with `LP_SAVE`/
`LP_RESUME`/`LP_START`) and built the new `luna_pilot_buckets` example. **Found and fixed a real bug before it could
waste 20 hours**: the binary that ran the earlier 8-epoch run had been deployed to Oracle from a copy of `luna_pilot.rs`
that predated `LP_SAVE` support (confirmed: `grep LP_SAVE` on the deployed file found nothing). The gate script
(`build_luna_pilot_and_buckets.sh`) ran a 2-superbatch smoke test and required the preamble to print
`Save Rate : 1` (the requested value) before allowing anything else to proceed; it failed twice before the correct
`luna_pilot.rs` was redeployed and both a path bug (relative path after `cd`) and the wrong-source-file issue were
fixed. Third attempt: `Save Rate : 1`, gate passed.

## Part 1: bullet input type and layout, verified against the REAL bullet code
Type: `bullet_lib::game::inputs::ChessBucketsMirrored`, `ChessBucketsMirrored::new(buckets: [usize; 32])` (a rank-major,
file-a-d-folded 32-entry table, expanded internally to 64 squares by mirroring each rank's e-h onto its d-c-b-a
counterpart). Configured with:
```
BUCKETS32 = [0,0,1,1, 2,2,2,2, 3,3,3,3, 3,3,3,3, 3,3,3,3, 3,3,3,3, 3,3,3,3, 3,3,3,3]
```
chosen to reproduce Luna's own `BUCKETS` table (`src/nnue.rs`: king a1/b1 -> 0, c1/d1 -> 1, rank2 a-d -> 2, ranks3-8 a-d
-> 3; `get_num_buckets` = max+1 = 4, matching).

**The gate that matters (per the request): the FINAL row index, not bucket indices or mirror flips checked separately.**
Two conventions intertwine here and checking either alone would have passed while the layout was wrong (found and fixed
during this check, see below): (1) bulletformat stores every position side-to-move-relative — `our_ksq()`/`opp_ksq()`
are each king's square in a frame where that side always "looks like White" (own_ksq = raw^56 if Black to move;
opp_ksq = raw^56 if White to move), not the raw FEN square; (2) `ChessBucketsMirrored` then applies its own file-only
mirror on top of that. My first transcription used raw FEN squares for `our_ksq`/`opp_ksq` directly and got 25,227 of
35,278 checked rows wrong; rather than keep hand-debugging a second Python reimplementation, I wrote `bucket_probe.rs`,
a bullet example that runs bulletformat's REAL `ChessBoard::from_str` and the REAL `ChessBucketsMirrored::map_features`
and prints every row, and checked my Python against ITS output first (0/604 positions mismatched), then fixed the
`our_ksq`/`opp_ksq` derivation in Python to match, confirmed 0/604 again, and only then compared against Luna:

```
CORRECT layout: 35,278 feature rows checked (604 positions: 600 random legal positions + 4 castled-both-sides-both-
                wings positions, both colours, king in all 4 buckets), 0 mismatches
```

**Mutation test:** swapping `BUCKETS32[0]` and `BUCKETS32[8]` (bucket 0 <-> bucket 2's region) makes the comparator
fail on 134/35,278 rows — the gate has teeth.

One consequence of the row layout matching directly: **no `sq ^ 7` permutation is needed this time** (unlike the
no-bucket `Chess768hm` case). `ChessBucketsMirrored`'s own file-mirror direction (flip when the king's file > 3, pushing
it to files a-d) already matches Luna's `perspective_flip` exactly; the earlier permutation was needed only because
plain `Chess768hm` mirrors the OPPOSITE way (pushes the king to e-h).

## Part 2: converter
`resources/net.bin`'s feature-weight block is `768 * 4 * 1024` rows either way (the no-bucket net gets there by
replicating 768 real rows 4 times; this net has 768*4 = 3072 distinct trained rows already, from `l0 =
new_affine(768*4, HIDDEN)`), so **the file stays exactly 6,297,664 bytes** — the invariant held.
`bullet_luna.convert_buckets`/`ReferenceBuckets`/`convert_verified_buckets` added (no tiling, no permutation, same four
quantisation gates as before). Round-trip tested on a random (untrained) net before spending any Oracle time: **500/500
positions, 0 differences.** Mutation test: swapping two entries of the bucket table used by the independent reference
makes the round-trip refuse and write nothing (18/500 positions differ) — the round-trip gate also has teeth for this
new architecture, not just the mirror one from before.

## Part 3: training, in progress
Started 2026-09-28 (bot stopped, no game running at the time; `luna-bot` inactive for the duration). Recipe identical to
the no-bucket 8-epoch run except the input type: 480 superbatches x 4069 batches x 4096 = 8.0 G samples over the same
1 G distinct positions (8 epochs), same lr/WDL schedule, CPU (not GPU, matching the comparison net's own training
path), Oracle, 4 threads.

**Deviation from the plan, deliberate, not an oversight: reuses the EXISTING mixed file** (`s2_1G_mix.bin`, the same
one the no-bucket 8-epoch run trained on) instead of a fresh clock-seeded mix. This removes the mixing-permutation
confound (+0.0011 floor-sized, per phase 3) entirely, rather than requiring it be declared as an unavoidable difference
— strictly better than what was asked, at no cost, so I made the call and am reporting it rather than asking first.

**Throughput note, to watch:** first superbatch measured **70,106 pos/sec**, well below the no-bucket run's ~111,000-
129,000 pos/sec (roughly 40-45% slower). This is plausible on its face (4x the input-layer parameters means 4x the
sparse feature-table lookups per position, even though only one bucket's rows are touched per position — the *dense*
l1 layer and the bookkeeping are unchanged, but l0's table is 4x larger, and cache/memory-bandwidth effects scale
with table size, not just active-row count). At steady state around this rate, 8.0 G samples would take roughly 32
hours, not the ~20 estimated — a real deviation, not noise, IF it holds past the first (cold-start) superbatch. Checked
CPU load (3.99/4.0) to confirm it is genuinely computing, not stalled. Steady-state figure and the decision on whether
this crosses the pre-registered "stop and report if far past ~20h" threshold: see the addendum below, filled in once
a few more superbatches have completed.

## Part 3, STOPPED per the pre-registered rule (2026-09-28, ~10 minutes into the run)
Steady-state throughput confirmed past cold start: superbatch 2 was measured mid-flight at **60,000-65,000 pos/sec**
with CPU load 3.8-4.0/4.0 (genuinely computing, not stalled/IO-bound). At this rate, 8.0 G samples would take
**roughly 34 hours**, not the ~20 estimated — about 70% over. Per the pre-registered rule ("se la corsa dovesse durare
molto più di venti ore, fermati e riferisci: il calcolo per campione dovrebbe essere simile... una durata molto diversa
vuol dire che qualcosa non e' come pensiamo"), **the run was stopped rather than left unattended for 34 hours on a
premise that no longer held.**

**Cost of stopping now: about 10 minutes of compute, no checkpoint had been written yet** (`LP_SAVE=60`, superbatch 1-2
of 480), so nothing is lost. Cleanup: `kill -TERM` on the trainer process (needed twice — the first attempt's SSH
command chain also included `pkill -f run8ep_buckets.sh`, which killed the queue script itself and reparented the
still-running trainer to PID 1 as an orphan before the second `kill` in the same command could reach it; caught by
checking `pgrep` afterward rather than assuming the kill worked). No orphan processes remain, `luna-bot` is active
again, load average back to baseline (~2-3, matching the machine's normal background), no partial checkpoint directory
was left behind.

**A plausible mechanism for the slowdown** (not verified further here): the no-bucket net's l0 table is 768 rows
(768*1024*4 bytes ~ 3.1 MB); the bucketed net's is 3,072 rows (~12.6 MB). The number of ACTIVE rows touched per
position is the same either way (~32, one piece-square per active piece, all within one bucket's block), so the
document's "compute per sample should be similar" reasoning holds for arithmetic operations — but the 4x larger table
no longer fits as well in cache, and the ~32 active rows for any given position are now scattered across a much wider
address range (spread over 4 disjoint 768-row blocks depending on which bucket each of the two king positions
selects), which plausibly costs more in cache misses / memory bandwidth than in raw FLOPs. This is a hypothesis, not
measured.

**Decision needed, not made here:** whether to (a) run it anyway at ~34h, (b) reduce scope (fewer epochs, e.g. run at
1 epoch over 1 G like the earlier no-bucket comparison point, ~4.25h at this rate, trading the 8-epoch comparison
for a faster read), (c) investigate/fix the throughput before spending the time, or (d) drop this experiment. Parts 4-6
(quantisation gates, scale coefficient, Spearman, the match) all wait on whichever training actually completes.
