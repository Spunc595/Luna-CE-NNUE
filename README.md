# luna-nnue

Provenienza dati, filiera e risultati per le reti NNUE di
[Luna Chess Engine](https://github.com/Spunc595/Luna-Chess-Engine).
Repository separato dal motore: qui vive la storia di *come* ogni rete è
stata generata e misurata, non il codice del motore stesso.

Pubblico. I numeri qui dentro non fanno sempre una bella figura (la rete
conforme sta sotto gen0, che sta sotto akimbo) — pubblicarli è la scelta,
non un compromesso: un registro che mostra anche i numeri scomodi vale più
di qualunque dichiarazione di provenienza non verificabile.

## Da dove iniziare

- **[`LINEAGE.md`](LINEAGE.md)** — da chi/cosa discende ogni rete
  presentata. La domanda più importante che ci verrà fatta.
- **[`COMPLIANCE.md`](COMPLIANCE.md)** — la dichiarazione di conformità
  TCEC NNUE, fase per fase, con l'elenco esplicito di ogni punto in cui
  Stockfish compare nel repository e perché non è una violazione.
- **[`RESULTS.md`](RESULTS.md)** — le tabelle. Ogni numero è ricalcolabile
  dai `.csv` in `results/`.

## Struttura

```
LINEAGE.md           il grafo di ascendenza delle reti
COMPLIANCE.md         la dichiarazione TCEC, punto per punto
RESULTS.md            le tabelle
results/
  eval_set.epd         l'insieme di posizioni di valutazione condiviso
  *.csv                valutazioni grezze, una riga per posizione
  scripts/             gli script che le producono e calcolano il ρ
pipeline/
  generate/ annotate/ dataset/ train/ measure/    codice, nessun dato
manifests/ gen1/ gen2/ gen3/                       manifesti per shard
nets/                 luna_gen1.nnue, luna_gen2.nnue (+ .sha256)
checksums/ gen1/ gen2/                             hash dei dataset
non_conforme/          gen0: cos'è, perché non conta, script isolato
```

## Come si riproduce una generazione

1. `pipeline/generate/` — self-play (`run_selfplay_genN.sh`) + estrazione
   posizioni + costruzione manifesto, guidato da `generate_shards_genN.sh`
   (assert aritmetico sul dimensionamento dei pool prima di partire).
2. `pipeline/annotate/` — annotazione incrementale a inseguimento
   (`annotate_incremental_genN*.py`), dedup globale via `global_seen.bin`,
   correzione WDL delle partite troncate.
3. `pipeline/dataset/` — `build_training_dataset_genN.py` assembla
   train/val (split per partita), `convert_to_binary.py` converte in
   formato memory-mapped per il training.
4. `pipeline/train/` — `train.py`, con i tre numeri di pre-volo stampati
   automaticamente prima di ogni run come controllo di sanità.
5. `pipeline/measure/` — gate sul maestro prima di ogni nuova generazione,
   misure Spearman statiche e in ricerca per `RESULTS.md`.

I dati stessi (shard, dataset assemblati, checkpoint) non sono in questo
repository — vivono su Oracle Cloud e su un bucket OCI. Questo repository
contiene il codice per riprodurli e le misure per verificarli.

## Regola di conformità

Tutti i dati di addestramento di gen1 in poi vengono dalla ricerca e/o
valutazione del motore stesso — mai da Stockfish, mai da un motore terzo.
Dettagli completi, incluso perché il nome "Stockfish" compare comunque nel
codice (come strumento di misura offline, non come sorgente di etichette),
in `COMPLIANCE.md`.
