"""
Genera posizioni di apertura casuali per la diversificazione del self-play:
Luna e deterministica oltre il proprio
libro interno (3183 posizioni), quindi senza una vera randomizzazione
delle aperture il self-play produce partite quasi identiche.

Per ogni posizione: gioca N semi-mosse LEGALI scelte a caso dalla
posizione iniziale, poi scarta se la posizione risultante e gia decisa
(valutazione Stockfish a profondita bassa oltre la soglia) e riprova.
Scrive un file EPD, una posizione per riga (FEN, senza mosse in coda).

Uso:
  python gen_random_openings.py --count 5000 --plies 9 --out openings.epd \
      --stockfish /usr/games/stockfish --eval-limit 200 --depth 6
"""
import argparse
import random
import subprocess
import sys


def quick_eval_cp(stockfish_proc, fen: str, depth: int) -> int | None:
    """Invia una posizione a un processo Stockfish gia avviato (UCI) e
    legge la valutazione a una profondita bassa. Riusa lo stesso processo
    per tutte le posizioni invece di riavviarlo ogni volta (che sarebbe
    il vero collo di bottiglia qui, non la ricerca in se)."""
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
            last_score = 10000  # decisamente deciso, scartare comunque
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
                     help="scarta la posizione se |eval| supera questo (cp)")
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
                # non ha trovato nulla di accettabile in N tentativi:
                # prosegue comunque, non blocca l'intero batch per questo
                pass

            if accepted % 500 == 0 and accepted > 0:
                print(f"  {accepted}/{args.count} aperture accettate ({rejected} scartate finora)")

    proc.stdin.write("quit\n"); proc.stdin.flush()
    proc.wait(timeout=5)

    print(f"Fatto: {accepted} aperture accettate, {rejected} scartate ({args.out})")


if __name__ == "__main__":
    main()
