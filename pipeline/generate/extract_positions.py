"""
Extraction + dedup + filters, BEFORE annotation — unlike the first
round, everything that isn't needed is discarded here before spending
Stockfish time on it, not after.

Games truncated by -maxmoves are not re-adjudicated here: Luna's score
is a judge correlated with its own bias (a +320/+370cp game never
converted would teach the network to be wrong exactly where Luna is
wrong). Each row instead carries game_id + truncated: which games get
truncated is decided later by resolve_truncated_wdl.py using Stockfish's
INDEPENDENT evaluation of the last sampled position, already computed
for free in the following annotation stage.

Usage:
  python extract_positions.py --pgn games.pgn --out positions.txt \
      --step 10 --skip-opening 11
"""
import argparse
import random

import chess
import chess.pgn


def dedup_key(board: chess.Board) -> str:
    """FEN without the move counters (halfmove clock + fullmove number):
    two positions identical apart from how long it took to reach them
    are the SAME position for a static evaluation network."""
    full_fen = board.fen()
    parts = full_fen.split(" ")
    return " ".join(parts[:4])  # pieces, side to move, castling, en passant


MAXMOVES_PLY = 160  # must match -maxmoves 80 in run_selfplay.sh (80 full moves)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pgn", required=True)
    ap.add_argument("--out", default="positions.txt")
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--skip-opening", type=int, default=11)
    ap.add_argument("--max-per-game", type=int, default=15,
                     help="cap on positions extracted from a single game, independent "
                          "of its length — structural protection against long/repetitive "
                          "games that would otherwise dominate the dataset with duplicates "
                          "(the real cause of the low uniqueness in the first generations)")
    args = ap.parse_args()

    seen = set()
    total_extracted = 0
    total_games = 0
    discarded_check = 0
    discarded_max_per_game = 0
    long_games_capped = 0

    with open(args.pgn, "r", errors="ignore") as fin, open(args.out, "w") as fout:
        game_id = 0
        while True:
            game = chess.pgn.read_game(fin)
            if game is None:
                break
            total_games += 1
            game_id += 1
            result = game.headers.get("Result", "*")

            board = game.board()
            node = game
            ply = 0
            extracted_this_game = 0
            hit_cap_this_game = False
            game_rows = []  # fen per row of this game, in play order
            # variable step (N + 0-3 jitter) instead of a fixed N: breaks
            # the resonance with shuttling cycles in endgames that
            # otherwise multiply a stuck-in-a-loop game into a dozen
            # duplicates. --step stays the base value, untouched.
            next_sample_ply = args.skip_opening + args.step + random.randint(0, 3)
            while node.variations:
                node = node.variation(0)
                board.push(node.move)
                ply += 1
                if board.is_game_over():
                    break
                if ply < next_sample_ply:
                    continue
                next_sample_ply = ply + args.step + random.randint(0, 3)

                if extracted_this_game >= args.max_per_game:
                    hit_cap_this_game = True
                    discarded_max_per_game += 1
                    continue

                if board.is_check():
                    discarded_check += 1
                    continue

                key = dedup_key(board)
                total_extracted += 1
                if key in seen:
                    continue
                seen.add(key)
                extracted_this_game += 1
                game_rows.append(board.fen())

            truncated = ply >= MAXMOVES_PLY
            if hit_cap_this_game:
                long_games_capped += 1

            # FEN <TAB> result <TAB> game_id <TAB> truncated: the result of
            # truncated games is provisional (cutechess always adjudicates
            # a draw for -maxmoves) and will be corrected by
            # resolve_truncated_wdl.py after Stockfish annotation.
            for fen in game_rows:
                fout.write(f"{fen}\t{result}\t{game_id}\t{int(truncated)}\n")

    unique = len(seen)
    pct = (unique / total_extracted * 100) if total_extracted else 0.0
    print(f"Games: {total_games}")
    print(f"Positions extracted (before dedup): {total_extracted}")
    print(f"Discarded because in check: {discarded_check}")
    print(f"Discarded by the max-per-game cap ({args.max_per_game}): {discarded_max_per_game}")
    print(f"Games that reached the cap: {long_games_capped} ({long_games_capped/max(total_games,1)*100:.1f}%)")
    print(f"Unique: {unique} ({pct:.1f}%)")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
