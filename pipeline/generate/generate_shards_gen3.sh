#!/bin/bash
# Generazione a shard per la GENERAZIONE 3 (gen3.md): self-play + estrazione
# + manifesto + annotazione, TUTTO su Oracle (una sola macchina, un solo
# global_seen.bin -- gen3.md, "regola di metodo", non un ripiego).
# Aperture SENZA reinserimento (build_shard_openings_gen3.py): pool esaurito
# = errore fatale, non wrap-around silenzioso.
#
# Uso: ./generate_shards_gen3.sh [games_per_shard] [max_shards]
set -euo pipefail
cd ~/gen3_classical

GAMES_PER_SHARD="${1:-5000}"
MAX_SHARDS="${2:-0}"  # 0 = nessun limite; usato per il checkpoint sui primi shard di controllo
NODES_SELFPLAY=3000
STATE=shards/next_id.txt
OCI_BUCKET=luna-nnue-data
OCI="$HOME/bin/oci"

mkdir -p shards/raw shards/backed_up
[ -f "$STATE" ] || echo 0 > "$STATE"

# Assert di dimensionamento pool (gen3.md, punto 2): aritmetico, non il gate
# di unicita' sui primi shard (che da' falso verde finche' il pool non si
# esaurisce davvero). Si rifiuta di partire se non torna, PRIMA di consumare
# nulla.
if [ "$MAX_SHARDS" -gt 0 ]; then
  ENDGAME_FRAC=0.30
  # Fattore di consumo misurato sui 5 shard di controllo (2026-09-15):
  # offset normale 17.500/17.500 attese, offset finale 7.500/7.500 attese --
  # nessuno scarto, le aperture sono assegnate prima del self-play, non per
  # partita completata, quindi partite fallite/ritentate non consumano righe
  # in piu'. Non e' un'assunzione: e' il valore misurato, va ricontrollato se
  # la logica di assegnazione aperture cambia in futuro.
  CONSUMPTION_FACTOR=1.0000
  NEED_TOTAL_NOMINAL=$((MAX_SHARDS * GAMES_PER_SHARD))
  NEED_ENDGAME=$(awk -v t="$NEED_TOTAL_NOMINAL" -v f="$ENDGAME_FRAC" -v c="$CONSUMPTION_FACTOR" 'BEGIN{printf "%d", t*f*c + 0.5}')
  NEED_NORMAL=$(awk -v t="$NEED_TOTAL_NOMINAL" -v f="$ENDGAME_FRAC" -v c="$CONSUMPTION_FACTOR" 'BEGIN{printf "%d", t*(1-f)*c + 0.5}')
  HAVE_NORMAL=$(wc -l < data/normal_openings.epd)
  HAVE_ENDGAME=$(wc -l < data/endgame_positions.epd)
  echo "=== assert dimensionamento pool: target $MAX_SHARDS shard x $GAMES_PER_SHARD partite, fattore di consumo misurato=$CONSUMPTION_FACTOR => servono normale=$NEED_NORMAL (ha $HAVE_NORMAL), finale=$NEED_ENDGAME (ha $HAVE_ENDGAME) ==="
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
        --name "gen3/$(basename "$f")" \
        --file "$f" --force --no-multipart 2>>"shards/upload_errors.log"; then
      echo "=== $sid: upload fallito per $(basename "$f") (dettagli in shards/upload_errors.log), proseguo ==="
    fi
  done
  rm -f "$pgn_gz" "$pos_gz"
}

while true; do
  ID=$(($(cat "$STATE") + 1))
  SID=$(printf 'gen3_shard_%05d' "$ID")
  PGN="shards/raw/${SID}.pgn"
  POS="shards/raw/${SID}_positions.txt"
  OPENINGS="shards/raw/${SID}_openings.epd"
  MANIFEST="shards/raw/${SID}.manifest.json"

  echo "=== $SID: aperture (mix 70/30, SENZA reinserimento) ==="
  BUILD_OUT=$(python3 -u build_shard_openings_gen3.py --normal-pool data/normal_openings.epd \
      --endgame-pool data/endgame_positions.epd --count "$GAMES_PER_SHARD" \
      --endgame-frac 0.30 --out "$OPENINGS")
  echo "$BUILD_OUT"
  ENDGAME_LINES=$(echo "$BUILD_OUT" | grep ENDGAME_LINES | cut -d= -f2)

  echo "=== $SID: self-play ($GAMES_PER_SHARD partite, $NODES_SELFPLAY nodi, rete gen2) ==="
  ./run_selfplay_gen3.sh "$GAMES_PER_SHARD" "$PGN" "$NODES_SELFPLAY" "$OPENINGS"

  echo "=== $SID: estrazione ==="
  python3 ~/rust-chess/extract_positions.py --pgn "$PGN" --out "$POS" --step 4 --skip-opening 11 --max-per-game 38

  echo "=== $SID: manifesto ==="
  python3 write_manifest_gen3.py --shard-id "$SID" --pgn "$PGN" --positions "$POS" \
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
