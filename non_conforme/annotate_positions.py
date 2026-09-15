"""
Annota posizioni gia estratte/deduplicate (output di extract_positions.py:
FEN <TAB> risultato <TAB> game_id <TAB> truncated, una per riga) con
Stockfish: punteggio, profondita raggiunta, e bestmove (necessaria per il
filtro "mossa migliore = cattura" di piu avanti — l'assenza di questo campo
nella pipeline precedente ha reso quel filtro impossibile).

game_id/truncated passano invariati: servono a resolve_truncated_wdl.py per
correggere il risultato delle partite troncate da -maxmoves usando la
valutazione Stockfish gia' calcolata qui, non il punteggio di Luna.

Output: una riga per posizione, campi separati da TAB:
  fen  risultato  game_id  truncated  eval_cp  is_mate  bestmove_uci

Uso:
  python annotate_positions.py --in positions.txt --out annotated.tsv \
      --stockfish /usr/games/stockfish --depth 8
"""
import argparse
import time

import chess
import chess.engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stockfish", required=True)
    ap.add_argument("--depth", type=int, default=8)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--hash", type=int, default=128)
    ap.add_argument("--max-positions", type=int, default=None)
    args = ap.parse_args()

    limit = chess.engine.Limit(depth=args.depth)
    engine = chess.engine.SimpleEngine.popen_uci(args.stockfish)
    try:
        engine.configure({"Threads": args.threads, "Hash": args.hash})
    except Exception as e:
        print(f"configure ignorato: {e}")

    annotated = 0
    skipped = 0
    t0 = time.time()

    with open(args.inp, "r", errors="ignore") as fin, open(args.out, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 4:
                skipped += 1
                continue
            fen, result, game_id, truncated = parts

            if args.max_positions is not None and annotated >= args.max_positions:
                break

            try:
                board = chess.Board(fen)
                info = engine.analyse(board, limit)
            except Exception as e:
                print(f"analisi saltata ({fen}): {e}")
                skipped += 1
                continue

            score = info["score"].pov(board.turn)
            if score.is_mate():
                eval_cp = 15000 if score.mate() > 0 else -15000
                is_mate = 1
            else:
                cp = score.score()
                if cp is None:
                    skipped += 1
                    continue
                eval_cp = cp
                is_mate = 0

            pv = info.get("pv")
            bestmove = pv[0].uci() if pv else ""

            fout.write(f"{fen}\t{result}\t{game_id}\t{truncated}\t{eval_cp}\t{is_mate}\t{bestmove}\n")
            annotated += 1

            if annotated % 1000 == 0:
                dt = time.time() - t0
                rate = annotated / dt if dt > 0 else 0
                print(f"  annotate={annotated:,}  scartate={skipped}  ({rate:.1f}/s)")

    engine.quit()
    dt = time.time() - t0
    rate = annotated / dt if dt > 0 else 0
    print(f"\nFatto: {annotated:,} posizioni annotate, {skipped} scartate, in {dt:.1f}s ({rate:.1f}/s)")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
