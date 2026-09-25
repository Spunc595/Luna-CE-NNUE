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
