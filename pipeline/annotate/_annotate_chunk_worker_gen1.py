"""
Worker interno di annotate_incremental_gen1.py: variante di
_annotate_chunk_worker.py per la generazione 1 — motore Luna invece di
Stockfish, limite a NODI invece che a profondita', UseNNUE=false forzato
(con probe di verifica prima di processare: non dare per assunta una
configurazione, dimostrala).

Uso: python _annotate_chunk_worker_gen1.py <input_fens.txt> <output.tsv> <luna_path> <nodes>
"""
import sys

import chess
import chess.engine


def main():
    in_path, out_path, luna_path, nodes = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])

    with open(in_path, "r", encoding="utf-8") as f:
        fens = [line.rstrip("\n") for line in f if line.strip()]

    engine = chess.engine.SimpleEngine.popen_uci(luna_path)
    engine.configure({"UseNNUE": False})

    # Probe: stessa posizione, UseNNUE opposto, i punteggi devono differire.
    probe = chess.Board()
    probe.push_san("e4"); probe.push_san("e5"); probe.push_san("Nf3")
    s_off = engine.analyse(probe, chess.engine.Limit(nodes=5000))["score"]
    engine.configure({"UseNNUE": True})
    s_on = engine.analyse(probe, chess.engine.Limit(nodes=5000))["score"]
    engine.configure({"UseNNUE": False})
    if s_off == s_on:
        sys.stderr.write(f"[ERRORE FATALE worker] UseNNUE non cambia l'eval (off={s_off} on={s_on})\n")
        engine.quit()
        sys.exit(1)

    limit = chess.engine.Limit(nodes=nodes)
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
