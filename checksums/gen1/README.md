# Checksum — generazione 1

**TODO** — non calcolati in questa sessione. Oracle era occupata dalla
generazione 3 (regola zero di `repo-risultati.md`: niente carico I/O pesante
su una macchina impegnata), e calcolare SHA-256 su 46 shard + dataset
assemblato + binario è I/O non banale anche se non usa CPU di ricerca.

Da fare nella finestra fra la fine dell'annotazione della gen3 e l'inizio
del suo training:

1. SHA-256 di ogni `gen1_shard_NNNNN_annotated.tsv` (46 file), con il
   numero di righe accanto a ciascun hash.
2. SHA-256 di `gen1_train.tsv`, `gen1_val.tsv`.
3. SHA-256 dei file binari (`gen1_train_bin.*.npy`, `gen1_val_bin.*.npy`).
4. SHA-256 della rete esportata — **già disponibile**:
   `nets/luna_gen1.nnue.sha256` (calcolato localmente, file piccolo, non
   ha aspettato questa finestra).
5. Verifica nel verso opposto: che gli hash committati corrispondano ai
   file realmente presenti sul bucket OCI (non a una copia locale
   eventualmente diversa).
