"""Verifies bucket_layout_check.py's `bullet_map_features` against the REAL bullet Rust code (bucket_probe.rs, run
through bulletformat's own FEN parser and the real ChessBucketsMirrored::map_features), not a second reimplementation
trusting the first. Compares the multiset of (row_stm, row_ntm) pairs per position (order-independent: bulletformat's
piece iteration order is its own internal bitboard scan order, not the FEN reading order this script uses).

usage:
  1. build the probe once: in the bullet fork, add to crates/bullet_lib/Cargo.toml:
       [[example]]
       name = "bucket_probe"
       path = "../../examples/bucket_probe.rs"
     then: cargo build -r --example bucket_probe --features cpu --no-default-features
  2. python verify_against_real_bullet.py FENS_FILE PROBE_BINARY
"""
import re
import subprocess
import sys

import bucket_layout_check as blc


def main():
    fens_path, probe_bin = sys.argv[1], sys.argv[2]
    fens = [f for f in open(fens_path, encoding="utf-8").read().split("\n") if f.strip()]
    out = subprocess.run([probe_bin], input="\n".join(fens) + "\n", capture_output=True, text=True, timeout=60).stdout
    fen_re = re.compile(r"FEN (\d+) white=(\d) pt=(\d) sq=(\d+) stm_row=(\d+) ntm_row=(\d+)")
    real_pairs_by_idx = {}
    for line in out.splitlines():
        mo = fen_re.match(line)
        if mo:
            i = int(mo[1])
            real_pairs_by_idx.setdefault(i, []).append((int(mo[5]), int(mo[6])))

    b64 = blc.expand_buckets(blc.BUCKETS32)
    mismatches = 0
    for i, fen in enumerate(fens):
        mine = sorted(blc.bullet_map_features(fen, b64).values())
        real = sorted(real_pairs_by_idx.get(i, []))
        if mine != real:
            mismatches += 1
            if mismatches <= 5:
                print(f"MISMATCH fen={fen}\n  python: {mine}\n  rust:   {real}")
    print(f"{mismatches}/{len(fens)} FENs mismatched against the real bullet Rust output")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
