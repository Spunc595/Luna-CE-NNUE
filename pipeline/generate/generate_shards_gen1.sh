#!/bin/bash
# Continuous shard generation for the at-scale run ("anti-loss rule"
# never implemented before this run — see also the previous round's
# data-loss incident).
#
# Each shard is marked .done ONLY after both the PGN and the extraction
# are written in full: the backup watcher (sync_shards.sh, on Daniele's
# PC) must never be able to copy a half-written file. The shard id is
# persisted to disk (shards/next_id.txt), so a script restart resumes
# from the right point without regenerating or skipping shards.
#
# Final configuration (2026-09-07): 3000 nodes, --step 4 + jitter,
# -resign 800, -maxmoves 80.
#
# FIX 2026-09-07 (urgent, correction to a run in progress): previously
# every shard reused the same fixed pool of 3000 openings
# (calib_openings.epd) across 5000 games/shard. Luna is deterministic
# beyond its own internal book: two games with an identical opening are
# the SAME game replayed move for move. Measured on shard_00001: 2000
# openings reused out of 3000, 4000 games out of 5000 involved in an
# exact replay — 40% of generation time produced no new information.
# The jitter on the sampling step masks the problem in the uniqueness
# metric (samples different plies from identical games, so different
# FENs that are nonetheless CORRELATED samples, not independent) — not
# visible without looking at the move list. Fix: a FRESH opening pool
# for every shard, as large as the shard's own game count, so no game in
# the shard can share its opening with another (neither within the
# shard nor with earlier shards, since every pool is new).
#
# FIX 2026-09-07: a third copy on OCI Object Storage
# (Instance Principal, no key on disk) in addition to instance disk and
# local PC. NON-BLOCKING: if the upload fails (network, quota, bucket
# not yet created) the script logs the error and continues — it must
# never stop generation for an archiving problem. IDEMPOTENT: --force
# overwrites without error if the shard is already in the bucket, so a
# script restart doesn't break. Every shard carries its JSON manifest
# (engine version, parameters, opening source) — without it, six months
# from now nobody would know which shard came from which configuration.
#
# Usage: ./generate_shards.sh [games_per_shard]
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
  # --max-per-game raised from 15 to 38: the cap was tuned for --step 10
  # (11 + 15*10 = 161 ply, covered the whole game up to the -maxmoves
  # cap). Left at 15 with --step 4 would cut extraction around ply 71,
  # i.e. BEFORE the conversion phase — silently defeating the reason
  # resign was raised to 800 (see the shard_00001 smoke test: cap
  # already reached in 16% of games even at 50 games). Safe now because
  # duplicates are already under control via -maxmoves 80 + jitter, no
  # longer via this cap.
  ~/nnue-data-venv/bin/python extract_positions.py --pgn "$PGN" --out "$POS" --step 4 --skip-opening 11 --max-per-game 38

  MANIFEST="shards/raw/${SID}.manifest.json"
  ~/nnue-data-venv/bin/python write_manifest.py --shard-id "$SID" --out "$MANIFEST"

  touch "shards/raw/${SID}.done"
  echo "$ID" > "$STATE"
  echo "=== $SID completato e marcato .done ==="

  # Third copy (bucket), BEFORE the local watcher picks up the shard —
  # non-blocking, see upload_to_bucket().
  upload_to_bucket "$SID" "$PGN" "$POS" "$MANIFEST"
done
