"""
Incremental annotation tailing generation 1 (TCEC-compliant data) —
variant of annotate_incremental.py: Luna engine instead of Stockfish,
NODE limit (measured: 10,000) instead of depth, UseNNUE=false forced in
every worker with a verification probe. Same global cross-shard dedup
logic and WDL correction for truncated games (here the "independent"
judge is still Luna in classical evaluation, not Stockfish: a deliberate
choice of method, "never Stockfish, at no point in the chain, not even
to resolve truncated game results" — a note, not a hidden defect).

SEPARATE state folder (dedicated --out-dir, e.g. gen1_annotated/) from
the historical dataset: the global dedup must never be mixed between
the two.

Usage (continuous loop, tailing the generation on Oracle):
  python annotate_incremental_gen1.py --shards-dir gen1_shards_backup \
      --out-dir gen1_annotated --luna "<path-to-luna-repo>/target/release/luna.exe" \
      --nodes 10000 --workers 4 --follow
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

import chess

LUNA_REPO_DIR = os.path.expanduser("~/Desktop/rust-chess")


def get_annotation_engine_commit():
    """Commit dell'eseguibile usato per ANNOTARE, non per il self-play — i
    due possono divergere (es.: shard generati col binario pre-fix
    076defc, etichette con quello corretto). La differenza va scritta nel
    manifesto, non lasciata implicita."""
    try:
        result = subprocess.run(["git", "-C", LUNA_REPO_DIR, "rev-parse", "HEAD"],
                                 capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return "UNKNOWN"


def patch_manifest_with_annotation_commit(shards_dir: str, shard_id: str, annotation_nodes: int):
    """Aggiunge al manifesto (gia' scritto al momento del self-play) i campi
    relativi all'annotazione: commit del motore usato qui, nodi, timestamp,
    e una nota esplicita se il commit di self-play e quello di annotazione
    non coincidono (la differenza va scritta, non lasciata implicita). Se
    il manifesto non esiste (non dovrebbe succedere, ma non
    e' un errore fatale per l'annotazione stessa) lo segnala e prosegue."""
    manifest_path = os.path.join(shards_dir, f"{shard_id}.manifest.json")
    if not os.path.exists(manifest_path):
        print(f"  [ATTENZIONE] manifesto mancante per {shard_id} ({manifest_path}), salto il patch")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    annotation_commit = get_annotation_engine_commit()
    self_play_commit = manifest.get("engine_commit", "UNKNOWN")

    manifest["annotation_engine_commit"] = annotation_commit
    manifest["annotation_nodes_actual"] = annotation_nodes
    manifest["annotated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if annotation_commit != "UNKNOWN" and self_play_commit != "UNKNOWN" and annotation_commit != self_play_commit:
        manifest["commit_mismatch_note"] = (
            f"Self-play used engine commit {self_play_commit}; labels were annotated with "
            f"commit {annotation_commit}. These differ because the quiescence check_time fix "
            f"(076defc) landed after self-play for this shard had already run. The fix affects "
            f"time/node budget enforcement inside quiescence search, not move legality or board "
            f"state — positions extracted under the pre-fix commit remain valid. Only the label "
            f"(this shard's evaluation/bestmove annotation) comes from the post-fix commit."
        )

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

WIDE_BAND_CP = 200  # same band as pov.py/resolve_truncated_wdl.py

_WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_annotate_chunk_worker_gen1.py")


def dedup_key_hash(fen: str) -> int:
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


def annotate_batch(fens, luna_path, workers, nodes, tmp_dir,
                    timeout_per_position=0.05, min_timeout=180, stagger_seconds=2):
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
            [sys.executable, _WORKER_SCRIPT, in_path, out_path, luna_path, str(nodes)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        procs.append((proc, in_path, out_path, len(chunk)))
        # Stagger: launching several python-chess/asyncio subprocess trees
        # (each itself spawning luna.exe) in the same instant reproduced a
        # hang where the FIRST-launched worker never returned from
        # engine.quit() while the others completed normally — a suspected
        # Windows ProactorEventLoop race on near-simultaneous subprocess
        # creation. Confirmed the search itself is not the cause: a single
        # worker processed the exact same 71,618-position shard start to
        # finish with zero stalls. A small delay between launches is a
        # cheap mitigation; the timeout below is the real safety net.
        time.sleep(stagger_seconds)

    out = {}
    for proc, in_path, out_path, n_fens in procs:
        worker_timeout = max(min_timeout, n_fens * timeout_per_position)
        try:
            _, stderr = proc.communicate(timeout=worker_timeout)
            if proc.returncode != 0:
                print(f"  worker fallito (rc={proc.returncode}): {stderr[-500:] if stderr else ''}")
        except subprocess.TimeoutExpired:
            print(f"  worker oltre il timeout ({worker_timeout:.0f}s per {n_fens:,} posizioni) — "
                  f"lo termino e controllo comunque quanto ha gia' scritto")
            proc.kill()
            try:
                proc.communicate(timeout=10)
            except Exception:
                pass
        # Even if the worker was killed for timing out, the output file
        # may already hold the entire chunk (observed: a worker stuck on
        # shutdown had still written every line before hanging) — read it
        # anyway instead of discarding valid results. Any genuinely
        # missing rows fail the completeness check in process_shard,
        # which retries the whole shard next round.
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


def process_shard(shard_id: str, shards_dir: str, out_dir: str, luna_path: str,
                   workers: int, nodes: int, global_seen: set):
    pos_path = os.path.join(shards_dir, f"{shard_id}_positions.txt")
    out_path = os.path.join(out_dir, f"{shard_id}_annotated.tsv")
    tmp_path = out_path + ".tmp"

    if os.path.exists(out_path):
        return "already_done"
    if not os.path.exists(pos_path):
        return "missing"

    rows = []
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

    last_row_idx_by_game = {}
    for i, row in enumerate(rows):
        last_row_idx_by_game[row[2]] = i
    truncated_last_indices = {
        idx for game_id, idx in last_row_idx_by_game.items() if rows[idx][3] == "1"
    }

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
    fen_results = annotate_batch(to_annotate_fens, luna_path, workers, nodes, out_dir)

    if any(fen not in fen_results for fen in to_annotate_fens):
        print(f"  {shard_id}: risultati mancanti da un worker, scarto e ritento")
        return False

    n_dup = sum(1 for s in status if s == "dup")
    n_new_total = sum(1 for s in status if s == "new")
    n_force_total = sum(1 for s in status if s == "force")
    n_failed = sum(1 for i in to_annotate_idx if fen_results[rows[i][0]][0] is None)

    assert n_new_total + n_force_total + n_dup == n_input, \
        f"{shard_id}: partizione non esaustiva ({n_new_total}+{n_force_total}+{n_dup} != {n_input})"

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
                continue
            eval_cp, bestmove = fen_results[fen]
            if eval_cp is None:
                continue
            final_result = fixed_result_by_game.get(game_id, result)
            board = chess.Board(fen)
            wdl_mover = wdl_mover_from_result(final_result, board.turn == chess.WHITE)
            fout.write(f"{fen}\t{eval_cp}\t{bestmove}\t{wdl_mover}\t{nodes}\n")
            new_hashes_this_shard.append(hashes[i])
            n_written += 1

    os.replace(tmp_path, out_path)
    global_seen.update(new_hashes_this_shard)
    return new_hashes_this_shard, n_input, n_written, n_dup, n_force_total, n_failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--luna", required=True, help="binario Luna (UCI), con l'opzione UseNNUE (v3.1.3+)")
    ap.add_argument("--nodes", type=int, default=10000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--poll-seconds", type=int, default=60)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    state_path = os.path.join(args.out_dir, "global_seen.bin")
    global_seen = load_global_seen(state_path)
    print(f"[gen1] Stato globale caricato: {len(global_seen):,} hash gia' visti (nodes={args.nodes})")

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
            result = process_shard(sid, args.shards_dir, args.out_dir, args.luna,
                                    args.workers, args.nodes, global_seen)
            if result in ("already_done", "missing"):
                continue
            if result is False:
                continue
            new_hashes, n_input, n_written, n_dup, n_force, n_failed = result
            append_global_seen(state_path, new_hashes)
            patch_manifest_with_annotation_commit(args.shards_dir, sid, args.nodes)
            dt = time.time() - t0
            rate = n_written / dt if dt > 0 else 0
            print(f"{sid}: input={n_input:,}  scritte={n_written:,}  "
                  f"duplicati_saltati={n_dup:,}  forzate_per_correzione={n_force:,}  "
                  f"fallite={n_failed:,}  {dt:.1f}s ({rate:.1f} pos/s)")

        if not args.follow:
            return


if __name__ == "__main__":
    main()
