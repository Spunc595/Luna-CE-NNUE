"""
Internal worker for annotate_incremental.py: annotates a list of FENs (an
input file, one FEN per line) and writes fen\teval_cp\tbestmove per line
("NONE" in place of eval_cp/bestmove if analysis fails). Launched as a
SEPARATE OS PROCESS (not multiprocessing.Pool): on Windows, chess.engine
inside a multiprocessing.Pool worker fails to spawn the Stockfish
subprocess (asyncio + ProactorEventLoop doesn't survive the spawn) — the
same separate-process pattern already used elsewhere in this pipeline
avoids the problem.

Usage: python _annotate_chunk_worker.py <input_fens.txt> <output.tsv> <stockfish_path> <depth>
"""
import sys

import chess
import chess.engine


def main():
    in_path, out_path, stockfish_path, depth = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])

    with open(in_path, "r", encoding="utf-8") as f:
        fens = [line.rstrip("\n") for line in f if line.strip()]

    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    limit = chess.engine.Limit(depth=depth)
    try:
        with open(out_path, "w", encoding="utf-8") as fout:
            for fen in fens:
                try:
                    board = chess.Board(fen)
                    info = engine.analyse(board, limit)
                    score = info["score"].pov(board.turn)
                    if score.is_mate():
                        eval_cp = 15000 if score.mate() > 0 else -15000
                    else:
                        cp = score.score()
                        eval_cp = cp
                    pv = info.get("pv")
                    bestmove = pv[0].uci() if pv else ""
                    if eval_cp is None:
                        fout.write(f"{fen}\tNONE\tNONE\n")
                    else:
                        fout.write(f"{fen}\t{eval_cp}\t{bestmove}\n")
                except Exception:
                    fout.write(f"{fen}\tNONE\tNONE\n")
                fout.flush()
    finally:
        engine.quit()


if __name__ == "__main__":
    main()
