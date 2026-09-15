"""
HalfKA feature indexing for Luna's NNUE, ported 1:1 from src/nnue.rs
(feature_index / get_base_index / get_bucket / perspective_flip).

Architecture: (768 inputs x 4 king buckets, horizontally mirrored) x 2
perspectives. Piece type order 0=Pawn,1=Knight,2=Bishop,3=Rook,4=Queen,
5=King (King IS a tracked feature, unlike classic HalfKP).

Any change here must be mirrored in src/nnue.rs's Rust functions of the
same name, or the exported network will silently misalign against what
the engine actually computes at inference time.
"""
import chess

NUM_BUCKETS = 4
HIDDEN = 1024

# Copied verbatim from nnue.rs's BUCKETS table (indexed by oriented king
# square; only file 0..=3 entries are ever reached).
BUCKETS = [
    0, 0, 1, 1, 5, 5, 4, 4,
    2, 2, 2, 2, 6, 6, 6, 6,
    3, 3, 3, 3, 7, 7, 7, 7,
    3, 3, 3, 3, 7, 7, 7, 7,
    3, 3, 3, 3, 7, 7, 7, 7,
    3, 3, 3, 3, 7, 7, 7, 7,
    3, 3, 3, 3, 7, 7, 7, 7,
    3, 3, 3, 3, 7, 7, 7, 7,
]

# python-chess piece types are 1-indexed (PAWN=1..KING=6); Luna uses 0..5.
PIECE_TYPE_TO_LUNA = {
    chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2,
    chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5,
}


def perspective_flip(perspective_black: bool, own_ksq: int) -> int:
    file_flip = 7 if (own_ksq % 8) > 3 else 0
    rank_flip = 56 if perspective_black else 0
    return file_flip ^ rank_flip


def get_bucket(perspective_black: bool, own_ksq: int) -> int:
    return BUCKETS[own_ksq ^ perspective_flip(perspective_black, own_ksq)]


def get_base_index(perspective_black: bool, piece_white: bool, pc: int, own_ksq: int) -> int:
    bucket = get_bucket(perspective_black, own_ksq)
    is_own_piece = piece_white != perspective_black
    return 768 * bucket + (0 if is_own_piece else 384) + 64 * pc


def feature_index(perspective_black: bool, own_ksq: int, piece_white: bool, pc: int, piece_sq: int) -> int:
    base = get_base_index(perspective_black, piece_white, pc, own_ksq)
    return base + (piece_sq ^ perspective_flip(perspective_black, own_ksq))


def active_features(board: chess.Board):
    """Returns (white_indices, black_indices): the active feature-table
    rows for the white-perspective and black-perspective accumulators,
    one index per piece currently on the board (including both kings)."""
    white_ksq = board.king(chess.WHITE)
    black_ksq = board.king(chess.BLACK)

    white_indices = []
    black_indices = []

    for sq, piece in board.piece_map().items():
        pc = PIECE_TYPE_TO_LUNA[piece.piece_type]
        piece_white = piece.color == chess.WHITE

        white_indices.append(feature_index(False, white_ksq, piece_white, pc, sq))
        black_indices.append(feature_index(True, black_ksq, piece_white, pc, sq))

    return white_indices, black_indices
