# gen0 — non conforme, conservata come riferimento

Rete addestrata su ~11M posizioni da self-play con rete akimbo (embedded,
di terzi, licenza MIT) come valutatore, **etichette da Stockfish**. Non
rispetta la linea guida TCEC applicata da gen1 in poi (tutti i dati devono
venire dalla ricerca/valutazione del motore stesso).

**Perché esiste**: precede la conoscenza esplicita di questa regola nel
progetto. Al momento in cui è stata generata, non era ancora stata presa
la decisione di ripartire da un bootstrap interamente autoprodotto (quella
decisione è ciò che ha aperto la generazione 1).

**Perché è conservata**: come riferimento esterno di confronto (vedi
tabella 1 in `RESULTS.md` — gen0 ottiene ρ 0,7850 contro Stockfish, più
alto di gen1 e gen2, ed è onesto mostrarlo). **Non è antenato di alcuna
rete presentata** — nessuna posizione, nessuna etichetta, nessun peso di
gen0 è entrato nei dati o nei pesi iniziali di gen1, gen2 o successive.
gen1 è ripartita da zero.

**Esito**: SPRT contro akimbo perso nettamente (-339,8 ± 94,8 Elo, LOS
0,0%, H0 accettata su 113 partite). Non più utilizzata, non cancellata.

## Lo script di annotazione con fonte esterna

`annotate_positions.py` (in questa cartella) è l'unico script di
annotazione dell'intero repository che chiama Stockfish come **sorgente di
etichette** (non come strumento di misura offline — vedi la distinzione in
`COMPLIANCE.md`). È isolato qui, non in `pipeline/annotate/` insieme agli
script conformi, proprio per marcare la differenza di categoria: non è un
errore da correggere, è un artefatto storico da non riusare.
