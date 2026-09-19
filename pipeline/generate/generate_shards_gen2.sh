#!/bin/bash
# Shard generation for GENERATION 2: self-play + extraction
# + manifest here on Oracle (4 dedicated CPUs). Annotation tailing on
# the PC (annotate_incremental_gen2.py, gen1 net at 50k nodes) — same
# pattern already proven for gen1, only the net changes. Openings
# WITHOUT replacement (build_shard_openings_gen2.py): exhausted pool =
# fatal error, not a silent wrap-around.
#
# Usage: ./generate_shards_gen2.sh [games_per_shard]
set -euo pipefail
cd ~/gen2_classical

GAMES_PER_SHARD="${1:-5000}"
MAX_SHARDS="${2:-0}"  # 0 = no limit; used for the checkpoint on the first 5
NODES_SELFPLAY=3000
STATE=shards/next_id.txt
OCI_BUCKET=luna-nnue-data
OCI="$HOME/bin/oci"

mkdir -p shards/raw shards/backed_up
[ -f "$STATE" ] || echo 0 > "$STATE"

# Pool-sizing assert: the uniqueness gate on the first shards doesn't
# prove the pool will hold out to the end — only the arithmetic does.
# Compares pool size against the total expected demand for MAX_SHARDS
# shards and refuses to start if it doesn't add up, BEFORE consuming
# anything.
if [ "$MAX_SHARDS" -gt 0 ]; then
  ENDGAME_FRAC=0.30
  NEED_TOTAL=$((MAX_SHARDS * GAMES_PER_SHARD))
  NEED_ENDGAME=$(awk -v t="$NEED_TOTAL" -v f="$ENDGAME_FRAC" 'BEGIN{printf "%d", t*f + 0.5}')
  NEED_NORMAL=$((NEED_TOTAL - NEED_ENDGAME))
  HAVE_NORMAL=$(wc -l < data/normal_openings.epd)
  HAVE_ENDGAME=$(wc -l < data/endgame_positions.epd)
  echo "=== assert pool sizing: target $MAX_SHARDS shards x $GAMES_PER_SHARD games => need normal=$NEED_NORMAL (has $HAVE_NORMAL), endgame=$NEED_ENDGAME (has $HAVE_ENDGAME) ==="
  if [ "$HAVE_NORMAL" -lt "$NEED_NORMAL" ] || [ "$HAVE_ENDGAME" -lt "$NEED_ENDGAME" ]; then
    echo "[FATAL ERROR] pool too small for the declared target of $MAX_SHARDS shards: normal has $HAVE_NORMAL rows, needs $NEED_NORMAL; endgame has $HAVE_ENDGAME rows, needs $NEED_ENDGAME. Size the pool before relaunching." >&2
    exit 1
  fi
fi

upload_to_bucket() {
  local sid="$1" pgn="$2" pos="$3" manifest="$4"
  if [ ! -x "$OCI" ]; then
    echo "=== $sid: oci CLI not found ($OCI), skipping the upload ==="
    return 0
  fi
  local pgn_gz="${pgn}.gz" pos_gz="${pos}.gz"
  gzip -k -f "$pgn" "$pos" || { echo "=== $sid: gzip failed, skipping the upload ==="; return 0; }
  for f in "$pgn_gz" "$pos_gz" "$manifest"; do
    if ! "$OCI" os object put --auth instance_principal \
        --bucket-name "$OCI_BUCKET" \
        --name "gen2/$(basename "$f")" \
        --file "$f" --force --no-multipart 2>>"shards/upload_errors.log"; then
      echo "=== $sid: upload fallito per $(basename "$f") (dettagli in shards/upload_errors.log), proseguo ==="
    fi
  done
  rm -f "$pgn_gz" "$pos_gz"
}

while true; do
  ID=$(($(cat "$STATE") + 1))
  SID=$(printf 'gen2_shard_%05d' "$ID")
  PGN="shards/raw/${SID}.pgn"
  POS="shards/raw/${SID}_positions.txt"
  OPENINGS="shards/raw/${SID}_openings.epd"
  MANIFEST="shards/raw/${SID}.manifest.json"

  echo "=== $SID: openings (70/30 mix, WITHOUT replacement) ==="
  BUILD_OUT=$(python3 -u build_shard_openings_gen2.py --normal-pool data/normal_openings.epd \
      --endgame-pool data/endgame_positions.epd --count "$GAMES_PER_SHARD" \
      --endgame-frac 0.30 --out "$OPENINGS")
  echo "$BUILD_OUT"
  ENDGAME_LINES=$(echo "$BUILD_OUT" | grep ENDGAME_LINES | cut -d= -f2)

  echo "=== $SID: self-play ($GAMES_PER_SHARD games, $NODES_SELFPLAY nodes, gen1 network) ==="
  ./run_selfplay_gen2.sh "$GAMES_PER_SHARD" "$PGN" "$NODES_SELFPLAY" "$OPENINGS"

  echo "=== $SID: extraction ==="
  python3 ~/rust-chess/extract_positions.py --pgn "$PGN" --out "$POS" --step 4 --skip-opening 11 --max-per-game 38

  echo "=== $SID: manifest (labels are chased on the PC) ==="
  python3 write_manifest_gen2.py --shard-id "$SID" --pgn "$PGN" --positions "$POS" \
      --openings "$OPENINGS" --endgame-lines-in-openings "$ENDGAME_LINES" --out "$MANIFEST"

  mv "$PGN" "$POS" "$OPENINGS" "$MANIFEST" shards/backed_up/
  touch "shards/backed_up/${SID}.done"
  echo "$ID" > "$STATE"
  echo "=== $SID completato e marcato .done ==="

  upload_to_bucket "$SID" "shards/backed_up/${SID}.pgn" "shards/backed_up/${SID}_positions.txt" \
      "shards/backed_up/${SID}.manifest.json"

  if [ "$MAX_SHARDS" -gt 0 ] && [ "$ID" -ge "$MAX_SHARDS" ]; then
    echo "=== limite di $MAX_SHARDS shard raggiunto, mi fermo per il checkpoint ==="
    break
  fi
done
