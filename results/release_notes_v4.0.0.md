## Luna CE v4.0.0

### A network trained by the author on public data

This is the first release whose embedded network (`resources/net.bin`) was
trained by the author, with his own training pipeline, on public Leela Chess
Zero data. It was trained with [bullet](https://github.com/jw1912/bullet) on
1 billion positions (about 914 million unique by exact board and
side-to-move match; 8 epochs), in the king-bucketed 768x4 mirrored
architecture ported from akimbo: 1024 hidden neurons, squared clipped ReLU.
The file format and size are unchanged.

The architecture and the AVX2 inference kernel are still akimbo's. Only the
trained weights changed.

### Training data

Leela Chess Zero self-play games (runs T77 and T79), as filtered and
converted to bullet's binary format by Linrock (Hugging Face:
linrock/bullet-training-data, subset S2; the conversion carries no separate
license declaration). The Lc0 project announced in June 2021 that its
training data is released under the Open Database License 1.0 and the
Database Contents License 1.0
(https://lczero.org/blog/2021/06/the-importance-of-open-data/). The network
weights are a trained model, not a redistribution of that data; how the
ODbL's share-alike terms apply to trained weights is not settled by the
license text, and this release makes no claim either way. Contains
information from the Leela Chess Zero training data, available under the
ODbL 1.0.

### Strength

Measured in Luna's own search against akimbo's network (the one shipped
through v3.1.7): 2,000 games at 10+0.1, same settings on both sides apart
from the network and its output scale.

**+492 =1018 −490, +0.3 ± 10.7 Elo (95% CI), no losses on time.**

The two networks are statistically indistinguishable: the interval runs from
roughly −10 to +11 Elo. This is a single training run, and v4.0.0 should be
expected to play at about the strength of v3.1.7, not stronger.

### Output scale: SCALE = 358

This training recipe (a WDL ramp) produces outputs about 1.116 times larger
than akimbo's network. The factor was measured twice, on networks of two
different architectures trained with the same recipe: 1.1156 and 1.1164.
`SCALE` is therefore 358 instead of 400 (400 / 1.1156). On the earlier
network, applying this correction was worth +15.9 Elo (SPRT, 1,443 games,
LOS 99.5%). It is applied in the engine rather than fixed in training; the
WDL ramp is to be revisited in the next training run.

### Measured along the way

All in Luna's own search, against akimbo's network unless stated:

- A first network trained by the author without king buckets lost about 50
  Elo (−49.8 ± 10.9, 2,000 games, material scale factor off on both sides)
  and was not shipped.
- Correcting its output scale: +15.9 ± 11.9 Elo (SPRT, 1,443 games).
- Adding the 768x4 king buckets: +36.9 ± 20.5 Elo over that network
  (SPRT, 529 games).
- The shipped network against akimbo's: +0.3 ± 10.7 Elo.

### Not yet measured

The material scaling factor introduced in v3.1.7 and the search's
centipawn-denominated margins were not re-tuned for this network; they stay
as they were in v3.1.7. Follow-up measurements are planned.

### License

From this version Luna is licensed under the MIT License. Releases through
v3.1.7 were GPLv3 and remain so as published. (A commit on `main` labelled
3.1.8 carried the license change; there was no 3.1.8 release.) See the
README for how the license applies to the code ported from akimbo and to the
network weights.

### Builds

Source code, an Android ARM64 build, and, new in this release, a Linux ARM64
build. The Linux ARM64 build was run and checked against the reference
results (same node counts and static evaluations as the build measured in
the match); x86_64 (AVX2) and aarch64 (NEON) also produce identical
evaluations and node counts on the test positions. The Android build was
compiled from the tagged source. Linux x86_64 and Windows builds are not
provided: compile from source with `cargo build --release`.

### Credits

Architecture, inference scheme and AVX2 kernel from
[akimbo](https://github.com/jw1912/akimbo) by Jamie Whiting (MIT), who also
wrote [bullet](https://github.com/jw1912/bullet), the trainer. Training data
from the Leela Chess Zero project, filtered and converted by Linrock.
Earlier versions of Luna, before the akimbo network, used SIMD inference
kernels contributed by Jim Ablett on the TalkChess forum, who also built and
shared cross-platform release binaries. See the README's Acknowledgments for
the full list.
