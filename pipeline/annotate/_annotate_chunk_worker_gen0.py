"""
Worker interno di annotate_incremental.py: annota un elenco di FEN (un file
di input, una riga per FEN) e scrive fen\teval_cp\tbestmove per riga
("NONE" al posto di eval_cp/bestmove se l'analisi fallisce). Lanciato come
PROCESSO OS SEPARATO (non multiprocessing.Pool): su Windows, chess.engine
dentro un worker di multiprocessing.Pool fallisce a creare il sottoprocesso
Stockfish (asyncio + ProactorEventLoop non sopravvive allo spawn) — lo
stesso schema a processi separati gia' usato altrove in questa pipeline
evita il problema.

Uso: python _annotate_chunk_worker.py <input_fens.txt> <output.tsv> <stockfish_path> <depth>
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
