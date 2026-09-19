"""
Train/validation split PER GAME (not per row): all the positions of one game
end up in the same set, otherwise the validation loss is optimistic
(positions of the same game are correlated: the network could "recognize" a
game seen in training from a single different position in the validation
set).

Reads one or more 6-column files (fen, result, game_id, eval_cp, is_mate,
bestmove) produced by resolve_truncated_wdl.py and writes train.tsv/val.tsv
in the same format. Games are shuffled with random.Random(seed) and the first
round(n_games * val_fraction) go to validation.

Usage:
  python split_train_val.py --in shard1.tsv shard2.tsv --train-out train.tsv       --val-out val.tsv --val-fraction 0.05 --seed 42
"""
import argparse
import random
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inputs", nargs="+", required=True)
    ap.add_argument("--train-out", required=True)
    ap.add_argument("--val-out", required=True)
    ap.add_argument("--val-fraction", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows_by_game = defaultdict(list)
    n_rows = 0
    for path in args.inputs:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) != 6:
                    continue
                game_id = parts[2]
                rows_by_game[game_id].append(line)
                n_rows += 1

    game_ids = list(rows_by_game.keys())
    rng = random.Random(args.seed)
    rng.shuffle(game_ids)

    n_val_games = max(1, round(len(game_ids) * args.val_fraction))
    val_games = set(game_ids[:n_val_games])

    n_train_rows = n_val_rows = 0
    with open(args.train_out, "w") as ftrain, open(args.val_out, "w") as fval:
        for game_id, rows in rows_by_game.items():
            target = fval if game_id in val_games else ftrain
            for line in rows:
                target.write(line + "\n")
            if game_id in val_games:
                n_val_rows += len(rows)
            else:
                n_train_rows += len(rows)

    print(f"Total games: {len(game_ids)}  (validation: {len(val_games)})")
    print(f"Total rows: {n_rows}")
    print(f"  train: {n_train_rows} ({args.train_out})")
    print(f"  val:   {n_val_rows} ({args.val_out})")


if __name__ == "__main__":
    main()
