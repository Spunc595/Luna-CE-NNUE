# Checksums — generation 1

**TODO** — not computed in this session. Oracle was busy running
generation 3 (rule zero: no heavy I/O load on a machine that's occupied),
and hashing 46 shards plus the assembled
dataset plus the binary files is non-trivial I/O even though it uses no
search CPU.

To do in the window between the end of gen3's annotation and the start of
its training:

1. SHA-256 of every `gen1_shard_NNNNN_annotated.tsv` (46 files), with the
   row count next to each hash.
2. SHA-256 of `gen1_train.tsv`, `gen1_val.tsv`.
3. SHA-256 of the binary files (`gen1_train_bin.*.npy`, `gen1_val_bin.*.npy`).
4. SHA-256 of the exported network — **already available**:
   `nets/luna_gen1.nnue.sha256` (computed locally, small file, didn't wait
   for this window).
5. Verify the other direction too: that the committed hashes match the
   files actually on the OCI bucket (not a possibly-different local
   copy).
