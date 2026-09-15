#!/bin/bash
# Generazione continua a shard per il run su scala (nnuedazero.md, sezione 0:
# "regola anti-perdita" mai implementata prima di questo run — vedi anche
# l'incidente di perdita dati del round precedente).
#
# Ogni shard viene marcato .done SOLO dopo che sia il PGN che l'estrazione
# sono scritti per intero: il watcher di backup (sync_shards.sh, sul PC di
# Daniele) non deve mai poter copiare un file a meta'. L'id di shard e'
# persistito su disco (shards/next_id.txt), quindi un riavvio dello script
# riprende dal punto giusto senza rigenerare o saltare shard.
#
# Configurazione definitiva (2026-09-07): 3000 nodi, --step 4 + jitter,
# -resign 800, -maxmoves 80.
#
# FIX 2026-09-07 (urgente, correzione a run in corso): prima ogni shard
# riusava lo stesso pool fisso di 3000 aperture (calib_openings.epd) su
# 5000 partite/shard. Luna e' deterministica oltre il proprio libro
# interno: due partite con l'apertura identica sono la STESSA partita
# rigiocata mossa per mossa. Misurato su shard_00001: 2000 aperture
# riusate su 3000, 4000 partite su 5000 coinvolte in un replay esatto —
# il 40% del tempo di generazione non produceva informazione nuova. Il
# jitter sul passo di campionamento maschera il problema nella metrica di
# unicita' (campiona ply diversi da partite identiche, quindi FEN diversi
# che pero' sono campioni CORRELATI, non indipendenti) — non e' visibile
# senza guardare la lista di mosse. Fix (nnuedazero.md, punto 1.2.2): un
# pool di aperture FRESCO per ogni shard, grande quanto il numero di
# partite dello shard stesso, cosi' nessuna partita nello shard puo'
# condividere l'apertura con un'altra (ne' dentro lo shard ne' con shard
# precedenti, dato che ogni pool e' nuovo).
#
# FIX 2026-09-07 (ocibucket.md): terza copia su OCI Object Storage
# (Instance Principal, nessuna chiave sul disco) oltre a disco-istanza e
# PC locale. NON BLOCCANTE: se l'upload fallisce (rete, quota, bucket non
# ancora creato) lo script registra l'errore e prosegue — non deve mai
# fermare la generazione per un problema di archiviazione. IDEMPOTENTE:
# --force sovrascrive senza errore se lo shard e' gia' nel bucket, quindi
# un riavvio dello script non si rompe. Ogni shard porta il suo manifest
# JSON (versione motore, parametri, sorgente aperture) — senza, fra sei
# mesi non si saprebbe piu' quale shard viene da quale configurazione.
#
# Uso: ./generate_shards.sh [games_per_shard]
set -euo pipefail
cd ~/rust-chess

GAMES_PER_SHARD="${1:-5000}"
NODES=3000
STATE=shards/next_id.txt
STOCKFISH=/usr/games/stockfish
OCI_BUCKET=luna-nnue-data
OCI="$HOME/bin/oci"

mkdir -p shards/raw shards/backed_up
[ -f "$STATE" ] || echo 0 > "$STATE"

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
        --name "shards/$(basename "$f")" \
        --file "$f" --force --no-multipart 2>>"shards/upload_errors.log"; then
      echo "=== $sid: upload fallito per $(basename "$f") (dettagli in shards/upload_errors.log), proseguo ==="
    fi
  done
  rm -f "$pgn_gz" "$pos_gz"
}

while true; do
  ID=$(($(cat "$STATE") + 1))
  SID=$(printf 'shard_%05d' "$ID")
  PGN="shards/raw/${SID}.pgn"
  POS="shards/raw/${SID}_positions.txt"
  OPENINGS="shards/raw/${SID}_openings.epd"

  echo "=== $SID: generazione aperture fresche ($GAMES_PER_SHARD, seed=$ID) ==="
  ~/nnue-data-venv/bin/python gen_random_openings.py --count "$GAMES_PER_SHARD" --plies 9 \
      --out "$OPENINGS" --stockfish "$STOCKFISH" --eval-limit 200 --depth 6 --seed "$ID"

  echo "=== $SID: generazione ($GAMES_PER_SHARD partite, $NODES nodi) ==="
  ./run_selfplay.sh "$GAMES_PER_SHARD" "$PGN" "$NODES" "$OPENINGS"

  echo "=== $SID: estrazione (step 4 + jitter) ==="
  # --max-per-game alzato da 15 a 38: il tetto era tarato per --step 10
  # (11 + 15*10 = 161 ply, copriva l'intera partita fino al tetto -maxmoves).
  # Lasciato a 15 con --step 4 taglierebbe l'estrazione intorno al ply 71,
  # cioe' PRIMA della fase di conversione — vanificherebbe silenziosamente
  # il motivo per cui il resign e' stato alzato a 800 (vedi smoke test
  # shard_00001: cap gia' raggiunto nel 16% delle partite anche a 50 partite).
  # Sicuro ora perche' i duplicati sono gia' sotto controllo via -maxmoves 80
  # + jitter, non piu' via questo tetto (nnuepostcalibrazione.md).
  ~/nnue-data-venv/bin/python extract_positions.py --pgn "$PGN" --out "$POS" --step 4 --skip-opening 11 --max-per-game 38

  MANIFEST="shards/raw/${SID}.manifest.json"
  ~/nnue-data-venv/bin/python write_manifest.py --shard-id "$SID" --out "$MANIFEST"

  touch "shards/raw/${SID}.done"
  echo "$ID" > "$STATE"
  echo "=== $SID completato e marcato .done ==="

  # Terza copia (bucket), PRIMA che il watcher locale prenda in carico lo
  # shard — non bloccante, vedi upload_to_bucket().
  upload_to_bucket "$SID" "$PGN" "$POS" "$MANIFEST"
done
