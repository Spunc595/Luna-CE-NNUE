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
  480. Total: 8.0 billion samples (8 epochs) over 1 billion distinct
  positions.

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
