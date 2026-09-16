# Checksums — generation 3

- `shards.txt` — SHA-256 of every `gen3_shard_NNNNN_annotated.tsv` (54 files), with row count.
- `dataset.txt` — SHA-256 of the assembled dataset (`gen3_train.tsv`, `gen3_val.tsv`) and the binary conversion, with byte sizes.
- Network checksum: `nets/luna_gen3.nnue.sha256`.

**Verified in the opposite direction, 2026-09-16**: sampled 2 of the 54 shards (`00001`, `00054`), downloaded fresh from the OCI bucket (`gen3/` prefix), re-hashed — both match the values in `shards.txt` exactly. Note: the 54 annotated shards were only uploaded to the bucket as part of this same verification pass — the annotation run itself had a status-file watcher but no shard-upload watcher, so this third copy didn't exist until now.
