#!/bin/bash
# Lancio self-play per generazione dati NNUE (correzioni del 2026-09-07).
# Tre correzioni rispetto al run di calibrazione precedente:
#
#   1. -maxmoves 80  (80 mosse INTERE = 160 semi-mosse, verificato contro il
#      sorgente di cutechess-cli: "Adjudicate ... if at least n full moves
#      have been played" — elimina in un colpo la coda lunga di partite
#      incartate, qualunque sia la causa specifica.
#   2. -draw / -resign: soglie ragionevoli scelte guardando 2-3 partite reali
#      (non ottimizzate: la precisione qui conta poco, il risultato pesa solo
#      il 30% dell'etichetta finale con eval_lambda=0.7).
#   3. Jitter sul passo di campionamento: gestito in extract_positions.py,
#      non qui.
#
# Le partite troncate dal limite -maxmoves vengono ri-aggiudicate con banda
# larga sul punteggio al punto di taglio da extract_positions.py (cutechess
# le marca sempre "Draw by adjudication" a prescindere dal punteggio reale).
#
# Uso:
#   ./run_selfplay.sh <n_games> <output.pgn>
#   ./run_selfplay.sh 500 verify_games.pgn

set -euo pipefail

N_GAMES="${1:-500}"
OUT_PGN="${2:-verify_games.pgn}"
NODES="${3:-10000}"
OPENINGS="${4:-calib_openings.epd}"
ENGINE=./target/release/luna
CONCURRENCY=4
CUTECHESS="${CUTECHESS:-$HOME/cutechess/build/cutechess-cli}"

# Soglia di resign alzata da 400 a 800 (misura 1, 2026-09-07): a 400 il
# 76,2% delle partite (le vinte per aggiudicazione) contribuiva solo il 3,6%
# delle posizioni di vero finale (<=8 pezzi) — le partite gia' decise
# venivano chiuse prima della fase di conversione, che e' esattamente il
# difetto di Luna che questo dataset deve correggere.
time "$CUTECHESS" \
  -engine cmd=$ENGINE name=Luna_A \
  -engine cmd=$ENGINE name=Luna_B \
  -each proto=uci tc=40/60000 nodes=$NODES option.Hash=16 \
  -openings file=$OPENINGS format=epd order=random \
  -games "$N_GAMES" \
  -concurrency $CONCURRENCY \
  -maxmoves 80 \
  -draw movenumber=34 movecount=8 score=30 \
  -resign movecount=8 score=800 twosided=true \
  -pgnout "$OUT_PGN" \
  -recover
