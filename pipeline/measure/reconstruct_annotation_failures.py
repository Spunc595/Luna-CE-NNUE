"""
Reconstructs, per shard, which input positions the annotator dropped because
their annotation FAILED (as opposed to being skipped as duplicates), from the
files that survive: <prefix>_shard_NNNNN_positions.txt (input) and
<prefix>_shard_NNNNN_annotated.tsv (output). Read-only.

Why it is needed: annotate_incremental_gen*.py counts n_failed but never stores
it, and the stdout log of the Oracle runs is empty (block-buffered, never
flushed), so for most shards the count does not exist.

Method. The annotator classifies each input row of a shard, in order, as
  new    : the hash of the first four FEN fields is NOT in global_seen
  force  : in global_seen, but the last row of a game truncated by -maxmoves
           (re-annotated to fix the game result, never written)
  dup    : in global_seen, skipped
and writes only the "new" rows whose annotation did not fail. global_seen is
updated after each shard with the hashes of the rows written. So, processing
shards in numeric order and rebuilding global_seen from the outputs:

  input row, "new" at that point, FEN missing from the shard's output -> FAILED
  input row missing from the output, hash already in global_seen      -> dup/force

Limits (declared, not hidden):
  * a position that fails in one shard and succeeds in a later one enters
    global_seen and is classified dup in the shard where it failed: failures are
    UNDER-counted;
  * the dedup key is the first four FEN fields, not the whole FEN;
  * it needs the order in which the shards were annotated, because "new" depends on
    what was written before. The default is numeric order; that is WRONG for gen2
    (its shards were not annotated in numeric order: the PC/Oracle hand-over).
    global_seen.bin is appended shard by shard in processing order, so
    --order-from-global-seen recovers the true order from it;
  * a failed "force" row (a duplicate re-annotated for the game result) is
    indistinguishable from a dup and does not affect the output.
When the original counts exist (--log, the stdout lines `input=... fallite=...`)
they are compared shard by shard: that is the gate on the reconstruction. When
they do not exist the result is an ESTIMATE, not a measurement.

Usage:
  python reconstruct_annotation_failures.py --shards-dir DIR --annotated-dir DIR \
      --prefix gen1 --start 1 --end 46 --csv-out rates.csv --failed-out failed.tsv \
      [--log annotate.log] [--global-seen global_seen.bin] [--order-from-global-seen]
"""
import argparse
import hashlib
import os
import re
import sys
from collections import Counter

# gen1-gen3 wrote the Italian field names, gen4 writes the English ones
LOG_RE = re.compile(
    r"(\S+_shard_\d+): input=([\d,]+)\s+(?:scritte|written)=([\d,]+)\s+(?:duplicati_saltati|dup_skipped)=([\d,]+)"
    r"\s+(?:forzate_per_correzione|forced_for_correction)=([\d,]+)\s+(?:fallite|failed)=([\d,]+)")


def key_hash(fen):
    key = " ".join(fen.split(" ")[:4])
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), "big")


def read_positions(path):
    rows = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 4:
                continue
            rows.append(parts)  # fen, result, game_id, truncated
    return rows


def read_output_fens(path):
    fens = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 5:
                continue
            fens.append(parts[0])
    return fens


def parse_log(path):
    out = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = LOG_RE.match(line)
            if m:
                v = [int(x.replace(",", "")) for x in m.groups()[1:]]
                out[m.group(1)] = dict(n_input=v[0], n_written=v[1], n_dup=v[2], n_force=v[3], n_failed=v[4])
    return out


def load_global_seen_seq(path):
    """The hashes in the order they were appended (one block per processed shard)."""
    data = open(path, "rb").read()
    return [int.from_bytes(data[i:i + 8], "big") for i in range(0, len(data) - len(data) % 8, 8)]


def order_from_global_seen(seq, shard_hashes):
    """Shard ids in processing order: the order in which their written hashes first
    appear in global_seen.bin. shard_hashes: shard id -> set of hashes it wrote."""
    owner = {}
    for sid, hs in shard_hashes.items():
        for h in hs:
            owner.setdefault(h, sid)
    order, seen_sid = [], set()
    for h in seq:
        sid = owner.get(h)
        if sid is not None and sid not in seen_sid:
            seen_sid.add(sid)
            order.append(sid)
    return order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--annotated-dir", required=True)
    ap.add_argument("--prefix", required=True, help="e.g. gen1 -> gen1_shard_00001_positions.txt")
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--csv-out", required=True)
    ap.add_argument("--failed-out", default=None,
                    help="TSV of the reconstructed failed positions: shard, input_index, "
                         "candidate_index, fen")
    ap.add_argument("--log", default=None, help="original annotator stdout, for the per-shard gate")
    ap.add_argument("--global-seen", default=None, help="the annotator's global_seen.bin, to compare")
    ap.add_argument("--order-from-global-seen", action="store_true",
                    help="process the shards in the order recorded in --global-seen instead of numeric")
    args = ap.parse_args()

    truth = parse_log(args.log) if args.log else {}
    seen = set()
    input_keys = set()   # every distinct dedup key present in any input file
    header = ["shard", "processing_rank", "n_input", "n_output", "n_not_output", "n_not_output_seen",
              "n_failed_reconstructed", "fail_rate_reconstructed",
              "log_n_input", "log_n_written", "log_n_dup_plus_force", "log_n_failed", "matches_log"]
    lines = [",".join(header)]
    failed_lines = []
    mismatches = 0
    checked = 0

    sids = [f"{args.prefix}_shard_{n:05d}" for n in range(args.start, args.end + 1)]
    if args.order_from_global_seen:
        if not args.global_seen:
            sys.exit("--order-from-global-seen needs --global-seen")
        shard_hashes = {}
        for sid in sids:
            op = os.path.join(args.annotated_dir, f"{sid}_annotated.tsv")
            if os.path.exists(op):
                shard_hashes[sid] = {key_hash(f) for f in read_output_fens(op)}
        order = order_from_global_seen(load_global_seen_seq(args.global_seen), shard_hashes)
        missing = [s for s in sids if s in shard_hashes and s not in order]
        if missing:
            print(f"shards absent from global_seen.bin (written nothing?): {missing}", file=sys.stderr)
        numeric = [s for s in sids if s in order]
        print(f"processing order recovered from global_seen.bin; identical to numeric order: {order == numeric}")
        if order != numeric:
            print("first 12 in processing order: " + ", ".join(s.rsplit('_', 1)[1] for s in order[:12]))
        sids = order + missing

    for rank, sid in enumerate(sids):
        pos_path = os.path.join(args.shards_dir, f"{sid}_positions.txt")
        out_path = os.path.join(args.annotated_dir, f"{sid}_annotated.tsv")
        if not os.path.exists(pos_path) or not os.path.exists(out_path):
            print(f"{sid}: missing input or output, shard skipped (later shards' 'seen' set is then incomplete)",
                  file=sys.stderr)
            continue
        rows = read_positions(pos_path)
        input_keys.update(key_hash(r[0]) for r in rows)
        out_count = Counter(read_output_fens(out_path))
        n_output = sum(out_count.values())

        # rows sent to the engine are the "new" and "force" ones, in input order
        last_idx_by_game = {}
        for i, r in enumerate(rows):
            last_idx_by_game[r[2]] = i
        truncated_last = {i for g, i in last_idx_by_game.items() if rows[i][3] == "1"}

        remaining = Counter(out_count)
        n_not_output = n_not_seen_fail = n_not_output_seen = 0
        cand_idx = -1
        for i, r in enumerate(rows):
            h = key_hash(r[0])
            is_new = h not in seen
            if is_new or i in truncated_last:
                cand_idx += 1
            if remaining[r[0]] > 0 and is_new:
                remaining[r[0]] -= 1          # written
                continue
            n_not_output += 1
            if is_new:
                n_not_seen_fail += 1
                failed_lines.append(f"{sid}\t{i}\t{cand_idx}\t{r[0]}")
            else:
                n_not_output_seen += 1
        # rows written this shard update `seen` only after the shard, like the annotator
        written_hashes = [key_hash(f) for f in out_count.elements()]
        seen.update(written_hashes)

        t = truth.get(sid)
        if t:
            checked += 1
            ok = (t["n_input"] == len(rows) and t["n_written"] == n_output
                  and t["n_dup"] + t["n_force"] == n_not_output_seen and t["n_failed"] == n_not_seen_fail)
            mismatches += (not ok)
            tv = [t["n_input"], t["n_written"], t["n_dup"] + t["n_force"], t["n_failed"], int(ok)]
        else:
            tv = ["", "", "", "", ""]
        rate = n_not_seen_fail / len(rows) if rows else 0.0
        lines.append(",".join(str(x) for x in [sid, rank, len(rows), n_output, n_not_output, n_not_output_seen,
                                                 n_not_seen_fail, f"{rate:.6f}"] + tv))

    with open(args.csv_out, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    if args.failed_out:
        with open(args.failed_out, "w", newline="\n") as f:
            f.write("\n".join(failed_lines) + ("\n" if failed_lines else ""))

    # Independent of the processing order and of the "fails in one shard, succeeds in a
    # later one" limit: a position that was never annotated in ANY shard is a key present in
    # the inputs and absent from everything that was written. This is the count that matters
    # for holes in the dataset.
    lost = input_keys - seen
    print(f"distinct dedup keys in the inputs: {len(input_keys):,}; written: {len(seen):,}; "
          f"never annotated in any shard: {len(lost):,}")
    tot_fail = len(failed_lines)
    print(f"shards processed: {len(lines) - 1}; reconstructed failed positions: {tot_fail}")
    if truth:
        print(f"GATE against the original log: {checked} shards compared, {mismatches} mismatches")
    if args.global_seen:
        real = set(load_global_seen_seq(args.global_seen))
        print(f"global_seen.bin: {len(real):,} hashes; rebuilt from outputs: {len(seen):,}; "
              f"identical sets: {real == seen}")


if __name__ == "__main__":
    main()
