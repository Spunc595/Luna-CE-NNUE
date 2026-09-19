"""
Reads the 5-column TSV format produced by annotate_incremental.py (fen,
eval_cp, bestmove, wdl_mover, depth — both eval_cp and wdl_mover already
from the side-to-move's point of view) and produces HalfKA training
examples: active feature indices for both perspectives, plus a target in
PROBABILITY SPACE [0,1] that blends the Stockfish eval with the game
result.

Relative to the previous version (resolve_truncated_wdl.py's 6-column
format, with an absolute white-side "result"), the board no longer needs
opening here to determine the side to move for the label:
annotate_incremental.py already did that conversion once, upstream.
board.fen() is still needed for active_features() AND to reorder the
indices into "mover/opponent" (see below) — not just for feature
indexing.

BUG FIXED 2026-09-08: active_features() returns
(white_indices, black_indices) — indices from White's and Black's
perspective, not "the mover's". model.py expects (us_idx, them_idx) with
"us" = the side TO MOVE (output_weights[0] pairs with the side to move,
matching evaluate_from_accumulator in nnue.rs), while the target here is
already relative to the side to move. train.py called the model always
passing white_idx as "us" — correct when it's White's turn, inverted
when it's Black's. On half the positions the model received the indices
as if evaluating from the wrong perspective relative to the target:
contradictory gradient on the same weights shared by half the data, the
model collapsed to a constant (val loss worse than the target variance
alone). Fix: reorder here, once, so train.py always receives
(us_idx, them_idx) already aligned with the target.

The target stays in [0,1] until the loss (train.py applies the same K
sigmoid to the model's prediction, which keeps producing centipawns in
forward() — see model.py).
"""
import math

import chess
import torch
from torch.utils.data import IterableDataset

from feature_set import active_features

# Clamp on the eval used to BUILD THE TARGET (not on the on-disk data,
# which stays as annotated): 0.61% of positions have mate scores around
# +-15,000, which sigmoid(K*eval) squashes to 0/1 anyway but with no
# benefit to training.
TARGET_EVAL_CLAMP_CP = 2000

# Natural-base sigmoid equivalent to 1/(1+10^(-cp/400)) (standard Elo-style
# convention): K = ln(10)/400. The same K must be used in train.py to
# transform the model's output (in cp) into the same [0,1] scale before
# the loss — if the two K's diverge the loss compares two different spaces.
K = math.log(10) / 400.0


def _read_rows(paths):
    for path in paths:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) != 5:
                    continue
                yield parts


class HalfKADataset(IterableDataset):
    def __init__(self, tsv_paths, eval_lambda: float = 0.7):
        # Accepts a single path or a list, so train.py can pass multiple
        # shards without having to concatenate them on disk.
        self.tsv_paths = [tsv_paths] if isinstance(tsv_paths, str) else list(tsv_paths)
        self.eval_lambda = eval_lambda

    def __iter__(self):
        # An IterableDataset is copied into EVERY DataLoader worker, and each
        # copy would iterate the whole file list: with num_workers > 0 every
        # position would be seen num_workers times per epoch (and batches
        # would repeat data), with no error. train.py uses num_workers=0; this
        # makes any other value fail loudly instead of silently duplicating
        # the data. Sharding by worker id would be the way to lift the limit.
        if torch.utils.data.get_worker_info() is not None:
            raise RuntimeError(
                "HalfKADataset does not shard across DataLoader workers: "
                "use num_workers=0 (each worker would iterate the whole dataset)")
        for fen, eval_cp_str, bestmove, wdl_mover_str, depth in _read_rows(self.tsv_paths):
            eval_cp = max(-TARGET_EVAL_CLAMP_CP, min(TARGET_EVAL_CLAMP_CP, float(eval_cp_str)))
            eval_wdl_mover = 1.0 / (1.0 + math.exp(-K * eval_cp))
            wdl_mover = float(wdl_mover_str)

            # Blend in probability space, side-to-move's point of view —
            # stays [0,1], no return to centipawns here.
            target = self.eval_lambda * eval_wdl_mover + (1.0 - self.eval_lambda) * wdl_mover

            board = chess.Board(fen)
            white_idx, black_idx = active_features(board)
            # us/them, not fixed white/black: the target above is already
            # relative to the side to move, so the indices must be the
            # same way, row by row.
            if board.turn == chess.WHITE:
                us_idx, them_idx = white_idx, black_idx
            else:
                us_idx, them_idx = black_idx, white_idx
            yield us_idx, them_idx, target


def collate_fn(batch):
    """Packs a list of (us_idx, them_idx, target) into the indices+offsets
    format that nn.EmbeddingBag expects. "us"/"them" = side to
    move/opponent, not fixed white/black — see HalfKADataset.__iter__."""
    us_all, us_offsets = [], [0]
    them_all, them_offsets = [], [0]
    targets = []

    for us_idx, them_idx, target in batch:
        us_all.extend(us_idx)
        us_offsets.append(us_offsets[-1] + len(us_idx))
        them_all.extend(them_idx)
        them_offsets.append(them_offsets[-1] + len(them_idx))
        targets.append(target)

    return (
        torch.tensor(us_all, dtype=torch.long),
        torch.tensor(us_offsets[:-1], dtype=torch.long),
        torch.tensor(them_all, dtype=torch.long),
        torch.tensor(them_offsets[:-1], dtype=torch.long),
        torch.tensor(targets, dtype=torch.float32),
    )
