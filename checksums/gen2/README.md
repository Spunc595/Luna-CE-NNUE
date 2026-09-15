# Checksums — generation 2

**TODO** — same reason as `checksums/gen1/README.md`: deferred to the
window between the end of gen3's annotation and the start of its
training, to avoid loading I/O onto Oracle while it's busy.

To do:

1. SHA-256 of every `gen2_shard_NNNNN_annotated.tsv` (53 files, all from
   the reconciled Oracle run — see `LINEAGE.md`), with the row count next
   to each hash.
2. SHA-256 of `gen2_train.tsv`, `gen2_val.tsv`.
3. SHA-256 of the binary files (`gen2_train_bin.*.npy`, `gen2_val_bin.*.npy`).
4. SHA-256 of the exported network — **already available**:
   `nets/luna_gen2.nnue.sha256`.
5. Verify the other direction too: committed hashes vs. the files
   actually on the OCI bucket, `gen2/` prefix.
