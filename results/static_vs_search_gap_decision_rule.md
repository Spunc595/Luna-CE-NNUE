# Static-vs-search gap diagnostic — decision rule (registered before any measurement)

Written and committed BEFORE the diagnostic was run; the commit timestamp is
the proof of ordering. Nothing below was edited after seeing numbers.

## Question

Is the capture-move class (`bestmove` is a capture) where the static
evaluation disagrees with a 20,000-node search disproportionately, i.e. is
filtering or down-weighting capture positions in the training data justified?

## Metric

Primary: `|sigmoid(K * search) - sigmoid(K * static)|`, with `K = ln(10)/400`
(the value defined in `pipeline/train/dataset.py`, line 53). Secondary, for
readability only: the same difference in centipawns. Spearman(static, search)
is computed within each class on raw values.

Both `static` (UCI `eval`) and `search` (`go nodes 20000`, 1 thread) are from
the same engine process with the same network, side-to-move perspective.

## Decision rule

The capture-filter hypothesis is **supported** only if BOTH hold:

- (a) median sigmoid-space gap of the capture class >= 1.5 x that of the
  quiet class;
- (b) Spearman(static, search) of the capture class is at least 0.05 LOWER
  than that of the quiet class.

Regardless of (a) and (b), the following is always reported and is the
deciding number:

- (c) the capture class's share of total squared sigmoid-space error compared
  with its share of positions. Operationalization fixed here in advance:
  ratio = (share of error) / (share of positions). If ratio < 1.5 the filter
  **cannot help** by construction, whatever (a) and (b) say; a supported
  hypothesis is only ACTIONABLE if (a), (b) and ratio >= 1.5 all hold.

If the rule is not satisfied: do NOT implement the filter; the plateau is
elsewhere and has to be looked for, not guessed.

Alternative hypothesis, measured in the same run at no extra cost: the gap
concentrates by piece count rather than by move type (which would point to
re-weighting by game phase instead of a capture filter). Reported with the
same statistics per piece-count bucket (<=8, 9-12, 13-20, 21-32) and crossed
with move class; any cell with n < 100 is flagged under-powered and no
conclusion is drawn from it.

## Conventions fixed in advance

- Class is decided by LUNA's own bestmove from the 20k-node search, not by
  the Stockfish column of the file (which is not used at all here).
- A promotion with capture is classified as **promotion** (the more specific
  and rarer class); en passant counts as a capture.
- Positions where the search reports a mate score are discarded (they are
  distances, not evaluations) and counted.
- `NNUE_EVAL_CLAMP = 15000`: positions where either value reaches it are
  counted separately and kept in the main tables; the decision statistics are
  additionally recomputed without them as a sensitivity check.
- Control: the identical run with the gen2 network. A profile that changes a
  lot between gen2 and gen3 is a property of that particular fit, and the
  rule must be reconsidered before acting on it.
