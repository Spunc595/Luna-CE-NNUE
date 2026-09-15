# TCEC NNUE compliance

**Regola**: tutti i dati di addestramento devono essere generati dal codice
di ricerca e/o valutazione del motore stesso. Nessuna fonte esterna
(Stockfish, altri motori, database di partite umane) può contribuire
un'etichetta o una posizione ai dati di addestramento di una rete
presentata.

## Come viene rispettata, fase per fase

**Aperture (self-play)**: generate da Luna stesso (mosse casuali filtrate
per posizione "non decisa" secondo la valutazione — classica per gen1,
rete gen1 per gen2, rete gen2 per gen3 — della stessa rete che poi giocherà
il self-play). Per il pool di finali: posizioni reali da
`lichess_db_puzzle.csv`, filtrate solo per numero di pezzi e squilibrio
materiale — nessuna valutazione motore coinvolta nella selezione, quindi
nessuna fonte di etichette esterna nemmeno lì.

**Self-play**: partite Luna-contro-Luna, valutazione della propria rete
(o PST classica per gen1), mai Stockfish, mai akimbo come giocatore.

**Etichette**: la valutazione (`eval_cp`) e la mossa migliore (`bestmove`)
di ogni posizione vengono dalla RICERCA di Luna stesso (`go nodes N`) con
la rete maestro della generazione corrente — mai da Stockfish, mai da
un motore terzo.

**Risoluzione WDL delle partite troncate**: usa l'`eval_cp` già scritto da
Luna nello stesso passaggio di annotazione — non chiama alcun motore
esterno.

## La trappola del grep, disinnescata

Chi cerca "stockfish" nel repository lo **troverà**, in `results/scripts/`.
Questo è un elenco esplicito di ogni file e ogni occorrenza, con il motivo,
perché la ricerca non basti a concludere una violazione.

| File | Cosa fa | Perché è lecito |
|---|---|---|
| `results/scripts/measure_static_vs_stockfish.py` | Confronta la valutazione statica dei nostri motori con l'eval Stockfish già presente in `results/eval_set.epd`, calcola Spearman | **Strumento di misura**: legge un valore Stockfish già registrato, non lo genera, non scrive nulla nei dati di addestramento |
| `results/scripts/measure_search_vs_stockfish.py` | Stessa cosa, ma con la ricerca del motore (`go nodes N`) invece della valutazione statica | Stesso motivo |
| `pipeline/measure/measure_master_spearman.py` | Misura, sullo stesso principio, il maestro di una generazione (rete precedente, in ricerca) contro Stockfish — usato per il gate "punto 1" prima di ogni nuova generazione | Stesso motivo: strumento di misura offline, non entra mai nella catena di generazione/annotazione |
| `pipeline/measure/measure_eval_error.py` | Confronto statico generico fra due motori e Stockfish, usato storicamente per gen0/gen1 | Stesso motivo |
| `RUNBOOK.md`, `RESULTS.md` (prosa) | Discutono questi confronti | Documentazione dei risultati, non codice della filiera dati |

**Distinzione applicata ovunque in questo repository**: uno **strumento di
misura** legge un valore di riferimento già esistente per calcolare una
metrica offline (Spearman, MAE) e non scrive mai in un file che poi entra
nella catena di addestramento. Una **sorgente di etichette** scrive
`eval_cp`/`bestmove`/WDL in un file che il training legge. Gli script sopra
sono tutti e soli strumenti di misura: rimuoverli dal repository non
cambierebbe di un bit alcuna rete prodotta, perché non hanno mai scritto
un dato di addestramento — verificabile leggendo `pipeline/annotate/` e
`pipeline/generate/`, dove Stockfish non compare mai.

## `non_conforme/`

Contiene gen0 (rete allenata su dati con etichette Stockfish, precedente
alla conoscenza di questa regola) come riferimento storico. Non è
antenato di alcuna rete presentata — vedi `LINEAGE.md` e
`non_conforme/README.md` per i dettagli.

## Dichiarazione

Le reti `luna_gen1.nnue` e `luna_gen2.nnue` (e, quando completa e misurata,
`luna_gen3.nnue`) sono addestrate esclusivamente su dati generati dalla
ricerca/valutazione del motore stesso, secondo la catena di bootstrap
documentata in `LINEAGE.md`. Nessuna posizione né etichetta di gen0 o di
qualunque motore esterno è entrata nei loro dati di addestramento.
