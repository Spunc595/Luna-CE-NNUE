"""
Generates random opening positions for self-play diversification: Luna
is deterministic beyond its own internal book (3183 positions), so
without genuine opening randomization self-play produces nearly
identical games.

For each position: plays N random LEGAL half-moves from the starting
position, then discards the resulting position if it's already decided
(low-depth Stockfish evaluation past the threshold) and retries. Writes
an EPD file, one position per line (FEN, no trailing moves).

Usage:
  python gen_random_openings.py --count 5000 --plies 9 --out openings.epd \
      --stockfish /usr/games/stockfish --eval-limit 200 --depth 6
"""
import argparse
import random
import subprocess
import sys


def quick_eval_cp(stockfish_proc, fen: str, depth: int) -> int | None:
    """Sends a position to an already-running Stockfish process (UCI) and
    reads the evaluation at a low depth. Reuses the same process for all
    positions instead of restarting it every time (which would be the
    real bottleneck here, not the search itself)."""
    stockfish_proc.stdin.write(f"position fen {fen}\n")
    stockfish_proc.stdin.write(f"go depth {depth}\n")
    stockfish_proc.stdin.flush()

    last_score = None
    while True:
        line = stockfish_proc.stdout.readline()
        if not line:
            return None
        if "score cp" in line:
            parts = line.split()
            idx = parts.index("cp")
            last_score = int(parts[idx + 1])
        elif "score mate" in line:
            last_score = 10000  # decisively decided, discard regardless
        if line.startswith("bestmove"):
            return last_score


def random_opening_fen(chess, plies: int, rng: random.Random) -> str:
    board = chess.Board()
    for _ in range(plies):
        legal = list(board.legal_moves)
        if not legal or board.is_game_over():
            break
        move = rng.choice(legal)
        board.push(move)
    return board.fen()


def main():
    import chess

    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--plies", type=int, default=9)
    ap.add_argument("--out", default="openings.epd")
    ap.add_argument("--stockfish", required=True)
    ap.add_argument("--eval-limit", type=int, default=200,
                     help="discard the position if |eval| exceeds this (cp)")
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-attempts-per-opening", type=int, default=20)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    proc = subprocess.Popen(
        [args.stockfish], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, bufsize=1,
    )
    proc.stdin.write("uci\n"); proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if "uciok" in line:
            break

    accepted = 0
    rejected = 0
    with open(args.out, "w") as f:
        while accepted < args.count:
            for _ in range(args.max_attempts_per_opening):
                fen = random_opening_fen(chess, args.plies, rng)
                score = quick_eval_cp(proc, fen, args.depth)
                if score is not None and abs(score) <= args.eval_limit:
                    f.write(fen + "\n")
                    accepted += 1
                    break
                rejected += 1
            else:
                # found nothing acceptable in N attempts: proceeds anyway,
                # doesn't block the whole batch over this
                pass

            if accepted % 500 == 0 and accepted > 0:
                print(f"  {accepted}/{args.count} openings accepted ({rejected} discarded so far)")

    proc.stdin.write("quit\n"); proc.stdin.flush()
    proc.wait(timeout=5)

    print(f"Done: {accepted} openings accepted, {rejected} discarded ({args.out})")


if __name__ == "__main__":
    main()
