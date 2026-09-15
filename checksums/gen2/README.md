# Checksum — generazione 2

**TODO** — stesso motivo di `checksums/gen1/README.md`: rimandato alla
finestra fra fine annotazione e inizio training della gen3, per non
caricare I/O su Oracle mentre è impegnata.

Da fare:

1. SHA-256 di ogni `gen2_shard_NNNNN_annotated.tsv` (53 file, tutti dalla
   corsa Oracle riconciliata — vedi `LINEAGE.md`), con il numero di righe
   accanto a ciascun hash.
2. SHA-256 di `gen2_train.tsv`, `gen2_val.tsv`.
3. SHA-256 dei file binari (`gen2_train_bin.*.npy`, `gen2_val_bin.*.npy`).
4. SHA-256 della rete esportata — **già disponibile**:
   `nets/luna_gen2.nnue.sha256`.
5. Verifica nel verso opposto: hash committati vs file realmente sul
   bucket OCI, prefisso `gen2/`.
