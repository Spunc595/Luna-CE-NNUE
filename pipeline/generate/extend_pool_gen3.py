"""
Safely extends the normal_openings.epd pool WITHOUT invalidating the
already-consumed state (data/normal_openings.epd.offset + .shuffled),
used by the 5 control shards already generated. Does NOT reshuffle the
existing pool: that would break the "without replacement" guarantee (a
position already assigned at offset [0, cursor) could reappear in
[cursor, end) under a new permutation). Only appends the NEW lines at
the end, to both the raw file and the .shuffled file (shuffled among
themselves with a seed never used before), leaving the offset and the
first N lines of .shuffled unchanged.

Usage:
  python3 extend_pool_gen2.py --base data/normal_openings.epd \
      --extension data/normal_openings_200k.epd data/normal_openings_topup20k.epd \
      --shuffle-seed 101
"""
import argparse
import os
import random


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--extension", nargs="+", required=True)
    ap.add_argument("--shuffle-seed", type=int, required=True)
    args = ap.parse_args()

    base_lines = read_lines(args.base)
    base_set = set(base_lines)
    shuffled_path = args.base + ".shuffled"
    offset_path = args.base + ".offset"

    if not os.path.exists(shuffled_path):
        raise SystemExit(f"[ERROR] {shuffled_path} does not exist: nothing has been consumed yet, "
                          f"this script is not needed — just regenerate the pool from scratch.")
    shuffled_lines = read_lines(shuffled_path)
    if len(shuffled_lines) != len(base_lines):
        raise SystemExit(f"[FATAL ERROR] {shuffled_path} ({len(shuffled_lines)} rows) does not match "
                          f"{args.base} ({len(base_lines)} rows) — inconsistent state, stopping everything.")

    seen = set(base_set)
    delta = []
    dup_within_base_extension = 0
    for ext_path in args.extension:
        for line in read_lines(ext_path):
            if line in seen:
                dup_within_base_extension += 1
                continue
            seen.add(line)
            delta.append(line)

    if not delta:
        raise SystemExit("[ERROR] no new row found in the extensions provided — check the inputs.")

    rng = random.Random(args.shuffle_seed)
    delta_shuffled = list(delta)
    rng.shuffle(delta_shuffled)

    offset_before = 0
    if os.path.exists(offset_path):
        with open(offset_path, "r") as f:
            offset_before = int(f.read().strip() or "0")

    with open(args.base, "a", encoding="utf-8") as f:
        for line in delta:
            f.write(line + "\n")
    with open(shuffled_path, "a", encoding="utf-8") as f:
        for line in delta_shuffled:
            f.write(line + "\n")

    new_total = len(base_lines) + len(delta)
    print(f"[DONE] base before: {len(base_lines)} rows, delta added: {len(delta)} rows "
          f"({dup_within_base_extension} duplicates already present discarded), new total: {new_total}")
    print(f"offset unchanged: {offset_before} (still valid, points inside the untouched part)")
    print(f"NEW_TOTAL={new_total}")


if __name__ == "__main__":
    main()
