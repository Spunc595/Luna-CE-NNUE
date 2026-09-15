"""
Annotazione incrementale a inseguimento della generazione
(annotazioneeunicita.md, sezione 2).

Per ogni shard, in ordine:
  1. Salta se shard_NNNNN_annotated.tsv esiste gia' ed e' completo
     (idempotente/ripartibile).
  2. Dedup GLOBALE (fra shard, non solo dentro lo shard — quello lo fa
     gia' extract_positions.py): una posizione gia' vista in uno shard
     precedente non viene rianalizzata con Stockfish, a meno che non sia
     l'ultima posizione di una partita troncata da -maxmoves (serve
     comunque per correggere il WDL — vedi resolve_truncated_wdl.py).
  3. Annota con Stockfish depth 8 SOLO le posizioni nuove.
  4. Corregge il WDL delle partite troncate (stessa logica di
     resolve_truncated_wdl.py: banda larga sull'eval Stockfish
     dell'ultima posizione, non sul punteggio di Luna).
  5. Scrive fen / eval_cp (POV lato a muovere) / bestmove / wdl_mover
     (POV lato a muovere: 1/0/0.5) / depth — SOLO per le posizioni
     nuove, non per i duplicati cross-shard (altrimenti si rianalizza
     Stockfish per niente E si duplica nel dataset di training).
  6. Scrittura su file temporaneo + rename finale: un'interruzione lascia
     un .tmp scartabile, mai un file troncato che sembra completo.
  7. Il conteggio (annotate + duplicati-saltati + fallite) deve
     corrispondere alle righe in ingresso, altrimenti lo shard non e'
     considerato completo e viene ritentato dal principio al prossimo giro.
  8. Solo DOPO che lo shard e' completo, le sue posizioni nuove entrano
     nello stato globale di dedup (persistito su disco) — cosi' un
     riavvio a meta' shard non "consuma" hash che poi non risultano mai
     scritti da nessuna parte.

Uso (un giro sui shard disponibili, poi esce):
  python annotate_incremental.py --shards-dir shards_backup --out-dir annotated --workers 4

Uso (loop continuo, a inseguimento della generazione):
  python annotate_incremental.py --shards-dir shards_backup --out-dir annotated --workers 4 --follow
"""
import argparse
import hashlib
import os
import subprocess
import sys
import time

import chess

MATE_CP = 15000
WIDE_BAND_CP = 200  # stessa banda di pov.py/resolve_truncated_wdl.py
DEPTH = 8


def dedup_key_hash(fen: str) -> int:
    # STESSA chiave di measure_uniqueness.py: pezzi + tratto + arrocco +
    # en-passant, contatori halfmove/fullmove esclusi.
    parts = fen.split(" ")
    key = " ".join(parts[:4])
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), "big")


def load_global_seen(state_path: str) -> set:
    seen = set()
    if os.path.exists(state_path):
        with open(state_path, "rb") as f:
            data = f.read()
        n = len(data) // 8
        for i in range(n):
            seen.add(int.from_bytes(data[i * 8:(i + 1) * 8], "big"))
    return seen


def append_global_seen(state_path: str, new_hashes) -> None:
    with open(state_path, "ab") as f:
        for h in new_hashes:
            f.write(h.to_bytes(8, "big"))


_WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_annotate_chunk_worker.py")


def annotate_batch(fens, stockfish_path, workers, tmp_dir):
    """Lancia N processi OS separati (non multiprocessing.Pool: su Windows
    chess.engine dentro un worker di multiprocessing fallisce a creare il
    sottoprocesso Stockfish — asyncio/ProactorEventLoop non sopravvive
    allo spawn). Ogni worker scrive il proprio chunk su un file temporaneo
    dedicato, letto qui a fine corsa."""
    if not fens:
        return {}
    chunk_size = max(1, (len(fens) + workers - 1) // workers)
    chunks = [fens[i:i + chunk_size] for i in range(0, len(fens), chunk_size)]

    procs = []
    for idx, chunk in enumerate(chunks):
        in_path = os.path.join(tmp_dir, f"_chunk_{idx}.in")
        out_path = os.path.join(tmp_dir, f"_chunk_{idx}.out")
        with open(in_path, "w", encoding="utf-8") as f:
            for fen in chunk:
                f.write(fen + "\n")
        proc = subprocess.Popen(
            [sys.executable, _WORKER_SCRIPT, in_path, out_path, stockfish_path, str(DEPTH)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        procs.append((proc, in_path, out_path))

    out = {}
    for proc, in_path, out_path in procs:
        _, stderr = proc.communicate()
        if proc.returncode != 0:
            print(f"  worker fallito (rc={proc.returncode}): {stderr[-500:] if stderr else ''}")
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) != 3:
                        continue
                    fen, eval_cp_s, bestmove = parts
                    eval_cp = None if eval_cp_s == "NONE" else int(eval_cp_s)
                    out[fen] = (eval_cp, None if bestmove == "NONE" else bestmove)
        for p in (in_path, out_path):
            try:
                os.remove(p)
            except OSError:
                pass
    return out


def wdl_mover_from_result(result: str, side_to_move_is_white: bool) -> str:
    if result == "1/2-1/2":
        return "0.5"
    white_won = result == "1-0"
    mover_won = white_won == side_to_move_is_white
    return "1" if mover_won else "0"


def process_shard(shard_id: str, shards_dir: str, out_dir: str, stockfish_path: str,
                   workers: int, global_seen: set):
    """Ritorna "already_done" / "missing" / False (riconciliazione fallita,
    da ritentare) / una tupla di statistiche in caso di successo."""
    pos_path = os.path.join(shards_dir, f"{shard_id}_positions.txt")
    out_path = os.path.join(out_dir, f"{shard_id}_annotated.tsv")
    tmp_path = out_path + ".tmp"

    if os.path.exists(out_path):
        return "already_done"
    if not os.path.exists(pos_path):
        return "missing"

    rows = []  # (fen, result, game_id, truncated)
    with open(pos_path, "r", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 4:
                continue
            rows.append(parts)

    n_input = len(rows)

    # Ultima riga per game_id (nell'ordine del file): serve per la
    # correzione delle partite troncate, anche se quella posizione
    # risultasse un duplicato cross-shard.
    last_row_idx_by_game = {}
    for i, row in enumerate(rows):
        last_row_idx_by_game[row[2]] = i
    truncated_last_indices = {
        idx for game_id, idx in last_row_idx_by_game.items() if rows[idx][3] == "1"
    }

    # Partizione ESAUSTIVA delle righe in ingresso, per costruzione:
    # ogni riga e' "new" (mai vista, verra' annotata e scritta), "force"
    # (duplicato cross-shard ma ultima posizione di una partita troncata:
    # va annotata per la correzione WDL, ma non scritta ne' committata
    # allo stato globale) o "dup" (duplicato puro, saltata del tutto).
    hashes = [dedup_key_hash(row[0]) for row in rows]
    status = []
    for i, h in enumerate(hashes):
        if h not in global_seen:
            status.append("new")
        elif i in truncated_last_indices:
            status.append("force")
        else:
            status.append("dup")

    to_annotate_idx = [i for i in range(n_input) if status[i] in ("new", "force")]
    to_annotate_fens = [rows[i][0] for i in to_annotate_idx]
    fen_results = annotate_batch(to_annotate_fens, stockfish_path, workers, out_dir)

    # Verifica che OGNI fen mandata ad annotare abbia una voce nei
    # risultati (non solo che il valore non sia None): se manca una
    # chiave intera, un worker e' morto a meta' senza completare il suo
    # blocco — lo shard va scartato e ritentato, non salvato a meta'.
    if any(fen not in fen_results for fen in to_annotate_fens):
        print(f"  {shard_id}: risultati mancanti da un worker, scarto e ritento")
        return False

    n_dup = sum(1 for s in status if s == "dup")
    n_new_total = sum(1 for s in status if s == "new")
    n_force_total = sum(1 for s in status if s == "force")
    n_failed = sum(1 for i in to_annotate_idx if fen_results[rows[i][0]][0] is None)

    # Identita' per costruzione (new+force+dup esaurisce tutte le righe):
    # non e' un controllo che possa fallire, ma lo lasciamo esplicito per
    # far vedere subito se una futura modifica rompe la partizione.
    assert n_new_total + n_force_total + n_dup == n_input, \
        f"{shard_id}: partizione non esaustiva ({n_new_total}+{n_force_total}+{n_dup} != {n_input})"

    # Correzione WDL delle partite troncate, usando l'eval Stockfish
    # dell'ultima posizione (indipendente dal punteggio di Luna).
    fixed_result_by_game = {}
    for game_id, idx in last_row_idx_by_game.items():
        if rows[idx][3] != "1":
            continue
        fen = rows[idx][0]
        eval_cp, _ = fen_results.get(fen, (None, None))
        if eval_cp is None:
            continue
        board = chess.Board(fen)
        if abs(eval_cp) <= WIDE_BAND_CP:
            fixed_result_by_game[game_id] = "1/2-1/2"
        else:
            side_to_move_is_white = board.turn == chess.WHITE
            white_ahead = (eval_cp > 0) == side_to_move_is_white
            fixed_result_by_game[game_id] = "1-0" if white_ahead else "0-1"

    new_hashes_this_shard = []
    n_written = 0
    with open(tmp_path, "w") as fout:
        for i, (fen, result, game_id, truncated) in enumerate(rows):
            if status[i] != "new":
                continue  # "dup": mai annotata; "force": annotata ma non scritta
            eval_cp, bestmove = fen_results[fen]
            if eval_cp is None:
                continue  # fallita, non scritta (conteggiata in n_failed)
            final_result = fixed_result_by_game.get(game_id, result)
            board = chess.Board(fen)
            wdl_mover = wdl_mover_from_result(final_result, board.turn == chess.WHITE)
            fout.write(f"{fen}\t{eval_cp}\t{bestmove}\t{wdl_mover}\t{DEPTH}\n")
            new_hashes_this_shard.append(hashes[i])
            n_written += 1

    os.replace(tmp_path, out_path)
    global_seen.update(new_hashes_this_shard)
    return new_hashes_this_shard, n_input, n_written, n_dup, n_force_total, n_failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--stockfish", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--follow", action="store_true",
                     help="dopo aver smaltito l'arretrato, continua a controllare nuovi shard")
    ap.add_argument("--poll-seconds", type=int, default=60)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    state_path = os.path.join(args.out_dir, "global_seen.bin")
    global_seen = load_global_seen(state_path)
    print(f"Stato globale caricato: {len(global_seen):,} hash gia' visti")

    def find_pending_shards():
        ids = sorted(
            f[:-len("_positions.txt")]
            for f in os.listdir(args.shards_dir)
            if f.endswith("_positions.txt")
        )
        return [sid for sid in ids
                if not os.path.exists(os.path.join(args.out_dir, f"{sid}_annotated.tsv"))]

    while True:
        pending = find_pending_shards()
        if not pending:
            if not args.follow:
                print("Nessuno shard in sospeso.")
                return
            time.sleep(args.poll_seconds)
            continue

        for sid in pending:
            t0 = time.time()
            result = process_shard(sid, args.shards_dir, args.out_dir, args.stockfish,
                                    args.workers, global_seen)
            if result in ("already_done", "missing"):
                continue
            if result is False:
                continue  # riconciliazione fallita, gia' segnalato, ritenta al prossimo giro
            new_hashes, n_input, n_written, n_dup, n_force, n_failed = result
            append_global_seen(state_path, new_hashes)
            dt = time.time() - t0
            rate = n_written / dt if dt > 0 else 0
            print(f"{sid}: input={n_input:,}  scritte={n_written:,}  "
                  f"duplicati_saltati={n_dup:,}  forzate_per_correzione={n_force:,}  "
                  f"fallite={n_failed:,}  {dt:.1f}s ({rate:.1f} pos/s)")

        if not args.follow:
            return


if __name__ == "__main__":
    main()
