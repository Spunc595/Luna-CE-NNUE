"""Row-index cross-check: bullet's `ChessBucketsMirrored` input (the trainer side) vs Luna's `feature_index` (the engine
side), for the 4-king-bucket network. Compares the FINAL row index (bucket offset + piece-color-type block + squared,
mirror-flipped square) for every piece of every position in a test set, not bucket indices or mirror flips separately
(the intertwining is exactly how a layout mismatch can pass every quantisation gate silently — see PROTOCOLLO.md,
the `casa ^ 7` case, 1,999/2,000 positions differing with every gate green).

The bullet-side transcription (`bullet_map_features_v2`) is verified against the REAL bullet/bulletformat Rust code, not
trusted as a reimplementation: `bucket_probe.rs` (a bullet example using bulletformat's own `ChessBoard::FromStr` and the
real `ChessBucketsMirrored::map_features`) is run on the same FEN set and its output matches this Python function on
0/604 positions before this script is used to check anything against Luna (see `verify_against_real_bullet.py`).

Two conventions intertwine and either one alone is easy to get right while getting the other wrong:
  - bulletformat stores the WHOLE position side-to-move-relative: when Black is to move, every square is rank-flipped
    (^56) and every piece's colour bit is flipped, BEFORE any input-type code runs. `our_ksq()`/`opp_ksq()` are each
    piece's OWN king square in a frame where that side always looks like it is "White" (own_ksq = raw ^ 56 if stm is
    Black; opp_ksq = raw ^ 56 if stm is White) — this is NOT the same as the raw FEN square.
  - `ChessBucketsMirrored` then applies its OWN additional file-only mirror (flip=7 iff king's file > 3) on top of
    that, and indexes the bucket table directly by the (already side-to-move-normalised) king square.
  Luna's `perspective_flip` combines a file mirror (opposite direction: flip iff king's file > 3, same numeric test but
  applied to Luna's OWN white/black-accumulator king squares, not bulletformat's stm-normalised ones) with an explicit
  rank flip for the black perspective. The two together must agree on the FINAL row, which is what this file checks.

Bucket table (Luna's BUCKETS, `src/nnue.rs`, only the file 0-3 columns are ever read):
  king on a1/b1 (rank1, file a-b)      -> bucket 0
  king on c1/d1 (rank1, file c-d)      -> bucket 1
  king on rank2, file a-d              -> bucket 2
  king on rank3-8, file a-d            -> bucket 3
Expressed as bullet's ChessBucketsMirrored 32-entry table (rank-major, file a-d already folded):
  BUCKETS32 = [0,0,1,1, 2,2,2,2, 3,3,3,3, 3,3,3,3, 3,3,3,3, 3,3,3,3, 3,3,3,3, 3,3,3,3]

usage: python bucket_layout_check.py
"""
import random
import sys

import chess

HIDDEN = 1024
NUM_BUCKETS = 4
BUCKETS32 = [0, 0, 1, 1, 2, 2, 2, 2] + [3] * 24
assert len(BUCKETS32) == 32

FOLD = [0, 1, 2, 3, 3, 2, 1, 0]


def expand_buckets(buckets32):
    expanded = [0] * 64
    for idx in range(64):
        expanded[idx] = buckets32[(idx // 8) * 4 + FOLD[idx % 8]]
    return expanded


def bullet_num_buckets(buckets64):
    return max(buckets64) + 1


PT_ORDER = "pnbrqk"  # 0=pawn..5=king, matches both bulletformat's piece%6 order and Luna's own 0=Pawn..5=King


def bullet_map_features(fen, buckets64):
    """Transcription of bulletformat's FromStr (side-to-move normalisation) + Chess768::map_features +
    ChessBucketsMirrored::map_features, verified against the real Rust code (see module docstring). Returns
    {(white, pt, raw_sq): (row_stm, row_ntm)} keyed by the piece's identity in the RAW (un-normalised) FEN."""
    board_field, stm = fen.split()[0], fen.split()[1]
    pieces = []
    for r, row in enumerate(board_field.split("/")):
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
                continue
            sq = (7 - r) * 8 + f
            pieces.append((ch.isupper(), PT_ORDER.index(ch.lower()), sq))
            f += 1
    own_king_raw = [s for w, pt, s in pieces if pt == 5 and w == (stm == "w")][0]
    opp_king_raw = [s for w, pt, s in pieces if pt == 5 and w != (stm == "w")][0]
    own_ksq = own_king_raw ^ (56 if stm == "b" else 0)   # bulletformat's our_ksq()
    opp_ksq = opp_king_raw ^ (56 if stm == "w" else 0)   # bulletformat's opp_ksq()

    def flip_and_bucket(ksq):
        flip = 7 if (ksq % 8) > 3 else 0
        return flip, 768 * buckets64[ksq]

    stm_flip, stm_bucket = flip_and_bucket(own_ksq)
    ntm_flip, ntm_bucket = flip_and_bucket(opp_ksq)

    out = {}
    for white, pt, raw_sq in pieces:
        is_own = white == (stm == "w")
        sq_n = raw_sq ^ (56 if stm == "b" else 0)        # bulletformat's own stm-relative square normalisation
        c = 0 if is_own else 1
        pc = 64 * pt
        base_stm = (0 if c == 0 else 384) + pc + sq_n
        base_ntm = (384 if c == 0 else 0) + pc + (sq_n ^ 56)
        out[(white, pt, raw_sq)] = (stm_bucket + (base_stm ^ stm_flip), ntm_bucket + (base_ntm ^ ntm_flip))
    return out


# --- Luna side: transcription of nnue.rs (feature_index, get_bucket, perspective_flip) ---
LUNA_BUCKETS = (
    [0, 0, 1, 1, 5, 5, 4, 4] + [2, 2, 2, 2, 6, 6, 6, 6] + [3, 3, 3, 3, 7, 7, 7, 7] + [3, 3, 3, 3, 7, 7, 7, 7] * 5
)[:64]


def luna_perspective_flip(perspective_black, own_ksq):
    file_flip = 7 if (own_ksq % 8) > 3 else 0
    rank_flip = 56 if perspective_black else 0
    return file_flip ^ rank_flip


def luna_get_bucket(perspective_black, own_ksq):
    return LUNA_BUCKETS[(own_ksq ^ luna_perspective_flip(perspective_black, own_ksq)) & 63]


def luna_feature_index(perspective_black, own_ksq, piece_white, pt, piece_sq):
    bucket = luna_get_bucket(perspective_black, own_ksq)
    is_own = piece_white != perspective_black
    base = 768 * bucket + (0 if is_own else 384) + 64 * pt
    return base + (piece_sq ^ luna_perspective_flip(perspective_black, own_ksq))


def luna_rows(fen):
    """Returns {(white, pt, raw_sq): row} for the white perspective and the black perspective, separately."""
    board_field = fen.split()[0]
    pieces = []
    for r, row in enumerate(board_field.split("/")):
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
                continue
            sq = (7 - r) * 8 + f
            pieces.append((ch.isupper(), PT_ORDER.index(ch.lower()), sq))
            f += 1
    white_ksq = [s for w, pt, s in pieces if pt == 5 and w][0]
    black_ksq = [s for w, pt, s in pieces if pt == 5 and not w][0]
    w = {(w_, pt, sq): luna_feature_index(False, white_ksq, w_, pt, sq) for w_, pt, sq in pieces}
    b = {(w_, pt, sq): luna_feature_index(True, black_ksq, w_, pt, sq) for w_, pt, sq in pieces}
    return w, b


def compare(fens, buckets32, verbose_first=0):
    b64 = expand_buckets(buckets32)
    total = mismatches = 0
    shown = 0
    for fen in fens:
        bmap = bullet_map_features(fen, b64)
        w_by_pid, b_by_pid = luna_rows(fen)
        side_white = fen.split()[1] == "w"
        luna_stm = w_by_pid if side_white else b_by_pid
        luna_ntm = b_by_pid if side_white else w_by_pid
        for pid, (row_stm, row_ntm) in bmap.items():
            total += 2
            if luna_stm.get(pid) != row_stm:
                mismatches += 1
                if shown < verbose_first:
                    print(f"STM MISMATCH fen={fen} piece={pid} bullet={row_stm} luna={luna_stm.get(pid)}")
                    shown += 1
            if luna_ntm.get(pid) != row_ntm:
                mismatches += 1
                if shown < verbose_first:
                    print(f"NTM MISMATCH fen={fen} piece={pid} bullet={row_ntm} luna={luna_ntm.get(pid)}")
                    shown += 1
    return total, mismatches


def positions(n, seed):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        b = chess.Board()
        for _ in range(rng.randint(2, 60)):
            m = list(b.legal_moves)
            if not m:
                break
            b.push(rng.choice(m))
        if b.is_check():
            continue
        out.append(b.fen())
    return out


def castled_positions():
    return [
        "r4rk1/pppq1ppp/2n1bn2/2bpp3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 1",
        "2kr3r/ppp2ppp/2n1bn2/2bpp3/2B1P3/2NP1N2/PPP2PPP/2KR3R w - - 0 1",
        "r4rk1/ppp2ppp/2n1bn2/2bpp3/2B1P3/2NP1N2/PPP2PPP/2KR3R w - - 0 1",
        "2kr3r/ppp2ppp/2n1bn2/2bpp3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 1",
    ]


def main():
    fens = positions(600, seed=42) + castled_positions()

    total, mismatches = compare(fens, BUCKETS32, verbose_first=8)
    print(f"CORRECT layout: {total} feature rows checked, {mismatches} mismatches")
    if mismatches:
        sys.exit(1)

    mutated = list(BUCKETS32)
    mutated[0], mutated[8] = mutated[8], mutated[0]
    total_m, mismatches_m = compare(fens, mutated)
    print(f"MUTATED layout (idx0<->idx8 swapped): {total_m} checked, {mismatches_m} mismatches "
          f"({'PASS: comparator screams' if mismatches_m > 0 else 'FAIL: comparator is blind, this gate is broken'})")
    if mismatches_m == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
