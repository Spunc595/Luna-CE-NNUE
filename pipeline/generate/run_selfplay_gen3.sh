#!/bin/bash
# Self-play for generation 3: gen2 net (UseNNUE=true, net
# loaded externally as ./engine/luna.nnue). Same structure as
# run_selfplay_gen2.sh, only the folder/net differ.
#
# Usage:
#   ./run_selfplay_gen3.sh <n_games> <output.pgn> <nodes> <openings.epd>
set -euo pipefail

N_GAMES="${1:-500}"
OUT_PGN="${2:-verify_games.pgn}"
NODES="${3:-3000}"
OPENINGS="${4:-openings.epd}"
ENGINE="$HOME/gen3_classical/engine/luna"
CONCURRENCY=4
CUTECHESS="${CUTECHESS:-$HOME/cutechess/build/cutechess-cli}"

PROBE=$(printf 'uci\nquit\n' | "$ENGINE" | grep -E "NNUE: loaded|External NNUE")
echo "=== probe caricamento rete gen2: $PROBE ==="
if ! echo "$PROBE" | grep -q "NNUE: loaded"; then
  echo "ERRORE FATALE: il motore non conferma il caricamento della rete esterna. Interrompo."
  exit 1
fi

time "$CUTECHESS" \
  -engine cmd=$ENGINE name=Luna_A \
  -engine cmd=$ENGINE name=Luna_B \
  -each proto=uci tc=40/60000 nodes=$NODES option.Hash=16 option.UseNNUE=true \
  -openings file=$OPENINGS format=epd order=random \
  -games "$N_GAMES" \
  -concurrency $CONCURRENCY \
  -maxmoves 80 \
  -draw movenumber=34 movecount=8 score=30 \
  -resign movecount=8 score=800 twosided=true \
  -pgnout "$OUT_PGN" \
  -recover
