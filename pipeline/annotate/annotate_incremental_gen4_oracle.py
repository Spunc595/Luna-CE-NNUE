"""
Annotator for generation 4: the gen3 annotator plus what the gen1-gen3 runs were
missing (see LINEAGE.md, "Annotation failures"). Same logic otherwise (network
master via UseNNUE=true, global cross-shard dedup, WDL correction for truncated
games), meant to run on Oracle.

What is new compared with annotate_incremental_gen3_oracle.py:

- Every position whose annotation FAILS (the engine raised, so the worker wrote
  NONE) is recorded, one line each, in <out-dir>/failed_fens/<shard>_failed.tsv:
  fen, input row index, whether it was a "force" row (a duplicate re-annotated only
  to correct the game result). The dataset never contains them; this file is the
  only trace, and without it the question "which positions did the annotator lose"
  cannot be answered afterwards.
- The five counts the annotator always computed and always threw away are written
  into the shard's manifest: annotation_n_input, annotation_n_new,
  annotation_n_dup, annotation_n_force, annotation_n_written, annotation_n_failed.
  Manifests already published for gen1-gen3 are NOT touched.
- A rejection threshold, declared on the command line and with no default
  (--max-failed-rate): a shard whose failed / (new + force) exceeds it is NOT
  written, the annotator stops with status "errore" and the failed FENs are still
  saved. The decision on what to do next is a human one.
- stdout is line-buffered. The gen2/gen3 runs redirected stdout to a file without
  flushing and the logs came out empty: the per-shard counts were lost.

Failure semantics, verified in the code: a worker that times out or dies leaves
positions with NO result, and the shard is discarded and retried (nothing is
counted as failed). Only a per-position exception is counted as failed, and if
the engine process itself dies mid-chunk every later position of that chunk raises
too, so real failures tend to come in contiguous runs.

Usage:
  python3 annotate_incremental_gen4_oracle.py \
      --shards-dir DIR --out-dir DIR --luna PATH --status-file FILE \
      --nodes N --workers 4 --max-failed-rate 0.001 [--follow]
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

LUNA_REPO_DIR = os.path.expanduser("~/gen1_classical/luna-src")
MACHINE_NAME = "oracle"


def get_annotation_engine_commit():
    try:
        result = subprocess.run(["git", "-C", LUNA_REPO_DIR, "rev-parse", "HEAD"],
                                 capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return "UNKNOWN"


def patch_manifest_with_annotation_commit(shards_dir: str, shard_id: str, annotation_nodes: int,
                                          counts: dict = None):
    manifest_path = os.path.join(shards_dir, f"{shard_id}.manifest.json")
    if not os.path.exists(manifest_path):
        print(f"  [WARNING] manifest missing for {shard_id} ({manifest_path}), skipping the patch")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    annotation_commit = get_annotation_engine_commit()
    self_play_commit = manifest.get("engine_commit", "UNKNOWN")

    manifest["annotation_engine_commit"] = annotation_commit
    manifest["annotation_machine"] = MACHINE_NAME
    manifest["annotation_nodes_actual"] = annotation_nodes
    manifest["annotated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if counts is not None:
        for name, value in counts.items():
            manifest["annotation_" + name] = value
    if annotation_commit != "UNKNOWN" and self_play_commit != "UNKNOWN" and annotation_commit != self_play_commit:
        manifest["commit_mismatch_note"] = (
            f"Self-play used engine commit {self_play_commit}; labels were annotated with "
            f"commit {annotation_commit} on machine {MACHINE_NAME}. Positions extracted under "
            f"the self-play commit remain valid; only the label comes from the annotation commit."
        )

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


WIDE_BAND_CP = 200

# The generic worker (UseNNUE=true, external net, probe that the net is really active). On Oracle
# the gen3 run used a copy named _annotate_chunk_worker_gen3.py, byte-identical to the gen2 one.
_WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_annotate_chunk_worker_gen2.py")


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


# PROTOCOL TOKEN, NOT TEXT: the field name "stato" and its values "in_corso" /
# "completato" / "errore" are deliberately Italian. They are read by watchers
# OUTSIDE this repository (the status-file / bucket watcher on the server), which
# match those exact strings. Translating them breaks those consumers silently.
# Do not "fix" them in a translation pass; change them only together with the
# consumers.
def write_status(status_path, **fields):
    if not status_path:
        return
    fields["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tmp = status_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(fields, f, indent=2)
    os.replace(tmp, status_path)


def annotate_batch(fens, luna_path, workers, nodes, tmp_dir,
                    timeout_per_position=0.15, min_timeout=180, stagger_seconds=2):
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
        time.sleep(stagger_seconds)

    out = {}
    for proc, in_path, out_path, n_fens in procs:
        worker_timeout = max(min_timeout, n_fens * timeout_per_position)
        try:
            _, stderr = proc.communicate(timeout=worker_timeout)
            if proc.returncode != 0:
                print(f"  worker failed (rc={proc.returncode}): {stderr[-500:] if stderr else ''}")
        except subprocess.TimeoutExpired:
            print(f"  worker over the timeout ({worker_timeout:.0f}s for {n_fens:,} positions) — "
                  f"terminating it and checking anyway how much it has already written")
            proc.kill()
            try:
                proc.communicate(timeout=10)
            except Exception:
                pass
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
                   workers: int, nodes: int, global_seen: set, max_failed_rate: float):
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
        print(f"  {shard_id}: results missing from a worker, discarding the shard and retrying")
        return False

    n_dup = sum(1 for s in status if s == "dup")
    n_new_total = sum(1 for s in status if s == "new")
    n_force_total = sum(1 for s in status if s == "force")
    n_failed = sum(1 for i in to_annotate_idx if fen_results[rows[i][0]][0] is None)

    failed_idx = [i for i in to_annotate_idx if fen_results[rows[i][0]][0] is None]
    if failed_idx:
        failed_dir = os.path.join(out_dir, "failed_fens")
        os.makedirs(failed_dir, exist_ok=True)
        with open(os.path.join(failed_dir, f"{shard_id}_failed.tsv"), "w", encoding="utf-8", newline="\n") as f:
            for i in failed_idx:
                f.write(f"{rows[i][0]}\t{i}\t{int(status[i] == 'force')}\n")
    n_sent = n_new_total + n_force_total
    if n_sent and n_failed / n_sent > max_failed_rate:
        raise RuntimeError(
            f"{shard_id}: {n_failed:,} of {n_sent:,} annotations failed "
            f"({n_failed / n_sent:.4%} > the declared limit {max_failed_rate:.4%}); shard NOT written, "
            f"failed FENs saved in {os.path.join(out_dir, 'failed_fens')}")

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
    counts = dict(n_input=n_input, n_new=n_new_total, n_dup=n_dup, n_force=n_force_total,
                  n_written=n_written, n_failed=n_failed)
    return new_hashes_this_shard, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--luna", required=True)
    ap.add_argument("--nodes", type=int, default=20000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--poll-seconds", type=int, default=60)
    ap.add_argument("--status-file", default=None)
    ap.add_argument("--max-failed-rate", type=float, required=True,
                    help="no default on purpose (it changes what gets written): a shard whose "
                         "failed / (new + force) exceeds it is not written and the run stops")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    os.makedirs(args.out_dir, exist_ok=True)
    state_path = os.path.join(args.out_dir, "global_seen.bin")
    global_seen = load_global_seen(state_path)
    print(f"[gen4/oracle] Global state loaded: {len(global_seen):,} hashes already seen (nodes={args.nodes})")

    def find_all_shard_ids():
        return sorted(
            f[:-len("_positions.txt")]
            for f in os.listdir(args.shards_dir)
            if f.endswith("_positions.txt")
        )

    def find_pending_shards():
        return [sid for sid in find_all_shard_ids()
                if not os.path.exists(os.path.join(args.out_dir, f"{sid}_annotated.tsv"))]

    total_shards = len(find_all_shard_ids())
    done_shards = total_shards - len(find_pending_shards())
    write_status(args.status_file, stato="in_corso",
                 shard_fatti=done_shards, shard_totali=total_shards,
                 posizioni_annotate=0, pos_per_sec=0.0, ultimo_errore=None)

    while True:
        pending = find_pending_shards()
        if not pending:
            done_shards = total_shards
            write_status(args.status_file, stato="completato",
                         shard_fatti=done_shards, shard_totali=total_shards,
                         posizioni_annotate=None, pos_per_sec=0.0, ultimo_errore=None)
            if not args.follow:
                print("No pending shards.")
                return
            time.sleep(args.poll_seconds)
            continue

        for sid in pending:
            t0 = time.time()
            try:
                result = process_shard(sid, args.shards_dir, args.out_dir, args.luna,
                                        args.workers, args.nodes, global_seen, args.max_failed_rate)
            except Exception as e:
                write_status(args.status_file, stato="errore",
                             shard_fatti=done_shards, shard_totali=total_shards,
                             pos_per_sec=0.0, ultimo_errore={"shard": sid, "messaggio": str(e)})
                raise
            if result in ("already_done", "missing"):
                continue
            if result is False:
                write_status(args.status_file, stato="errore",
                             shard_fatti=done_shards, shard_totali=total_shards,
                             pos_per_sec=0.0,
                             ultimo_errore={"shard": sid, "messaggio": "risultati mancanti da un worker"})
                continue
            new_hashes, counts = result
            n_input, n_written, n_dup = counts["n_input"], counts["n_written"], counts["n_dup"]
            n_force, n_failed = counts["n_force"], counts["n_failed"]
            append_global_seen(state_path, new_hashes)
            patch_manifest_with_annotation_commit(args.shards_dir, sid, args.nodes, counts)
            dt = time.time() - t0
            rate = n_written / dt if dt > 0 else 0
            done_shards += 1
            print(f"{sid}: input={n_input:,}  written={n_written:,}  "
                  f"dup_skipped={n_dup:,}  forced_for_correction={n_force:,}  "
                  f"failed={n_failed:,}  {dt:.1f}s ({rate:.1f} pos/s)")
            write_status(args.status_file, stato="in_corso",
                         shard_fatti=done_shards, shard_totali=total_shards,
                         ultimo_shard=sid, posizioni_scritte_ultimo_shard=n_written,
                         pos_per_sec=round(rate, 1), ultimo_errore=None)

        if not args.follow:
            return


if __name__ == "__main__":
    main()
