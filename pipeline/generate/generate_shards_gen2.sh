#!/bin/bash
# Generazione a shard per la GENERAZIONE 2 (gen2.md): self-play + estrazione
# + manifesto qui su Oracle (4 CPU dedicate). Annotazione a inseguimento sul
# PC (annotate_incremental_gen2.py, rete gen1 a 50k nodi) — stesso pattern
# gia' collaudato della gen1, solo la rete cambia. Aperture SENZA
# reinserimento (build_shard_openings_gen2.py): pool esaurito = errore
# fatale, non wrap-around silenzioso.
#
# Uso: ./generate_shards_gen2.sh [games_per_shard]
set -euo pipefail
cd ~/gen2_classical

GAMES_PER_SHARD="${1:-5000}"
MAX_SHARDS="${2:-0}"  # 0 = nessun limite; usato per il checkpoint sui primi 5 (gen2.md punto 2)
NODES_SELFPLAY=3000
STATE=shards/next_id.txt
OCI_BUCKET=luna-nnue-data
OCI="$HOME/bin/oci"

mkdir -p shards/raw shards/backed_up
[ -f "$STATE" ] || echo 0 > "$STATE"

# Assert di dimensionamento pool (gen2-pool.md, punto 1): il gate di unicita'
# sui primi shard non dimostra che il pool basti fino in fondo — solo
# l'aritmetica lo fa. Confronta la dimensione dei pool con la domanda totale
# attesa per MAX_SHARDS shard e si rifiuta di partire se non torna, PRIMA di
# consumare nulla.
if [ "$MAX_SHARDS" -gt 0 ]; then
  ENDGAME_FRAC=0.30
  NEED_TOTAL=$((MAX_SHARDS * GAMES_PER_SHARD))
  NEED_ENDGAME=$(awk -v t="$NEED_TOTAL" -v f="$ENDGAME_FRAC" 'BEGIN{printf "%d", t*f + 0.5}')
  NEED_NORMAL=$((NEED_TOTAL - NEED_ENDGAME))
  HAVE_NORMAL=$(wc -l < data/normal_openings.epd)
  HAVE_ENDGAME=$(wc -l < data/endgame_positions.epd)
  echo "=== assert dimensionamento pool: target $MAX_SHARDS shard x $GAMES_PER_SHARD partite => servono normale=$NEED_NORMAL (ha $HAVE_NORMAL), finale=$NEED_ENDGAME (ha $HAVE_ENDGAME) ==="
  if [ "$HAVE_NORMAL" -lt "$NEED_NORMAL" ] || [ "$HAVE_ENDGAME" -lt "$NEED_ENDGAME" ]; then
    echo "[ERRORE FATALE] pool insufficiente per il target dichiarato di $MAX_SHARDS shard: normale ha $HAVE_NORMAL righe, servono $NEED_NORMAL; finale ha $HAVE_ENDGAME righe, servono $NEED_ENDGAME. Dimensiona il pool prima di rilanciare." >&2
    exit 1
  fi
fi

upload_to_bucket() {
  local sid="$1" pgn="$2" pos="$3" manifest="$4"
  if [ ! -x "$OCI" ]; then
    echo "=== $sid: oci CLI non trovato ($OCI), salto l'upload ==="
    return 0
  fi
  local pgn_gz="${pgn}.gz" pos_gz="${pos}.gz"
  gzip -k -f "$pgn" "$pos" || { echo "=== $sid: gzip fallito, salto l'upload ==="; return 0; }
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

  echo "=== $SID: aperture (mix 70/30, SENZA reinserimento) ==="
  BUILD_OUT=$(python3 -u build_shard_openings_gen2.py --normal-pool data/normal_openings.epd \
      --endgame-pool data/endgame_positions.epd --count "$GAMES_PER_SHARD" \
      --endgame-frac 0.30 --out "$OPENINGS")
  echo "$BUILD_OUT"
  ENDGAME_LINES=$(echo "$BUILD_OUT" | grep ENDGAME_LINES | cut -d= -f2)

  echo "=== $SID: self-play ($GAMES_PER_SHARD partite, $NODES_SELFPLAY nodi, rete gen1) ==="
  ./run_selfplay_gen2.sh "$GAMES_PER_SHARD" "$PGN" "$NODES_SELFPLAY" "$OPENINGS"

  echo "=== $SID: estrazione ==="
  python3 ~/rust-chess/extract_positions.py --pgn "$PGN" --out "$POS" --step 4 --skip-opening 11 --max-per-game 38

  echo "=== $SID: manifesto (etichette a inseguimento sul PC) ==="
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
