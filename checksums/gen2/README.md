# Checksums — generation 2

- `shards.txt` — SHA-256 of every `gen2_shard_NNNNN_annotated.tsv` (53 files, all from the reconciled single Oracle run — see `LINEAGE.md`), with row count.
- `dataset.txt` — SHA-256 of the assembled dataset (`gen2_train.tsv`, `gen2_val.tsv`) and the binary conversion, with row counts (TSV) or byte sizes (binary).
- Network checksum: `nets/luna_gen2.nnue.sha256`.

**Verified in the opposite direction, 2026-09-16**: sampled 2 of the 53 shards (`00027`, `00053`), downloaded fresh from the OCI bucket (`gen2/` prefix), re-hashed — both match the values in `shards.txt` exactly.
