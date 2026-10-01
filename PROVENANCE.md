# Network provenance (v4.0.0)

Covers the network shipped as `resources/net.bin` in Luna CE v4.0.0 — the
`phase-1` line (see `results/`), trained by the author, with his own
training pipeline, on public Leela Chess Zero data (source and license:
`DATA.md`).

## File

- sha256: `ecd8a917fd8d6f1e900f64ec1721494178cd610ab5f02b4c91c0ca1950446940`
- size: 6,297,664 bytes

## Trainer

[bullet](https://github.com/jw1912/bullet), fork
`AleksPeshkov/bullet`, branch `cpu`, commit `6a4f4fb`. Training script:
`pipeline/bullet_pilot/luna_pilot_buckets.rs` in this repository.

## Architecture and configuration

- Input: `ChessBucketsMirrored`, 4 king buckets (32-entry table, rank-major,
  file a-d folded: king a1/b1 -> 0, c1/d1 -> 1, rank2 -> 2, ranks3-8 -> 3),
  horizontally mirrored — matches `BUCKETS` in `rust-chess/src/nnue.rs`,
  cross-checked against bullet's own code via `pipeline/bullet_pilot/bucket_probe.rs`
  (0/35,278 mismatches).
- Network: `(768 x 4 -> 1024) x 2 -> 1`, squared clipped ReLU (SCReLU),
  dual-perspective (side-to-move / not-to-move concatenated before the
  output layer).
- Quantisation: QA=255, QB=64 (same constants in `rust-chess/src/nnue.rs`).
- `eval_scale`: 400.0 (bullet-side constant; the engine-side `SCALE=358`
  correction is applied downstream, not at training — see the release
  notes).
- Optimiser: AdamW (bullet's built-in; weight-clipping/decay left at
  bullet's defaults — not overridden in the training script, exact default
  values not recorded here).
- LR schedule: cosine decay, `initial_lr = 0.0004`, `final_lr = 0.0004/40`
  (`= 1e-5`), over the full run.
- WDL schedule: cosine ramp, `start = 0.0`, `end = 0.1` over the full run
  (bullet's convention: blends toward the discrete game result, not the
  search eval — this ramp is the confirmed source of the ~1.116x output
  inflation corrected by `SCALE=358`, see the release notes).
- Batch size: 4,096. Batches per superbatch: 4,069 (measured,
  `Positions / Superbatch: 16,666,624` from the run preamble). Superbatches:
  480. Total: 8.0 billion samples (8 epochs) over 1 billion positions —
  about 914 million unique by exact board and side-to-move match (91.4%),
  910.5 million if mirror images are merged (91.0%). See "Position-uniqueness
  measurement" below.

## Position-uniqueness measurement (2026-10-01)

Measured directly on the training files still present on the Oracle volume
(`/mnt/nnue-data`), read-only, not re-derived from memory or the training
logs' "distinct" language (which asserted a count without having measured
one — see `LESSONS.md`).

**Format and identity key**: `bulletformat` 1.8.0's `MarlinFormat` (32-byte
record: `occ: u64, pcs: [u8;16], stm_enp: u8, hfm: u8, fmc: u16, score: i16,
result: u8, extra: u8` — layout read from the crate's own
`src/chess/marlin.rs`, not reconstructed). The identity key used is `occ +
pcs + stm` (the side-to-move bit, bit 7 of `stm_enp`) only — board and side
to move, as specified. **Deliberately excludes**: the en-passant bits (the
other 7 bits of `stm_enp`) and the halfmove/fullmove counters, score and
result fields, none of which are position identity. **Limit of the
measurement, not of the method**: this record format does not encode
castling rights at all, so two positions identical in board and side to
move but differing only in castling rights are counted as one.

**Mirror-canonical key**: the same fields, additionally folding the
horizontal file mirror (`sq ^= 7`, the same mirror `ChessBucketsMirrored`
applies) and taking the lexicographically smaller of the raw and mirrored
key, so a position and its mirror image collapse to one entry.

**Method**: stream-read each file, hash each record's key with 64-bit
FNV-1a, collect into an in-memory `Vec<u64>` (8 GB peak for the 1-billion-
record file, against 21 GB free RAM — comfortable; no disk-based sort was
needed), `sort_unstable`, count runs of equal values. Validated on a 10
-million-record sample before the full run.

**Collision risk**: with a 64-bit hash and N records, P(>=1 collision) ~
`1 - exp(-N^2 / 2^65)`. At N=1e9: ~2.7% chance of at least one collision
somewhere, expected count ~0.027 (i.e. under 1 expected, across the entire
file) — negligible against the tens of millions of real duplicates found.
At N=2.5e8: ~0.17% chance, expected ~0.0017.

**Results**:

| File | Used for | Records | Unique (raw) | Unique (mirror-canonical) | Time (raw / mirror) |
|---|---|---|---|---|---|
| `s2_1G_mix.bin` | shipped network + no-bucket comparison | 1,000,000,000 | 914,416,689 (91.44%) | 910,466,531 (91.05%) | 1221.2s / 1232.9s |
| `s2_250M_mix.bin` | phase-3 "A-mix" | 250,000,000 | 243,748,129 (97.50%) | 242,961,864 (97.18%) | 331.6s / 72.6s |
| `s2_250M_mix2.bin` | phase-3 "A-mix-2" | 250,000,000 | 243,748,129 (97.50%) | 242,961,864 (97.18%) | 331.6s / 72.5s |

`s2_250M_mix.bin` and `s2_250M_mix2.bin` give byte-identical unique counts —
expected, since both are the same underlying 250M positions under two
different shuffles (`runAmix.sh`/`runAmix2.sh`), and the method is
order-independent. This is a consistency check on the method, not a new
fact about the data.

**What is not computable from current data**: `s2_1G_mix.bin` was built by
`prep1G.sh` interleaving 4 parts drawn from `iter-1` (used whole) and a
prefix of `iter-2`; those intermediate per-source files
(`g1/part_0.bin`...`part_3.bin`) and the raw `iter-1`/`iter-2` downloads
were deleted by the prep script after interleaving, before this
measurement was conceived, and are no longer on Oracle. The overlap
between `iter-1` and `iter-2` specifically, and the per-source contribution
to `s2_1G_mix.bin`, cannot be recovered from the files that remain — doing
so would require re-downloading the ~9 GB source files from Hugging Face,
which was not done.

**Source files, identified without re-downloading** (Hugging Face's file
API exposes LFS object metadata — name, size, sha256 — without transferring
the file content):

| File (`linrock/bullet-training-data`, subset S2) | Size (compressed, as hosted) | sha256 (LFS object) |
|---|---|---|
| `test77nov-unfilt-test79-maraprmay-v6-dd.skip-see-ge0.wdl-pdist.iter-1.bullet.bin.zst` | 9,007,693,288 bytes | `f02a0dc3da8e294f32514b599135e39685d4d80672bbf0371fe81cab7a0aa84d` |
| `test77nov-unfilt-test79-maraprmay-v6-dd.skip-see-ge0.wdl-pdist.iter-2.bullet.bin.zst` | 9,003,836,115 bytes | `9493a253194a7042ad398aaaed9e2cb7759aaeb5cb41214022a83fd43d8e19fe` |

These are the sizes/hashes of the `.zst`-compressed files as published, not
of the decompressed `.bin` content actually streamed into training (that
form no longer exists locally to hash).

## Machine and duration

Oracle Cloud Ampere (aarch64) instance, CPU training (no GPU), 30h27m wall
clock (`ck_8ep_buckets/luna_pilot_buckets-480`, final checkpoint).

## What is not reproducible

- The batch-mixing order is clock-seeded; a re-run with the same data and
  config will not produce byte-identical weights.
- This is a single training run, not a statistical population of runs.

## Output-scale measurement

The trained network's raw output is larger than akimbo's own network by a
factor measured at 1.1156 (this network) and 1.1164 (a no-bucket network
trained with the same recipe), both against the same akimbo reference on
the same `eval_set.epd` (seed 7) population — see `results/scale_hypothesis_v2.md`
and `results/bucket_experiment_part4_report.md`. `SCALE = 400/1.1156 ≈ 358`.

## Quantisation gates (checked before shipping)

- Round-trip (export -> reload -> re-export) byte-identical: confirmed.
- Rust probe (`bucket_probe.rs`) cross-check against the real bullet
  feature-indexing code: 0 mismatches.
- Max `|output_weight|` observed: 127 (SIMD-safe limit is 128, see
  `rust-chess/src/nnue.rs`).
- Accumulator range observed on the quantisation gate set: +5.125 / −9.465.

## Verification against the shipped binary

Node counts and static evaluations identical across x86_64 (AVX2), aarch64
(NEON) and scalar-fallback builds on the fixed test-position set — see
`rust-chess`'s release gates (G2/G3/G4 in the v4.0.0 release record) for the
exact procedure and results.
