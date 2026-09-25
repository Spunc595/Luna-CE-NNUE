# NNUE phase 2: can this machine train? (2026-09-25)

Numbers and arithmetic only; no decision is taken here. Everything below was **observed** unless marked *inferred*.
No file was deleted, no existing dataset touched; the only download was a 64 MB prefix of one S2 file (the same kind of
probe as phase 1).

## 1. Samples per second

**bullet.** Upstream `jw1912/bullet` (HEAD `10e7e82`, 2026-09-24) has **no CPU backend** (features `cuda`, `rocm`, `metal`
only). The CPU path is in Petrel's fork `AleksPeshkov/bullet`, branch `cpu`, commit **`6a4f4fb`** (2026-08-31): crate
`acyclib` ("Contains the CPU backend") and a declared cargo feature `cpu` in `bullet_lib` (build:
`cargo build -r --example <name> --features cpu --no-default-features`; docs: "do not use CPU backend if you have a GPU").
Built with rustc 1.92 on the PC (76 s) and 1.97.1 on Oracle (22 s). I did not open the CPU kernels, so whether they use explicit SIMD is not established here; `-C target-cpu=native` on the PC made no measurable difference
(see below). Model measured: `(768hm -> 1024)x2 -> 1` SCReLU, batch 4096, AdamW, real S2 data (4,091,904 positions, prefix
of `S2 ... iter-1`), 4 to 6 superbatches after warm-up, "pos/sec" as printed by bullet (total, not per replica).

| machine | replicas (`use_threads`) | pos/s (successive superbatches) |
|---|---|---|
| PC, Ryzen 3 3200U (2 cores / 4 threads, laptop) | 4 | 57,786 60,124 54,276 59,818 |
| PC | **2** | 59,317 57,942 60,888 59,728 |
| PC | 1 | 47,127 47,752 47,903 42,157 |
| PC, `target-cpu=native` | 4 | 55,174 59,599 58,522 57,141 |
| PC, `target-cpu=native` | 2 | 58,666 62,079 63,782 63,240 |
| **Oracle**, aarch64, 4 cores (bot stopped) | **4** | 129,321 124,569 131,215 129,497 |
| Oracle | 2 | 72,529 72,944 74,921 73,781 |
| Oracle | 1 | 39,982 39,510 40,545 40,127 |

Figures used below: **PC 60,000 pos/s**, **Oracle 129,000 pos/s**. What they do not include: the cost of streaming and
decompressing real data (this sample was already in memory and cycled), and thermal throttling of the laptop over hours.

| positions seen | PC at 60k/s | Oracle at 129k/s |
|---|---|---|
| 24 billion (Petrel 4.0) | 400,000 s = 111 h = **4.6 days** | 186,047 s = 51.7 h = **2.2 days** |
| 6 billion | 100,000 s = 27.8 h = **1.2 days** | 46,512 s = 12.9 h = **0.54 days** |
| 1 billion | 16,667 s = **4.6 h** | 7,752 s = **2.2 h** |

By the document's reading rule (days = in-house), all three sizes land in "days or less" **on compute**. Three costs the
arithmetic above does not cover, each observed:

- **Disk.** bullet's `DirectSequentialDataLoader` reads uncompressed 32-byte records: 1 B positions = 32 GB, 6 B = 192 GB,
  24 B = 768 GB uncompressed. **The PC has 2.3 GB free of 238 GB. Oracle has 11 GB free of 45 GB.** Neither can hold even
  1 B positions today. (*Inferred*: a streaming decompressor feeding the loader was not tried.)
- **Oracle is also the bot's host.** At 129k pos/s all 4 cores are used; the bot must be stopped for the whole run (2.2 days
  for 24 B). I stopped it for about 2.5 minutes between games for this measurement (no game in progress, restarted, active).
- **Download.** One S1 file is ~20 GB compressed, two S2 files ~18 GB; the 24 B schedule reads the whole 108 GB S2 set
  (*inferred* from Petrel's script).

## 2. Lambda direction (bullet)

`crates/bullet_lib/src/value.rs:115` at bullet `10e7e82`: `targets[0] = blend * result + (1. - blend) * score;`.
bullet's lambda is the **WDL (game result) fraction**. Luna's pipeline lambda (weight of the evaluation) = 1 - bullet's:
Luna lambda 0.7 = bullet 0.3; Petrel's 0.0 -> 0.1 = Luna 1.0 -> 0.9. (The fork's `ConstantWDL`/`CosineDecayWDL` feed the same
`blend`.)

## 3. Pilot, end to end

Recipe: `(768hm -> 1024)x2 -> 1`, no buckets, SCReLU, AdamW, cosine lr 4e-4 -> 1e-5, WDL 0.1 constant, `eval_scale` 400
(Luna's inference SCALE), batch 4096, 60 superbatches x 150 batches = 36.9 M samples (about 9 passes over the 4.09 M
positions), 10 min 34 s on the PC. Final loss 0.0125 (it overfits a 4 M sample; this is a plumbing test, not a net).

| step | result |
|---|---|
| bullet trains, checkpoint written (`raw.bin`, f32) | OK (3,158,020 bytes = 789,505 f32, layout feature-major, `l1w` = stm then ntm) |
| convert to Luna `net.bin` (`convert_bullet_to_luna.py`) | OK after **one break point**, below |
| size | 6,297,664 bytes (exactly what `parse` expects) |
| saturation of the four tensors | 0 |
| SIMD gate (255 x max\|output weight\| <= 32767) | max\|w\| = 36, 255 x 36 = 9,180: OK |
| accumulator bound (bias + 32 largest positives) | max +1,821 / min -2,118 vs +/-32,767: OK |
| round-trip, independent numpy reference vs Luna `eval`, 2,000 positions | **0 differences**, max\|diff\| = 0 (`roundtrip.py`) |
| engine loads it as `luna.nnue` next to the exe | "loaded (3072 input features, 4 king buckets, 1024 hidden)" |
| engine searches | depth 14 from the start position, no panic, `e2e4` |
| static quality, first 40,000 SF18 rows, v3.1.6 raw | Spearman 0.8662 (a subset: not comparable to the full-set 0.9036 of the embedded net) |

**Break point found (format mismatch between bullet and Luna).** First round-trip: 1,999 of 2,000 positions differed
(max 1,794 cp). Cause: **the horizontal mirroring goes the opposite way.** bullet's `Chess768hm` (`chess768hm.rs`,
`hm_s = if our_ksq & 4 != 0 { 0 } else { 7 }`) flips the file when the king is on a-d, putting it on e-h; Luna
(`nnue.rs`, `perspective_flip`, `own_ksq % 8 > 3`) flips when the king is on e-h, putting it on a-d. Exact fix in the
converter: Luna's row (piece, sq) = bullet's row (piece, sq ^ 7). After it the round-trip is exact. No net trained with
`Chess768hm` and exported without this permutation would have crashed or been rejected by any gate: it would have loaded and
evaluated differently from its training (up to 1,794 cp on the 2,000 positions); I did not test how it plays.
Also required and done: the 768 rows are replicated into Luna's 4 king buckets (no-bucket net), and a training-time
`eval_scale` of 400 is used so that Luna's `SCALE = 400` inference needs no rescaling (Petrel trains at 800: an 800 net
would need its output weights and bias doubled).

Not done / out of scope this round: bucketed nets, a real-data run, anything that needs the big download.

## 4. The measuring instrument: Stockfish 18 depth-12 evaluation set

`stockfish_position_evaluations.csv` (Kaggle, CC BY-SA 4.0) arrived; 468,234 rows, 14,560 duplicate FENs dropped, **434,897
centipawn rows**, 18,777 mate rows excluded from the correlation.

**Point of view verified on the data** (rows with >= 400 cp material imbalance): Black to move, evaluation agrees with
"side to move is ahead" 0.9632 and with "White is ahead" 0.0368; White to move 0.9604. **The column is side-to-move
relative.**

| net | v3.1.6 (raw) | 95% CI | v3.1.7 (material scale) | 95% CI |
|---|---|---|---|---|
| embedded (akimbo) | **0.9036** | 0.9026-0.9045 | 0.9029 | 0.9019-0.9038 |
| gen1 | 0.7696 | 0.7679-0.7711 | 0.7669 | 0.7653-0.7684 |
| gen2 | 0.8062 | 0.8045-0.8076 | 0.8050 | 0.8035-0.8067 |
| gen3 | 0.8253 | 0.8240-0.8268 | 0.8246 | 0.8230-0.8259 |

Standard deviation of Spearman over random subsets (v3.1.6 raw; range = smallest to largest over the four nets): n = 2,000: 0.009-0.012; 5,000: 0.005-0.008; 10,000: 0.003-0.005; 20,000: 0.002-0.004;
50,000: 0.0016-0.0027; 100,000: 0.0008-0.0013. Full-set bootstrap CI half-width: about 0.001.
Gaps between the nets (0.90 / 0.83 / 0.81 / 0.77) are 10x to 100x the CI; a subset of 20,000 resolves them (sd 0.003)
and one of 10,000 too, but not differences below about 0.01 between two nets. The full set takes ~80 s per (engine, net)
pair. Positions come from games and puzzles and are correlated, so the naive 1/sqrt(n) understates the error; the sd
above is measured, not assumed. *Not chosen here: the subset size is the user's call; the figures above are the input.*

On the new scale the ranking is unchanged from the old 2,000-position set (embedded > gen3 > gen2 > gen1) and the
material scale (v3.1.7) moves the static Spearman by -0.0006 to -0.0027 (embedded -0.0007, about the CI half-width of 0.001). I did not investigate why it moves in that direction.

## Files

`pipeline/bullet_pilot/` (`luna_pilot.rs`, `convert_bullet_to_luna.py`, `roundtrip.py`, `getprefix.py`,
`cargo_example_entry.patch` for the fork at `6a4f4fb`); `results/sf18_evalset/` (JSON, log). Pilot net
`C:\Users\danie\Desktop\NNUE\pilot\luna_pilot.nnue` sha256 `23e5812e2c26a8a035b88b634a39a0ed310bb3f4adfa2f38d3debc1c51923b82`
(a plumbing test, not to be played or published).

## Confounder to keep in mind before any S1-vs-S2 comparison (recorded 2026-09-25, before it is needed)

The evaluation set is labelled by **Stockfish 18** (depth 12). S1 is data **generated by Stockfish** (5k-node games, labels
from Stockfish searches); S2 is Leela data. A network trained on S1 is therefore **favoured on this metric by construction**:
it is fitted to labels of the same kind as the reference, whether or not it plays better. Today's comparisons are fair
because the pilots and the embedded network (akimbo) are both trained on Leela-derived data. The gen1/gen2/gen3 nets are the
opposite case: their labels are Stockfish 17.1 (depth 8), so this metric already favours them, and they still score below the
Leela-trained nets. **Consequence for S1 vs S2:**
a higher Spearman for S1 on this set is not evidence of a better network. The arbiter has to be the SPRT (or an evaluation
against a label source independent of both, e.g. game results), never this correlation alone.
