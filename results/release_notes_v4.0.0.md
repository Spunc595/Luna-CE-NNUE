## Luna CE v4.0.0 (draft — NOT to be published by the assistant; Daniele publishes from the GitHub web UI)

**<DA CONFERMARE — training data license, see below, flagged here so it is not missed.>**

### What's new

The first version of Luna that runs on a network trained on its own dataset and its own training pipeline, not
akimbo's. The architecture, the on-disk network format, and the AVX2/NEON inference kernels are still akimbo's
(Jamie Whiting, MIT).

### The result, with its real meaning

Measured in the engine itself, against akimbo's own network: **+0.3 +/- 10.7 Elo** (2,000 games, 10+0.1, 95% CI,
zero games lost on time). **Statistically indistinguishable from akimbo's network. Not "stronger," not "at least
equal" — parity, with an interval of roughly (-10, +11).** This is one training run, not a statistical population of
runs.

### `SCALE = 358`

The network's training recipe (a WDL-fraction ramp in the `bullet` trainer, from 0.0 to 0.1) inflates its raw output
relative to akimbo's network by a factor measured at ~1.116, independently on two different network architectures
(1.1156 and 1.1164 against the same akimbo reference). `SCALE` is lowered from 400 to 358 (`400 / 1.1156`) to correct
for it — applied downstream in the engine, not fixed at the training source, because retraining was out of scope for
this release. Measured to be worth **+15.9 +/- 11.9 Elo** in SPRT (1,443 games, LOS 99.5%) over the uncorrected 400.
This constant is expected to disappear, not just change, once a future network is trained with a ramp that does not
need the correction.

### License

**As of this version, Luna CE is MIT-licensed** (previously GPLv3; see the relicensing commit, `68fb919`, and the
LICENSE file). Every version through v3.1.7 was published under the GPLv3, as released, and remains available
under those original terms; a 3.1.8 was prepared with the relicensing alone but never published as a release
(no tag). v4.0.0 is the first tagged release under the new license.

### Training data: source and license — **<DA CONFERMARE>**

The network is trained on `S2` from `linrock/bullet-training-data` (Hugging Face), Leela Chess Zero self-play data
converted to `bullet`'s own binary format. **The Hugging Face repository has no dataset card and its license field is
empty: no license is declared for this dataset.** This was found and recorded during phase-1 research
(`nnue_phase1_research.md`, section 1a) and has not been independently re-verified since. State the source as above;
**do not state a license** until this is confirmed one way or another — this line is deliberately left marked rather
than guessed.

### Measured and not shipped, this cycle

- The no-bucket network (same recipe, no king buckets), measured directly against akimbo with D3 disabled (isolating
  the network from a correction tuned for akimbo's own network): **-53.9 +/- 26.6 Elo**. Not shipped.
- The scale correction alone (`SCALE=358` vs the default 400, same no-bucket network, D3 active): **+15.9 +/- 11.9
  Elo**. Folded into this release.
- The 4-king-bucket architecture vs the no-bucket network, both at `SCALE=358`: **+36.9 +/- 20.5 Elo**. This is the
  architecture shipped in v4.0.0.

### Credits

NNUE architecture, quantisation scheme and AVX2 inference kernel: [akimbo](https://github.com/jw1912/akimbo) by
Jamie Whiting, MIT licensed. NEON kernel for AArch64: a port of the same scheme, written by the author with AI
assistance. Training: [bullet](https://github.com/jw1912/bullet) by Jamie Whiting. Earlier versions of Luna, before
the akimbo network, used SIMD inference kernels contributed by Jim Ablett on the TalkChess forum (July 2026), who
also built and shared cross-platform release binaries for the engine — unchanged credit, corrected to no longer
cover the current kernels (see commit `cf908aa`/`a122b16`).

### Platforms

Source, Android ARM64, and (new in this release) Linux ARM64 — built and verified natively on the same
aarch64 machine the measured match ran on. **Linux x86_64 is not included in this release**: no working
cross-compilation or execution path was available (no WSL distribution installed, no musl linker, Oracle is
aarch64-only) to both build and verify it, and an unverified binary is not shipped.

| file | sha256 |
|---|---|
| `luna-v4.0.0-source.tar` | `e489f68cbfc97fc00c6cf8203951e6b3aef4edbb7f98c2e8ac4ce1d148218c02` |
| `luna-v4.0.0-android-arm64` | `72caa67615d3741be085dc16712f78340618f67c220c9a2e68c06b38d421d9ab` |
| `luna-v4.0.0-linux-aarch64` | `2de537190dfee6c0f7b24ce4c8d4305f1c74ca05b6e9f74e07335c5dd7eacb0d` |

The Android binary was built and its bytes hashed; it was **not executed on an Android device** (none available in
this session) — verified only by the same gates (G2/G3/G7-equivalent) as the Linux aarch64 build, on the source tree
it shares, not by running on the target OS itself.
