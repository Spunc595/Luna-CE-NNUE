# Checksums — generation 1

- `shards.txt` — SHA-256 of every `gen1_shard_NNNNN_annotated.tsv` (46 files), with row count.
- `dataset.txt` — SHA-256 of the assembled dataset (`gen1_train.tsv`, `gen1_val.tsv`) and the binary conversion (`gen1_train_bin.*.npy`, `gen1_val_bin.*.npy`), with row counts (TSV) or byte sizes (binary).
- Network checksum: `nets/luna_gen1.nnue.sha256` (computed separately, alongside the file itself).

**Verified in the opposite direction, 2026-09-16**: sampled 2 of the 46 shards (`00001`, `00046`), downloaded fresh from the OCI bucket (`gen1/` prefix), re-hashed — both match the values in `shards.txt` exactly. The committed hashes describe what's actually stored, not a possibly-different local copy.
