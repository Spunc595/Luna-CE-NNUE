"""
Estrazione + deduplica + filtri, PRIMA dell'annotazione — a differenza
del primo giro, qui si scarta tutto quello che non serve prima di
spendere tempo di Stockfish, non dopo.

Le partite troncate da -maxmoves non vengono ri-aggiudicate qui: il
punteggio di Luna e' un giudice correlato al suo stesso bias (una partita
+320/+370cp mai convertita insegnerebbe alla rete a sbagliare esattamente
dove sbaglia Luna). Ogni riga porta invece game_id + truncated: chi tronca
la partita viene deciso poi da resolve_truncated_wdl.py usando la
valutazione INDIPENDENTE di Stockfish sull'ultima posizione campionata,
gia' calcolata gratis nello stadio di annotazione successivo.

Uso:
  python extract_positions.py --pgn partite.pgn --out positions.txt \
      --step 10 --skip-opening 11
"""
import argparse
import random

import chess
import chess.pgn


def dedup_key(board: chess.Board) -> str:
    """FEN senza i contatori di mossa (halfmove clock + fullmove number):
    due posizioni identiche a parte quanto tempo ci si e messi ad
    arrivarci sono la STESSA posizione per una rete di valutazione
    statica."""
    full_fen = board.fen()
    parts = full_fen.split(" ")
    return " ".join(parts[:4])  # pieces, side to move, castling, en passant


MAXMOVES_PLY = 160  # deve combaciare con -maxmoves 80 in run_selfplay.sh (80 mosse intere)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pgn", required=True)
    ap.add_argument("--out", default="positions.txt")
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--skip-opening", type=int, default=11)
    ap.add_argument("--max-per-game", type=int, default=15,
                     help="tetto di posizioni estratte da una singola partita, indipendente "
                          "dalla sua lunghezza — protezione strutturale contro le partite "
                          "lunghe/ripetitive che altrimenti dominano il dataset di duplicati "
                          "(causa reale della bassa unicita nelle prime generazioni)")
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
            game_rows = []  # fen per riga di questa partita, nell'ordine di gioco
            # passo variabile (N + scarto 0-3) invece di N fisso: rompe la
            # risonanza con i cicli di navetta nei finali che altrimenti
            # moltiplicano una partita incartata in una decina di duplicati.
            # --step resta il valore base, non toccato.
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

            # FEN <TAB> risultato <TAB> game_id <TAB> truncated: il risultato
            # delle partite troncate e' provvisorio (cutechess aggiudica
            # sempre patta per -maxmoves) e verra' corretto da
            # resolve_truncated_wdl.py dopo l'annotazione Stockfish.
            for fen in game_rows:
                fout.write(f"{fen}\t{result}\t{game_id}\t{int(truncated)}\n")

    unique = len(seen)
    pct = (unique / total_extracted * 100) if total_extracted else 0.0
    print(f"Partite: {total_games}")
    print(f"Posizioni estratte (prima della dedup): {total_extracted}")
    print(f"Scartate perche sotto scacco: {discarded_check}")
    print(f"Scartate per tetto max-per-partita ({args.max_per_game}): {discarded_max_per_game}")
    print(f"Partite che hanno raggiunto il tetto: {long_games_capped} ({long_games_capped/max(total_games,1)*100:.1f}%)")
    print(f"Uniche: {unique} ({pct:.1f}%)")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
