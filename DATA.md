# Training data: source and license (v4.0.0 network)

This covers the network shipped in Luna CE v4.0.0 (the `phase-1` line, see
`results/`), not the separate `gen1`/`gen2`/`gen3` self-play line — see the
top of this repository's `README.md` for that distinction.

## Source, at two levels

1. **The underlying games**: Leela Chess Zero (Lc0) self-play games, from
   runs T77 and T79.
2. **The file actually used**: a filtered and converted copy of those games,
   in bullet's binary format, published by Linrock on Hugging Face
   (`linrock/bullet-training-data`, subset `S2`). The files used were
   `test77nov-unfilt-test79-maraprmay-v6-dd.skip-see-ge0.wdl-pdist.iter-1.bullet.bin.zst`
   in full, plus a prefix of `iter-2`, for 1 billion positions in total
   (about 914 million unique by exact board and side-to-move match, 91.4%;
   910.5 million if mirror images are merged — see `PROVENANCE.md` for the
   measurement).

These are two distinct facts. A license on (1) does not automatically mean a
license on (2): (2) is Linrock's own derived artifact, not a re-publication
of Lc0's files as such.

## License

- **Lc0's training data (level 1)**: the Lc0 project announced, in a blog
  post dated 2021-06-14, that its training-data collection is released
  under the **Open Database License 1.0** (database) and the **Database
  Contents License 1.0** (individual contents) —
  https://lczero.org/blog/2021/06/the-importance-of-open-data/, consulted
  2026-09-30. This is **not CC0** — ODbL carries share-alike terms for the
  database. The announcement is a 2021 policy statement for the data
  collection as a whole; it does not enumerate individual runs, and T77/T79
  postdate it. It is stated here as "announced", not independently verified
  run by run.
- **Linrock's converted file (level 2)**: the Hugging Face repository
  (`linrock/bullet-training-data`) has no dataset card and no license field
  — checked 2026-09-30. No license is declared for this specific conversion.
- **What is left open, stated as open**: whether the ODbL's share-alike
  terms extend to a model trained on the data, as opposed to a
  redistribution of the data itself, is not settled by the license text.
  This project makes no claim either way, in either direction.

## Credit

Not required by ODbL/DbCL in the way CC0's "no rights reserved" would make
moot, but given as correct practice: training data credit goes to the Lc0
project (self-play games, runs T77/T79) and to Linrock (filtering and
conversion to bullet's format, Hugging Face: `linrock/bullet-training-data`).

## What is published here

Only checksums and manifests of the trained network (see `PROVENANCE.md`)
— never the training data itself, and never a repackaging of Linrock's or
Lc0's files.
