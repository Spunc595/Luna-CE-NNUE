#!/bin/bash
# Launches self-play for NNUE data generation (corrections of
# 2026-09-07). Three corrections relative to the previous calibration
# run:
#
#   1. -maxmoves 80  (80 FULL moves = 160 half-moves, verified against
#      cutechess-cli's source: "Adjudicate ... if at least n full moves
#      have been played" — eliminates in one shot the long tail of
#      stuck games, whatever the specific cause.
#   2. -draw / -resign: reasonable thresholds chosen by looking at 2-3
#      real games (not optimized: precision matters little here, the
#      result weighs only 30% of the final label with eval_lambda=0.7).
#   3. Jitter on the sampling step: handled in extract_positions.py,
#      not here.
#
# Games truncated by the -maxmoves limit are re-adjudicated with a wide
# band on the score at the cutoff point by extract_positions.py
# (cutechess always marks them "Draw by adjudication" regardless of the
# actual score).
#
# Usage:
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

# Resign threshold raised from 400 to 800 (correction 1, 2026-09-07): at
# 400, 76.2% of games (those won by adjudication) contributed only 3.6%
# of true-endgame positions (<=8 pieces) — already-decided games were
# being closed before the conversion phase, which is exactly the defect
# in Luna this dataset is meant to correct.
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
