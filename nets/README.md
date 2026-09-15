# Licenza delle reti

**`luna_gen1.nnue`, `luna_gen2.nnue`** — allenate da zero da Daniele
Marpino sulla propria pipeline (`pipeline/train/`), su dati generati
interamente dalla ricerca/valutazione di Luna stesso (vedi `LINEAGE.md` e
`COMPLIANCE.md`). Sono opera propria dell'autore del motore, non derivate
da reti di terzi. **Licenziate GPLv3**, come il motore stesso e come
questo repository (vedi `LICENSE`) — scelta coerente: stesso autore,
stesso progetto, stessa licenza.

**Non è la rete embedded di default nel binario di Luna** (`resources/net.bin`
nel repository del motore, akimbo di Jamie Whiting, MIT — vedi il README
del motore). Quella rete non vive in questo repository: qui ci sono solo
le reti autoprodotte dalla catena di bootstrap gen1/gen2/....

## Checksum

`luna_genN.nnue.sha256` accanto a ciascun file, calcolato localmente al
momento del commit — vedi `checksums/genN/README.md` per lo stato dei
checksum dell'intero dataset di quella generazione (alcuni ancora TODO).
