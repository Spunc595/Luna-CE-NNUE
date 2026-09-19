"""
Last step before training in the 6-column chain
(extract_positions.py -> annotate -> resolve_truncated_wdl.py ->
split_train_val.py): fixes the result of games truncated by -maxmoves using
the INDEPENDENT evaluation of the last sampled position of that game
(already annotated by the annotator upstream, so at zero cost) instead of the
score of Luna's own play, which is correlated with its own conversion bias
(a game at +320/+370cp that was never converted would teach the network to be
wrong exactly where Luna is wrong).

This script never calls an engine: it only consumes the eval_cp already
written upstream, so it is engine-agnostic. Whether the chain it belongs to is
compliant depends entirely on the annotator that produced its input.

Games that were not truncated pass through unchanged. The output file goes
back to 6 columns (game_id stays, it is needed by the per-game train/validation
split; `truncated` was only internal bookkeeping of this step):
  fen  result  game_id  eval_cp  is_mate  bestmove_uci

--shard-tag prepends a prefix to game_id (e.g. "00001") so that games from
different shards do not collide when the files are combined before the split:
extract_positions.py numbers game_id from 1 inside each shard, not globally.

Usage:
  python resolve_truncated_wdl.py --in annotated.tsv --out training_ready.tsv       --shard-tag 00001
"""
import argparse

from pov import decisive_result_from_eval


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard-tag", default="",
                     help="prefix that makes game_id unique across shards")
    args = ap.parse_args()

    rows = []  # (fen, result, game_id, truncated, eval_cp, is_mate, bestmove)
    with open(args.inp, "r", errors="ignore") as fin:
        for line in fin:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 7:
                continue
            rows.append(parts)

    # Last row per game_id, in file order (extract_positions.py writes the
    # rows of a game in playing order).
    last_row_by_game = {}
    for row in rows:
        game_id = row[2]
        last_row_by_game[game_id] = row

    fixed_result_by_game = {}
    for game_id, last_row in last_row_by_game.items():
        _, _, _, truncated, eval_cp, _, _ = last_row
        if truncated != "1":
            continue
        fixed_result_by_game[game_id] = decisive_result_from_eval(last_row[0], int(eval_cp))

    tag_prefix = f"{args.shard_tag}_" if args.shard_tag else ""

    n_fixed_games = 0
    n_fixed_rows = 0
    seen_fixed_games = set()
    with open(args.out, "w") as fout:
        for fen, result, game_id, truncated, eval_cp, is_mate, bestmove in rows:
            if game_id in fixed_result_by_game:
                new_result = fixed_result_by_game[game_id]
                if new_result != result:
                    n_fixed_rows += 1
                    if game_id not in seen_fixed_games:
                        seen_fixed_games.add(game_id)
                        n_fixed_games += 1
                result = new_result
            fout.write(f"{fen}\t{result}\t{tag_prefix}{game_id}\t{eval_cp}\t{is_mate}\t{bestmove}\n")

    print(f"Total rows: {len(rows)}")
    print(f"Truncated games resolved from the annotator's eval: {len(fixed_result_by_game)}")
    print(f"Games whose label actually changed compared to cutechess: {n_fixed_games}")
    print(f"Rows rewritten: {n_fixed_rows}")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
