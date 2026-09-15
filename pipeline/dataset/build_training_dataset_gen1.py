"""
Assembla il dataset di training dagli shard annotati (primotraining.md,
sezione 1): join di ogni shard_NNNNN_annotated.tsv (fen, eval_cp, bestmove,
wdl_mover, depth) con lo shard_NNNNN_positions.txt originale (fen, result,
game_id, truncated) per recuperare il game_id — necessario per lo split
treno/validazione PER PARTITA, non per posizione: posizioni della stessa
partita sono correlate, se finiscono sparse fra treno e validazione la
validation loss misura memorizzazione, non generalizzazione.

Il game_id di extract_positions.py e' locale allo shard (riparte da 1 ogni
volta): qui viene reso globale col prefisso "<shard_id>_", stessa
convenzione di resolve_truncated_wdl.py --shard-tag.

Scrive train.tsv/val.tsv (5 colonne, stesso formato degli shard annotati,
game_id NON incluso: serve solo per lo split, non per il training) e un
dataset_composition.json con la composizione esatta (shard inclusi,
posizioni per shard, totali, data).

Uso:
  python build_training_dataset.py --shards-dir shards_backup --annotated-dir annotated \
      --start 1 --end 67 --train-out train.tsv --val-out val.tsv \
      --composition-out dataset_composition.json --val-fraction 0.03 --seed 42
"""
import argparse
import datetime
import json
import os
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--annotated-dir", required=True)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--train-out", required=True)
    ap.add_argument("--val-out", required=True)
    ap.add_argument("--composition-out", required=True)
    ap.add_argument("--val-fraction", type=float, default=0.03)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows_by_game = {}  # game_id globale -> lista di righe (5 colonne)
    per_shard_counts = []
    total_positions = 0

    for n in range(args.start, args.end + 1):
        sid = f"gen1_shard_{n:05d}"
        ann_path = os.path.join(args.annotated_dir, f"{sid}_annotated.tsv")
        pos_path = os.path.join(args.shards_dir, f"{sid}_positions.txt")
        if not os.path.exists(ann_path) or not os.path.exists(pos_path):
            print(f"  {sid}: mancante (annotato o positions.txt), salto")
            continue

        fen_to_gameid = {}
        with open(pos_path, "r", errors="ignore") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 4:
                    continue
                fen, result, game_id, truncated = parts
                fen_to_gameid[fen] = f"{sid}_{game_id}"

        shard_count = 0
        missing_join = 0
        with open(ann_path, "r", errors="ignore") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 5:
                    continue
                fen = parts[0]
                game_id = fen_to_gameid.get(fen)
                if game_id is None:
                    missing_join += 1
                    continue
                rows_by_game.setdefault(game_id, []).append(parts)
                shard_count += 1

        total_positions += shard_count
        per_shard_counts.append({"shard_id": sid, "positions": shard_count,
                                  "join_mancanti": missing_join})
        if missing_join:
            print(f"  {sid}: {missing_join} righe annotate senza game_id corrispondente (scartate)")

    game_ids = list(rows_by_game.keys())
    rng = random.Random(args.seed)
    rng.shuffle(game_ids)
    n_val_games = max(1, round(len(game_ids) * args.val_fraction))
    val_games = set(game_ids[:n_val_games])

    train_rows = []
    val_rows = []
    for game_id, rows in rows_by_game.items():
        target = val_rows if game_id in val_games else train_rows
        target.extend(rows)

    rng.shuffle(train_rows)  # shuffle del solo training set, non della validazione

    with open(args.train_out, "w") as f:
        for row in train_rows:
            f.write("\t".join(row) + "\n")
    with open(args.val_out, "w") as f:
        for row in val_rows:
            f.write("\t".join(row) + "\n")

    composition = {
        "created_at": datetime.datetime.now().isoformat(),
        "shards_start": args.start,
        "shards_end": args.end,
        "shard_details": per_shard_counts,
        "total_positions": total_positions,
        "total_games": len(game_ids),
        "train_positions": len(train_rows),
        "train_games": len(game_ids) - len(val_games),
        "val_positions": len(val_rows),
        "val_games": len(val_games),
        "val_fraction_requested": args.val_fraction,
        "seed": args.seed,
    }
    with open(args.composition_out, "w") as f:
        json.dump(composition, f, indent=2)

    print()
    print(f"Shard inclusi: {args.start:05d}..{args.end:05d} ({len(per_shard_counts)} shard)")
    print(f"Posizioni totali: {total_positions:,}  (partite: {len(game_ids):,})")
    print(f"Train: {len(train_rows):,} posizioni, {len(game_ids) - len(val_games):,} partite ({args.train_out})")
    print(f"Val:   {len(val_rows):,} posizioni, {len(val_games):,} partite ({args.val_out})")
    print(f"Composizione: {args.composition_out}")


if __name__ == "__main__":
    main()
