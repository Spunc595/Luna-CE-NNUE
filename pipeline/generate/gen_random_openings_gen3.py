"""
Variante di gen_random_openings_luna.py per la generazione 2: il filtro
"posizione non ancora decisa" usa la valutazione della RETE GEN1 (UseNNUE
di default true, rete caricata esternamente accanto al binario come
luna.nnue), non la classica -- coerente con quello che il self-play della
gen2 usera' davvero (gen2.md: "self-play con la rete gen1, non la
classica").

Uso:
  python gen_random_openings_gen2.py --count 155000 --plies 9 --out normal_openings.epd \
      --engine ./engine/luna --eval-limit 200 --depth 6
"""
import argparse
import random
import subprocess
import sys


def quick_eval_cp(engine_proc, fen: str, depth: int):
    engine_proc.stdin.write(f"position fen {fen}\n")
    engine_proc.stdin.write(f"go depth {depth}\n")
    engine_proc.stdin.flush()

    last_score = None
    while True:
        line = engine_proc.stdout.readline()
        if not line:
            return None
        if "score cp" in line:
            parts = line.split()
            idx = parts.index("cp")
            last_score = int(parts[idx + 1])
        elif "score mate" in line:
            last_score = 10000
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
    ap.add_argument("--out", default="normal_openings.epd")
    ap.add_argument("--engine", required=True, help="binario Luna (UCI) con la rete gen1 caricata esternamente")
    ap.add_argument("--eval-limit", type=int, default=200)
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-attempts-per-opening", type=int, default=20)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    proc = subprocess.Popen(
        [args.engine], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, bufsize=1,
    )
    proc.stdin.write("uci\n"); proc.stdin.flush()
    nnue_confirmed = False
    while True:
        line = proc.stdout.readline()
        if "NNUE: loaded" in line:
            nnue_confirmed = True
        if "uciok" in line:
            break
    if not nnue_confirmed:
        print("[ERRORE FATALE] Il motore non conferma di aver caricato una rete NNUE esterna. Interrompo.")
        proc.terminate()
        sys.exit(1)
    print("[PROVA] rete NNUE esterna confermata caricata prima di generare le aperture (self-play della gen2 la usera' per davvero).")

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
                pass

            if accepted % 2000 == 0 and accepted > 0:
                print(f"  {accepted}/{args.count} aperture accettate ({rejected} scartate finora)")

    proc.stdin.write("quit\n"); proc.stdin.flush()
    proc.wait(timeout=5)

    print(f"Fatto: {accepted} aperture accettate, {rejected} scartate ({args.out})")


if __name__ == "__main__":
    main()
