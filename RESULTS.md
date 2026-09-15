# Results

Ogni numero in questo documento è stato **ricalcolato dai `.csv` in
`results/`** al momento di scriverlo (2026-09-15), non copiato dal
RUNBOOK — vedi 5.2 per il vincolo e per le due discrepanze reali trovate
ricalcolando.

## 1. Reti a confronto — misura statica

Valutazione statica (comando UCI `eval`, **nessuna ricerca**), stesso
insieme di 2.000 posizioni (`results/eval_set.epd`, campionate con
seed=7 da un validation set di riferimento condiviso, dettagli in 5.3),
Stockfish depth 8 come riferimento.

| Rete | ρ vs Stockfish |
|---|---|
| gen1 | 0,5874 |
| gen2 | 0,6790 |
| gen0 *(non conforme — vedi `non_conforme/README.md`)* | 0,7850 |
| akimbo *(rete di terzi, MIT, solo riferimento — mai usata per generare dati)* | 0,8522 |

Script: `results/scripts/measure_static_vs_stockfish.py`. CSV:
`results/gen1_vs_stockfish.csv`, `gen2_vs_stockfish.csv`,
`akimbo_vs_stockfish.csv`. Motore commit `076defcb93d4a1dc834d4ecd5132f45ba9a311d2`
(gen1, gen2); akimbo: build di riferimento separata (v3.1.2, rete embedded
akimbo, nessuna rete esterna caricata). Data: 2026-09-15. Nessuna ricerca
coinvolta: la valutazione statica non usa thread, è deterministica per
costruzione.

## 2. Il motore in ricerca, per generazione

**Non è la stessa grandezza della tabella 1** — qui si misura il motore
COME GIOCA DAVVERO (ricerca a nodi fissi), non la rete isolata. **1 thread**
(default UCI, mai sovrascritto in nessuno script di misura di questo
repository — riproducibile esattamente). Stesso insieme di 2.000 posizioni
di `results/eval_set.epd`.

| nodi | Luna + gen1 | Luna + gen2 | passo |
|---|---|---|---|
| 10.000 | 0,8072 | 0,8537 | +0,0465 |
| 20.000 | 0,8285 | 0,8760 | +0,0475 |
| 50.000 | 0,8413 | 0,8887 | +0,0474 |

**Il passo è costante ai tre livelli di nodi** — se fosse rumore lo si
vedrebbe variare. Il miglioramento gen1→gen2 si trasferisce alla ricerca
in modo uniforme, non solo dove la ricerca è cieca.

Script: `results/scripts/measure_search_vs_stockfish.py`. CSV:
`results/gen1_master_vs_stockfish.csv`, `results/gen2_master_vs_stockfish.csv`.
Data: 2026-09-15.

**Discrepanza trovata e non risolta a favore di un numero scelto a
piacere** (vincolo 5.2): ricalcolando dai CSV appena prodotti, i valori
gen1 a 20k e 50k nodi **non coincidono esattamente** con quelli registrati
nel RUNBOOK/gen2.md:

| nodi | registrato (RUNBOOK) | ricalcolato ora (stesso seed, stesso commit motore) |
|---|---|---|
| 10.000 | 0,8072 | 0,8072 |
| 20.000 | 0,8285 | 0,8249 |
| 50.000 | 0,8413 | 0,8428 |

gen2 ricalcola entro 0,0004 in tutti e tre i casi (rumore di
arrotondamento atteso). gen1 no, a 20k e 50k. Entrambi i motori sono
**a 1 thread** e la valutazione a 10.000 nodi coincide esattamente —
un'ipotesi plausibile ma non verificata è che la misura originale di gen1
sia stata fatta a cavallo del fix `076defc` (correzione di un vero bug di
timeout in `quiescence`, che incide di più su ricerche più profonde/lunghe
— coerente col fatto che 10k, la ricerca più corta, coincida esattamente
mentre 20k/50k no). **Non scelto quale dei due è giusto**: la tabella sopra
usa il valore RICALCOLATO ora (stesso commit `076defc` per entrambe le
generazioni, quindi confrontabile fra loro), il valore storico resta
qui come nota. TODO: verificare il commit esatto usato per la misura gen1
originale, se recuperabile dai log.

## 3. Quanto ciascuna rete ha appreso dal proprio maestro

**Grandezza diversa dalle prime due — non confrontabile con esse.** Misura
quanto fedelmente la rete riproduce il proprio maestro (che per gen1 è la
PST classica, per gen2 è la rete gen1 in ricerca): non dice nulla su
quanto la rete sia vicina alla verità (quello lo dicono le tabelle 1-2).

| Generazione | ρ vs proprio maestro |
|---|---|
| gen1 | 0,9230 |
| gen2 | 0,9508 |

## 4. I dataset

| Generazione | Posizioni totali | Uniche | Tasso di unicità | Partite | Resa (pos/partita) | Nodi self-play | Nodi annotazione | Rete maestro | Macchina | Commit |
|---|---|---|---|---|---|---|---|---|---|---|
| gen1 | 3.300.643 | 2.135.009 | 64,7% | 230.000 | 14,3506 | 3.000 | 10.000 | classica (PST) | Oracle (self-play), PC (annotazione) | self-play `b0cfb937` / annotazione `076defc` |
| gen2 | 3.083.063 | 2.972.944 | 96,4% | 265.000 | 11,6342 | 3.000 | 20.000 | gen1 (ricerca) | Oracle (self-play e, dopo riconciliazione, annotazione) | `076defc` (entrambe) |
| gen3 | *in corso* | *in corso* | *in corso* | *in corso* | 11,88 *(solo 5 shard di controllo su 54, non l'intera generazione)* | 3.000 | 20.000 | gen2 (ricerca) | Oracle (intera generazione) | `076defc` (entrambe) |

**Denominatore della resa, dichiarato per tutte e tre**: posizioni grezze
estratte / **partite completate**. Verificato esplicitamente per tutte e
tre le generazioni che partite completate = partite assegnate (100% in
ognuna, nessuna partita fallita/persa) — il denominatore non è ambiguo qui,
ma va ricontrollato ad ogni generazione futura, non assunto.

**Nota sulla gen1**: la cifra "14,2 pos/partita" circolata in precedenza
(RUNBOOK, conversazioni) veniva da un **trial preliminare di 3 shard**
(2.400 partite), non dall'intera generazione. Il numero corretto per
l'intera gen1 (46 shard, 230.000 partite) è **14,3506** — la differenza è
piccola ma il numero sbagliato non va propagato: è quello con cui si
dimensionerebbero i pool di una generazione futura se si riusasse gen1
come riferimento.

## 5. Addestramento

| Generazione | Val loss minima | Epoca | Epoche usate | Varianza target (pre-volo) | MSE materiale (pre-volo) | MSE non addestrato (pre-volo) |
|---|---|---|---|---|---|---|
| gen1 | 0,013316 | — | 12 (mai raggiunto plateau, non rifare per questo) | — | — | — |
| gen2 | 0,018874 | 4 | 10 (early stop, patience 6) | 0,134622 | 0,030026 | 0,135515 |

**Le val loss non sono confrontabili fra generazioni: sono scale diverse**
(dataset e target diversi). Guardare i rapporti (quota di varianza
spiegata, distanza dal materiale), non il valore assoluto.

I tre numeri di pre-volo di gen1 non sono stati ritrovati in questa
sessione (TODO: recuperarli da `gen1_train.log` su richiesta, non urgente).

## 5.5 Controllo di sovrapposizione

`results/eval_set.epd` (le 2.000 posizioni usate per tutte le tabelle
sopra) è un campione di un validation set (`val_final.tsv`, 274.226
posizioni) tenuto fuori dal training fin dalla sua creazione (gen0).
**Verificato per intero, non a campione** (confronto letterale di FEN,
leggero anche su milioni di righe, nessuna CPU pesante):

| Dataset di training | Righe controllate | Sovrapposizioni trovate |
|---|---|---|
| gen1 (`gen1_train.tsv`) | 2.080.991 | 0 |
| gen2 (`gen2_train.tsv`) | 2.899.216 | 0 |
| gen3 | *in corso, da controllare a fine generazione* | TODO |

Zero sovrapposizioni confermate per gen1 e gen2: le misure di Spearman non
premiano memorizzazione.

## 5.6 Cosa non è stato misurato

- **Misurato direttamente**: correlazione di ordinamento (Spearman),
  sia statica (tabella 1) sia in ricerca a nodi fissi (tabella 2).
- **Inferito, non misurato**: che una correlazione di rango più alta
  corrisponda a più forza di gioco (Elo). È un'assunzione ragionevole
  (l'unico SPRT diretto disponibile, gen0 vs akimbo, mostra una rete con
  Spearman più basso perdere nettamente — coerente ma è un solo punto dato)
  non una misura.
- **Non misurato affatto**: l'Elo di gen1 o gen2. Nessuno SPRT è stato
  lanciato in questi due cicli (per istruzione esplicita — il confronto è
  fra generazioni via Spearman, non fra generazione e baseline via Elo).

## 5.7 Le due previsioni per la gen3 (registrate il 2026-09-15, prima del risultato)

1. **Tendenza statica** (da `gen3.md`): 0,5874 → 0,6790 è +0,0916; con passi
   che si accorciano, atteso **0,73-0,76**.
2. **Rapporto allievo/maestro**: gen2 ha reso 0,6790/0,8285 = **0,8196** del
   proprio maestro (in ricerca a 20k nodi, valore RUNBOOK originale — vedi
   nota sulla discrepanza in tabella 2 se si vuole ricalcolare con
   0,8249); con un maestro gen3 a 0,8760, la gen3 atterrerebbe a **~0,718**.

Non modificare la prima previsione dopo aver visto risultati parziali:
si registrano entrambe adesso, si vede quale vince quando la gen3 chiude.

## 5.8 Confondimento della generazione 3

Il pool di aperture normali della gen3 è stato **rigenerato da zero** col
filtro della rete gen2 (gen2 aveva usato il filtro della rete gen1, non
riusato). **Il passo gen2→gen3 nel ρ vs Stockfish sarà quindi attribuibile
a rete E distribuzione delle aperture insieme, non al solo miglioramento
del maestro isolato.** Non è un errore ed è tardi per tornare indietro —
ma chi legge il numero fra sei mesi deve saperlo qui, non solo nel testo
introduttivo: quando la riga gen3 verrà aggiunta alla tabella 1, questa
nota va ripetuta nella cella o nella riga stessa.

---

## Riferimenti rapidi ai file

- `eval_set.epd` — 2.000 posizioni (fen, eval Stockfish depth 8, bestmove,
  wdl, depth), campionate deterministicamente (seed=7) da un validation
  set di riferimento di 274.226 posizioni non usato in alcun training.
- `*_vs_stockfish.csv` — valutazioni grezze riga per posizione, uno per
  motore/misura, prodotti dagli script in `results/scripts/`.
- `results/scripts/` — codice che produce i CSV sopra e calcola Spearman.
  Vedi `COMPLIANCE.md` per perché la presenza di "stockfish" qui non è una
  violazione.
