"""
Incremental annotation, tailing the generation.

For each shard, in order:
  1. Skip if shard_NNNNN_annotated.tsv already exists and is complete
     (idempotent/resumable).
  2. GLOBAL dedup (across shards, not just within a shard — that's
     already done by extract_positions.py): a position already seen in
     an earlier shard is not re-analyzed with Stockfish, unless it's the
     last position of a game truncated by -maxmoves (still needed to
     correct the WDL — see resolve_truncated_wdl.py).
  3. Annotate with Stockfish depth 8 ONLY the new positions.
  4. Correct the WDL of truncated games (same logic as
     resolve_truncated_wdl.py: wide band on Stockfish's eval of the last
     position, not on Luna's score).
  5. Write fen / eval_cp (POV side to move) / bestmove / wdl_mover
     (POV side to move: 1/0/0.5) / depth — ONLY for new positions, not
     for cross-shard duplicates (otherwise Stockfish re-analyzes for
     nothing AND the position gets duplicated in the training dataset).
  6. Write to a temp file + final rename: an interruption leaves a
     discardable .tmp, never a truncated file that looks complete.
  7. The count (annotated + duplicates-skipped + failed) must match the
     input rows, otherwise the shard isn't considered complete and gets
     retried from scratch next round.
  8. Only AFTER a shard is complete do its new positions enter the
     global dedup state (persisted to disk) — so a restart mid-shard
     doesn't "consume" hashes that then never get written anywhere.

Usage (one pass over available shards, then exits):
  python annotate_incremental.py --shards-dir shards_backup --out-dir annotated --workers 4

Usage (continuous loop, tailing the generation):
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
WIDE_BAND_CP = 200  # same band as pov.py/resolve_truncated_wdl.py
DEPTH = 8


def dedup_key_hash(fen: str) -> int:
    # SAME key as measure_uniqueness.py: pieces + side to move + castling +
    # en passant, halfmove/fullmove counters excluded.
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
    """Launches N separate OS processes (not multiprocessing.Pool: on
    Windows, chess.engine inside a multiprocessing worker fails to spawn
    the Stockfish subprocess — asyncio/ProactorEventLoop doesn't survive
    the spawn). Each worker writes its own chunk to a dedicated temp
    file, read back here at the end."""
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
    """Returns "already_done" / "missing" / False (reconciliation failed,
    to be retried) / a stats tuple on success."""
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

    # Last row per game_id (in file order): needed for correcting
    # truncated games, even if that position turns out to be a
    # cross-shard duplicate.
    last_row_idx_by_game = {}
    for i, row in enumerate(rows):
        last_row_idx_by_game[row[2]] = i
    truncated_last_indices = {
        idx for game_id, idx in last_row_idx_by_game.items() if rows[idx][3] == "1"
    }

    # EXHAUSTIVE partition of the input rows, by construction: every row
    # is "new" (never seen, will be annotated and written), "force"
    # (cross-shard duplicate but the last position of a truncated game:
    # needs annotating for the WDL correction, but not written nor
    # committed to the global state) or "dup" (pure duplicate, skipped
    # entirely).
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

    # Verify that EVERY fen sent for annotation has an entry in the
    # results (not just that the value isn't None): if an entire key is
    # missing, a worker died halfway without finishing its chunk — the
    # shard must be discarded and retried, not saved half-done.
    if any(fen not in fen_results for fen in to_annotate_fens):
        print(f"  {shard_id}: risultati mancanti da un worker, scarto e ritento")
        return False

    n_dup = sum(1 for s in status if s == "dup")
    n_new_total = sum(1 for s in status if s == "new")
    n_force_total = sum(1 for s in status if s == "force")
    n_failed = sum(1 for i in to_annotate_idx if fen_results[rows[i][0]][0] is None)

    # Identity by construction (new+force+dup exhausts all rows): not a
    # check that can actually fail, but left explicit so a future change
    # that breaks the partition shows up immediately.
    assert n_new_total + n_force_total + n_dup == n_input, \
        f"{shard_id}: partizione non esaustiva ({n_new_total}+{n_force_total}+{n_dup} != {n_input})"

    # WDL correction for truncated games, using Stockfish's eval of the
    # last position (independent of Luna's score).
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
                continue  # "dup": never annotated; "force": annotated but not written
            eval_cp, bestmove = fen_results[fen]
            if eval_cp is None:
                continue  # failed, not written (counted in n_failed)
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
                continue  # reconciliation failed, already reported, retry next round
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
