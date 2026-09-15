# Lineage

Luna's NNUE is bootstrapped generation by generation: each net becomes the
self-play evaluator and annotation master for the next generation's data.
This document is the answer to the one question that actually matters —
**what does the presented net descend from** — because conformance is a
property of the whole chain: one link touched by an external label source
contaminates everything downstream.

As of this writing (2026-09-15), **gen2 is the current presentation
candidate**: it is complete, measured, and its full chain is documented
below. Generation 3 is in progress on Oracle; it replaces gen2 as the
candidate only if it lands in time and its measured ρ falls inside the
pre-registered 0.73-0.76 interval (see `RESULTS.md` 5.7). This file will
gain a gen3 row once that is true — not before.

```
eval classica  (nessuna sorgente esterna)
      │   self-play + annotazione con la RICERCA di Luna
      ▼
    gen1   nets/luna_gen1.nnue   motore 076defc (etichette) / b0cfb937 (self-play)   ρ 0,5874
      ▼
    gen2   nets/luna_gen2.nnue   motore 076defc (etichette e self-play)              ρ 0,6790
      ▼
    gen3   (in corso — non ancora presentabile)

ramo separato, NON antenato di alcuna rete presentata:
    etichette esterne (Stockfish) ──► gen0   ρ 0,7850   [NON CONFORME]
```

**La rete presentata non ha gen0 fra i propri antenati.** gen0 esiste solo
come riferimento di confronto (vedi tabella 1 in `RESULTS.md`) e non ha
contribuito ad alcun dato di addestramento delle reti gen1 e successive —
è precedente alla conoscenza della regola TCEC applicata da gen1 in poi
(dettagli in `non_conforme/README.md`).

## Generazione 1

| Campo | Valore |
|---|---|
| Rete | `nets/luna_gen1.nnue` (`sha256`: vedi `nets/luna_gen1.nnue.sha256`) |
| Maestro self-play | valutazione classica PST (nessuna rete, nessuna fonte esterna) |
| Commit motore — self-play | `b0cfb9378fad417bf03d6bf662d4738d7adadc66` |
| Commit motore — annotazione | `076defcb93d4a1dc834d4ecd5132f45ba9a311d2` |
| Nota di divergenza commit | il self-play è partito prima del fix quiescence (`076defc`); l'annotazione lo usa. Il fix riguarda solo il rispetto del budget nodi/tempo in `quiescence`, non la legalità delle mosse — le posizioni estratte sotto il commit precedente restano valide, solo l'etichetta viene dal commit corretto. |
| Nodi self-play | 3.000 |
| Nodi annotazione | 10.000 |
| Macchina | Oracle (self-play e annotazione) |
| Shard | 46 (`gen1_shard_00001`..`00046`) |
| Partite | 230.000 (assegnate = completate, 100%) |
| Posizioni grezze | 3.300.643 |
| Posizioni uniche | 2.135.009 (64,7%) |
| Resa | 14,3506 pos/partita (denominatore: partite completate = partite assegnate) |
| Dataset train/val | 2.080.991 / 54.018 posizioni, 209.480 / 5.371 partite (split per partita, seed 42) |
| Val loss minima | 0,013316 |
| ρ vs proprio maestro | 0,9230 |
| ρ vs Stockfish (statico) | 0,5874 |
| Checksum dataset | TODO — vedi `checksums/gen1/README.md` |

## Generazione 2

| Campo | Valore |
|---|---|
| Rete | `nets/luna_gen2.nnue` (`sha256`: vedi `nets/luna_gen2.nnue.sha256`) |
| Maestro self-play e annotazione | rete gen1, in ricerca |
| Commit motore — self-play | `b0cfb9378fad417bf03d6bf662d4738d7adadc66` |
| Commit motore — annotazione | `076defcb93d4a1dc834d4ecd5132f45ba9a311d2` |
| Nodi self-play | 3.000 |
| Nodi annotazione | 20.000 (scelto: ginocchio della curva su 10k/20k/50k) |
| Macchina | Oracle (self-play e — dopo riconciliazione, vedi sotto — anche l'intera annotazione) |
| Shard | 53 (`gen2_shard_00001`..`00053`) |
| Partite | 265.000 (assegnate = completate, 100%) |
| Posizioni grezze | 3.083.063 |
| Posizioni uniche | 2.972.944 (96,4%) |
| Resa | 11,6342 pos/partita (denominatore: partite completate = partite assegnate) |
| Dataset train/val | 2.899.216 / 73.728 posizioni, 249.020 / 6.385 partite (split per partita, seed 42) |
| Val loss minima | 0,018874 (epoca 4, early stop epoca 10) |
| ρ vs proprio maestro | 0,9508 |
| ρ vs Stockfish (statico) | 0,6790 |
| Checksum dataset | TODO — vedi `checksums/gen2/README.md` |

**Incidente di provenienza (dichiarato, non nascosto)**: l'annotazione
doveva passare dal PC a Oracle a metà generazione. Il processo PC non si è
fermato per un errore di permessi dell'harness e ha ri-annotato in
parallelo gli shard 3-8 già fatti da Oracle, producendo per alcuni shard un
disallineamento reale fra `.tsv` (da una corsa) e manifesto (dall'altra) —
un guasto che non si vede guardando i numeri: il dataset sembrava sano, la
provenienza era falsa. Intercettato e corretto riconciliando tutto sulla
corsa Oracle (unica fonte autorevole per gli shard 3-53). In seguito si è
scoperto che nemmeno gli shard 1-2 venivano dalla corsa Oracle (nessun
`annotation_machine` nel manifesto, timestamp della corsa PC originale):
**rifatti su Oracle** sotto lo stesso `global_seen.bin` usato per gli altri
51, invece di far convivere due stati di deduplica nello stesso script.
Tutto il dataset gen2 finale viene da un'unica corsa continua. Dettaglio
completo in `RUNBOOK.md` sez. 15-16 (repository del motore).

Un registro che documenta un guasto intercettato e corretto è più
credibile di uno immacolato: il secondo fa pensare che i controlli non
esistano, non che non abbiano mai trovato nulla.

## Generazione 3 (in corso, non presentabile finché non chiude il gate)

| Campo | Valore (parziale, aggiornare a chiusura) |
|---|---|
| Maestro self-play e annotazione | rete gen2, in ricerca |
| Commit motore | `076defcb93d4a1dc834d4ecd5132f45ba9a311d2` (self-play e annotazione, stesso commit fin dall'inizio — nessuna divergenza) |
| Nodi self-play | 3.000 |
| Nodi annotazione | 20.000 (gate sul maestro: ρ 0,8537/0,8760/0,8887 a 10k/20k/50k, sopra il maestro gen2) |
| Macchina | Oracle, unica dall'inizio alla fine (regola di metodo fissata dopo l'incidente gen2) |
| Target shard | 54 |
| Confondimento noto | il pool di aperture normali è stato rigenerato col filtro della rete gen2 (non riusato da gen2). Il passo gen2→gen3 sarà quindi attribuibile a rete + distribuzione delle aperture insieme, non al solo maestro — vedi `RESULTS.md` 5.8. |
| Resto | TODO — in corso, vedi `RUNBOOK.md` sez. 17 |
