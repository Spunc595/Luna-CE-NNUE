# NNUE phase 3 / 3b: scale ladder and repetition vs fresh data (2026-09-25)

Static Spearman against Stockfish 18 depth 12 on the full set (434,897 positions), engine v3.1.6 (raw). Not playing strength;
no game was played. Recipe for every row: (768hm -> 1024)x2 -> 1 SCReLU, no buckets, from scratch, S2 only, AdamW, lr cosine
4e-4 -> 1e-5, WDL fraction ramp 0.0 -> 0.1 (bullet convention), eval_scale 400, batch 4096, 60 superbatches. Every net went
through the converter's round-trip (2,000 positions, 0 differences).

| step | distinct positions | samples seen | epochs | machine, time | Spearman (95% CI) |
|---|---|---|---|---|---|
| pilot, WDL constant 0.1 | 4.09 M | 36.9 M | ~9 | PC, 10.6 min | 0.8687 (0.8674-0.8700) |
| 37M (final recipe) | 4.09 M | 36.9 M | ~9 | PC, 13.2 min | 0.8686 (0.8674-0.8696) |
| B | 31.25 M (first 1.0 GB of A's data) | 250 M | ~8 | Oracle, 32.5 min | 0.8847 (0.8835-0.8856) |
| A | 250 M | 250 M | 1 | Oracle, 33.6 min | 0.8857 (0.8847-0.8867) |
| reference: embedded (akimbo) | | | | | 0.9036 |
| reference: gen3 | | | | | 0.8253 |

**A vs B: 0.0010 apart** (the CIs overlap at their edges; the threshold the plan set was 0.005). Same samples, same time, same
machine; only the number of distinct positions differs (8x). Reading by the plan's rule: B is close to A, so at this scale the
repetition costs almost nothing measurable. Limits of that reading: one run each (no seed variance measured), one scale (250 M
samples; the gap may open at larger totals), and the loader does not shuffle (below), so "distinct" here means distinct
positions in file order.

Gap covered: 0.8687 -> 0.8857 between 37 M and 250 M samples (+0.0170); 0.0179 remains to the embedded net. 1 G and 4 G
were not run (disk: 32 / 128 GB).

## bullet does not shuffle, and neither do the data files
`DirectSequentialDataLoader` (`crates/bullet_lib/src/value/loader/direct.rs:126`, `buf[..len].chunks(batch_size)`) yields
consecutive records; the 256 MB buffer (line 62) is a read buffer. bullet's docs list "Shuffle data files" as a prior step
(`docs/2-getting-started.md:26`). Measured on the first 200,000 records of the S2 sample: 9.6% of adjacent pairs differ on <= 4
occupied squares, against 0.02% of random pairs (mean popcount of the occupancy xor: 17.4 vs 23.6): batches are runs from
few games. It applies equally to every row above, so it does not show in the comparison between rows; whether shuffling would
raise all of them was not measured. (`bullet_utils` has a shuffle tool; it needs disk for the shuffled copy.)

## Artifacts
Nets in `C:\Users\danie\Desktop\NNUE\pilot\` (`step_37M.nnue`, `step_250M.nnue`, `step_B.nnue`): measurement candidates,
not to be played. Oracle: `~/nnue_pilot/data/` (8 GB + 1 GB), checkpoints `ck_250M`, `ck_B`.

## 3c: shuffling (B vs B-mix) and the 100 GB volume
Tool: `bullet-utils shuffle -i -o -m` (bullet's own, `crates/bullet_utils/src/shuffle.rs`; in-memory Fisher-Yates over 32-byte
records when the file fits `-m`, otherwise split into `./tmp` parts + interleave; seed = clock, so not reproducible).
B-mix = the same 1.0 GB as B, shuffled (24.7 s), same recipe, same 250 M samples, Oracle.

| | order | Spearman (95% CI) |
|---|---|---|
| B | file order | 0.8847 (0.8835-0.8856) |
| B-mix | shuffled | **0.8858** (0.8848-0.8868) |

Difference +0.0011, CIs overlapping; one run each. At this scale (31 M positions, 8 epochs) shuffling made no measurable
difference. Not shown by this: whether it matters for 250 M+ distinct positions (A-mix, running).

Volume: 100 GB block volume attached as `/dev/sdb` (stable path `/dev/oracleoci/oraclevda`), ext4, label `nnuedata`, mounted at
`/mnt/nnue-data` via UUID in `/etc/fstab` with `nofail,noatime,x-systemd.device-timeout=10` (backup `/etc/fstab.bak-before-nnue`);
verified by umount + `mount -a` and `findmnt --verify` (no errors). Not verified: a real reboot.

## 3d notes recorded before the 1 G step
- **Different shuffle types.** A-mix: one global Fisher-Yates in memory over all 8 GB (`bullet-utils shuffle`, clock seed, NOT
  reproducible; both permutations `s2_250M_mix.bin` and `s2_250M_mix2.bin` are kept for that reason). The 1 G data: **four parts of
  250 M shuffled separately** (`chunkshuf.py`, numpy, seeds `20260925 + k`, reproducible) and then randomly interleaved by
  `bullet-utils interleave` (clock seed for the interleave itself, so the final file is not reproducible either, the parts are).
  This is not a global permutation: two records of the same part are never adjacent in the output, and the order stays stratified
  by part. **The 1 G step therefore differs from A-mix in two things, more samples and a different shuffle quality.** If it
  disappoints, this is a ready candidate explanation, not a tested one; B vs B-mix (+0.0011) suggests shuffle quality matters little
  at that scale.
- **Disk guard (`prep1G.sh` line 10):** a **precondition** evaluated once before anything is written (`avail >= 70 GB`, else it
  writes `abort_prep1G` and exits), not a check during the run. There is no check during the run; the run writes 64 GB into 82 GB
  free (about 74 GB when it starts, after the second A-mix shuffle file exists), leaving about 10 GB.
- **If it stops halfway:** no resume logic. Parts already finished stay on disk as complete files; the interrupted one may be a
  partial file. Re-running redoes everything (re-download, same seeds) and overwrites (truncates) `part_*.bin` and the output; it does
  not reuse them and deletes nothing. `prep1G_done` is written only after the output size check (32,000,000,000 bytes); training on
  the 1 G data must be gated on that marker.
- **Paired bootstrap B vs B-mix:** the 10,000-resample run ran 28 min and exited with an error I did not capture (no output); it was
  replaced by a 2,000-resample run (~0.5 s per resample, about 17 min).

## 3d results: the floor
Same 8 GB, same recipe, same 250 M samples, two different global shuffles (clock seeds, both files kept):

| run | Spearman (95% CI) |
|---|---|
| A (file order) | 0.8857 (0.8847-0.8867) |
| A-mix | 0.8870 (0.8859-0.8880) |
| A-mix-2 | 0.8865 (0.8855-0.8875) |

**Floor (same configuration, different randomness): |A-mix - A-mix-2| = 0.0004** (paired bootstrap of the difference, 300 resamples:
-0.0004, CI [-0.0006, -0.0003]). One pair only, so this is one sample of the floor, not its distribution.
Reading against it (paired bootstrap of the differences, same eval set): B-mix - B = +0.0011 (2,000 resamples, CI [+0.0009, +0.0013]);
mean(A-mix, A-mix-2) - A = +0.0011. Both are about 2.5-3x the single floor measurement and both point the same way (shuffled >
file order), at two scales. That is consistent with a small real shuffling effect of about +0.001, not established by one floor pair.
Any step-to-step gain below ~0.001 cannot be told from the floor.

## 3d: 1 G preparation failure (13:53 UTC) and restart
`prep1G.sh` aborted: the plain `curl | zstd` stream ended after 8,002,469,888 decompressed bytes (part_0, 250 M records, complete;
chunk 1 got 2.4 MB). Cause of the drop not captured (curl ran with `-s`, zstd stderr discarded). `part_0.bin` is valid and untouched.
Restart as `prep1G_v2.sh`: resumable range downloader `dl.py` (re-requests from the last byte on any error, logs retries), part_0
skipped rather than rewritten (`chunkshuf2.py`, same seeds `20260925 + k`), guard precondition 60 GB (3 parts + output + margin).
Note: part_0 is the same first 250 M positions of S2 iter-1 that A used, so the 1 G set contains A's data.

## dl.py: reader-closed vs network error (fix, 2026-09-25)
`dl.py` treated `BrokenPipe` (the consumer closed the pipe: normal end) as a network error and retried it 30 times (31 misleading log
lines after the 1 G cut). Now: a write failure on stdout is handled in its own branch (`READER CLOSED`, one line, exit 0, no retry;
`OSError` with `EPIPE`, and on Windows winerror 232/109/EINVAL, recognised; stdout redirected to the null device before exit so Python
does not print its own "BrokenPipeError ignored"); network failures log `NETWORK ERROR ... retry n from byte p`; success ends with
`DONE: n file(s), B bytes transferred, r network retries`. Found while testing: `http.client` `read(amt)` returns `b''` on a premature
close instead of raising, so a cut connection used to resume silently with no log line at all; it now raises `ConnectionError` and is
logged as a network error. Tests (`test_dl.py`, local Range server with fault injection): 1) reader closes early -> exactly one
`READER CLOSED` line, 0 network errors, exit 0; 2) the old script (`dl_v1_defective.py`) on the same case retries a closed pipe as if it
were the network (proves test 1 can see the defect); 3) a real cut (server hangs up at 40% twice) -> 2 `NETWORK ERROR` lines, byte-exact
resume (sha256 equal), `DONE ... 2 network retries`; 4) plain transfer -> `DONE ... 0 network retries`. All pass on Windows (Python 3.14)
and on Oracle (Python 3.12, run with `nice -n 19` while the 1 G step was training; superbatch time unchanged at ~150 s).
