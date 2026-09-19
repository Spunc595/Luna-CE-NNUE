"""
Score-relative -> absolute-result conversion, kept in a single place because
it is the class of bug that poisons a dataset without any metric noticing (a
sign inversion still produces a well-formed file, with plausible uniqueness
percentages and counts).

Convention: eval_cp is from the point of view of the side TO MOVE in the given
fen (python-chess PovScore.pov(board.turn), the same convention used by
annotate_positions.py). It is NOT the point of view of whoever just moved.
"""
import chess

WIDE_BAND_CP = 200  # above: result decided for whoever is ahead; below: draw


def decisive_result_from_eval(fen: str, eval_cp: int, wide_band_cp: int = WIDE_BAND_CP) -> str:
    """Returns '1-0' / '0-1' / '1/2-1/2' given the eval (side-to-move POV)
    of a position. Precision matters little here by construction (see
    resolve_truncated_wdl.py): it only has to tell "clearly decided" from
    "draw", not to judge ambiguous positions."""
    if abs(eval_cp) <= wide_band_cp:
        return "1/2-1/2"
    side_to_move_is_white = chess.Board(fen).turn == chess.WHITE
    white_ahead = (eval_cp > 0) == side_to_move_is_white
    return "1-0" if white_ahead else "0-1"
