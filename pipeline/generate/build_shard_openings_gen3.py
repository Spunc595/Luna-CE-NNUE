"""
Builds the opening file for ONE shard of generation 2, with
CONSUMPTION WITHOUT REPLACEMENT (guarantees <=1x reuse by construction
instead of hoping for it): each pool is shuffled ONCE ONLY (fixed seed,
on the first call) and then consumed in sequence via a cursor persisted
to disk (data/*_offset.txt) — every opening position used at most once
across the whole run, regardless of how many shards consume it.

Usage (called once per shard, in order):
  python build_shard_openings_gen2.py --normal-pool data/normal_openings.epd \
      --endgame-pool data/endgame_positions.epd --count 5000 --endgame-frac 0.30 \
      --out shards/raw/gen2_shard_00001_openings.epd
"""
import argparse
import os
import random


def load_or_shuffle_pool(path, seed):
    """If <path>.shuffled doesn't exist yet, shuffles <path> once (fixed
    seed) and writes it as <path>.shuffled — every subsequent call (for
    each shard) reads the SAME shuffled order, guaranteeing the offset
    cursor stays consistent run after run."""
    shuffled_path = path + ".shuffled"
    if os.path.exists(shuffled_path):
        with open(shuffled_path, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    rng = random.Random(seed)
    rng.shuffle(lines)
    with open(shuffled_path, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")
    return lines


def consume(pool, offset_path, n):
    """Reads the current cursor, takes the next N lines, advances and
    persists the cursor. Fails loudly (not a silent wrap-around) if the
    pool runs out: it means it was sized too small for the planned
    number of games."""
    offset = 0
    if os.path.exists(offset_path):
        with open(offset_path, "r") as f:
            offset = int(f.read().strip() or "0")
    end = offset + n
    if end > len(pool):
        raise SystemExit(
            f"[FATAL ERROR] pool exhausted: {n} positions needed from offset {offset} "
            f"but the pool only has {len(pool)}. Size the pool larger before "
            f"continuing — no automatic wrap-around (it would bring back the reuse that "
            f"this script exists to avoid)."
        )
    slice_ = pool[offset:end]
    with open(offset_path, "w") as f:
        f.write(str(end))
    return slice_


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--normal-pool", required=True)
    ap.add_argument("--endgame-pool", required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--endgame-frac", type=float, default=0.30)
    ap.add_argument("--shuffle-seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    normal_pool = load_or_shuffle_pool(args.normal_pool, args.shuffle_seed)
    endgame_pool = load_or_shuffle_pool(args.endgame_pool, args.shuffle_seed + 1)

    n_endgame = round(args.count * args.endgame_frac)
    n_normal = args.count - n_endgame

    normal_offset_path = args.normal_pool + ".offset"
    endgame_offset_path = args.endgame_pool + ".offset"

    chosen_normal = consume(normal_pool, normal_offset_path, n_normal)
    chosen_endgame = consume(endgame_pool, endgame_offset_path, n_endgame)

    combined = chosen_endgame + chosen_normal
    # Shuffle ONLY the order within this shard's file (which game uses it
    # first), doesn't re-shuffle the source pools: the position->shard
    # assignment stays the cursor's, deterministic and without
    # replacement.
    random.Random(args.shuffle_seed + 1000).shuffle(combined)

    with open(args.out, "w") as f:
        for line in combined:
            f.write(line + "\n")

    print(f"[DONE] {args.out}: {len(combined)} openings ({len(chosen_endgame)} endgame, {len(chosen_normal)} normal, without replacement)")
    print(f"ENDGAME_LINES={len(chosen_endgame)}")


if __name__ == "__main__":
    main()
