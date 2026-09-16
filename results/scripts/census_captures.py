"""
Census (no engine, no evaluation): on the assembled gen3 dataset, how many
positions have bestmove = capture, how many have promotion without capture,
and the breakdown by origin (normal-opening pool vs endgame pool) and by
piece count on the board. Numbers from this script are reported in
RESULTS.md 5.11.

Origin per game: from the PGN [FEN] tag at that game's starting position
(game_origins.txt), classified endgame if <=12 pieces, normal otherwise --
the same threshold used by the endgame pool itself (max_pieces=12).

Not included in this repository (see .gitignore, and the project rule that
no training data is ever committed): game_origins.txt, positions/*.txt,
annotated/*.tsv -- these are derived directly from the gen3 training
dataset. This script is committed for recomputability of the numbers in
RESULTS.md, not to be re-run standalone without that data.
"""
import glob
import os

import chess


def piece_count(fen: str) -> int:
    board_part = fen.split(" ")[0]
    return sum(1 for c in board_part if c.isalpha())


def load_game_origins(path):
    # (shard, game_idx) -> (origin, opening_piece_count)
    origins = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            shard, gid, fen_tag = parts
            fen = fen_tag.split('"')[1]
            pc = piece_count(fen)
            origin = "endgame" if pc <= 12 else "normal"
            origins[(shard, gid)] = origin
    return origins


def load_positions_gameid(path):
    # fen -> game_id (local, string)
    m = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                continue
            fen, result, game_id, truncated = parts
            m[fen] = game_id
    return m


def piece_bucket(n):
    if n <= 8:
        return "<=8"
    if n <= 12:
        return "9-12"
    if n <= 20:
        return "13-20"
    return "21-32"


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    origins = load_game_origins(os.path.join(base, "game_origins.txt"))
    print(f"game_origins loaded: {len(origins):,}")

    total = 0
    captures = 0
    promo_no_capture = 0
    by_origin = {"normal": [0, 0], "endgame": [0, 0]}  # [total, captures]
    by_bucket = {}  # bucket -> [total, captures]
    unmatched_origin = 0

    ann_files = sorted(glob.glob(os.path.join(base, "annotated", "gen3_shard_*_annotated.tsv")))
    for ann_path in ann_files:
        sid = os.path.basename(ann_path).replace("_annotated.tsv", "")
        pos_path = os.path.join(base, "positions", f"{sid}_positions.txt")
        fen_to_gid = load_positions_gameid(pos_path)

        with open(ann_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 5:
                    continue
                fen, eval_cp, bestmove, wdl_mover, depth = parts
                if bestmove in ("", "NONE"):
                    continue

                total += 1
                board = chess.Board(fen)
                try:
                    move = chess.Move.from_uci(bestmove)
                except ValueError:
                    continue

                is_cap = board.is_capture(move)
                is_promo = move.promotion is not None

                if is_cap:
                    captures += 1
                elif is_promo:
                    promo_no_capture += 1

                pc = piece_count(fen)
                bucket = piece_bucket(pc)
                by_bucket.setdefault(bucket, [0, 0])
                by_bucket[bucket][0] += 1
                if is_cap:
                    by_bucket[bucket][1] += 1

                gid = fen_to_gid.get(fen)
                origin = origins.get((sid, gid)) if gid is not None else None
                if origin is None:
                    unmatched_origin += 1
                else:
                    by_origin[origin][0] += 1
                    if is_cap:
                        by_origin[origin][1] += 1

    print(f"\nTotal positions censused: {total:,}")
    print(f"Bestmove = capture (en passant included): {captures:,} ({captures/total*100:.2f}%)")
    print(f"Promotion without capture: {promo_no_capture:,} ({promo_no_capture/total*100:.2f}%)")
    print(f"Positions with no traceable origin (game_id not found): {unmatched_origin:,}")

    print(f"\n{'Origin':<12}{'Total':>12}{'Captures':>12}{'%':>8}")
    for origin, (t, c) in by_origin.items():
        pct = c / t * 100 if t else 0.0
        print(f"{origin:<12}{t:>12,}{c:>12,}{pct:>7.2f}%")

    print(f"\n{'Pieces':<10}{'Total':>12}{'Captures':>12}{'%':>8}")
    for bucket in ["<=8", "9-12", "13-20", "21-32"]:
        if bucket in by_bucket:
            t, c = by_bucket[bucket]
            pct = c / t * 100 if t else 0.0
            print(f"{bucket:<10}{t:>12,}{c:>12,}{pct:>7.2f}%")


if __name__ == "__main__":
    main()
