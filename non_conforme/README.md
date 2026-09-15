# gen0 — non-compliant, kept as a reference

A network trained on ~11M positions from self-play with the akimbo
network (embedded, third-party, MIT license) as evaluator, **Stockfish
labels**. Does not meet the TCEC guideline applied from gen1 onward (all
data must come from the engine's own search/evaluation).

**Why it exists**: it predates explicit knowledge of this rule within the
project. At the time it was generated, the decision to restart from a
fully self-produced bootstrap hadn't been made yet (that decision is what
opened generation 1).

**Why it's kept**: as an external comparison reference (see table 1 in
`RESULTS.md` — gen0 scores ρ 0.7850 against Stockfish, higher than gen1
and gen2, and it's honest to show that). **It is not an ancestor of any
presented network** — no gen0 position, label, or weight entered the data
or initial weights of gen1, gen2, or later generations. gen1 started from
scratch.

**Outcome**: lost an SPRT against akimbo decisively (-339.8 ± 94.8 Elo,
LOS 0.0%, H0 accepted over 113 games). No longer used, not deleted.

## The annotation scripts with an external source

Three scripts in this folder call Stockfish as a **label source** (not as
an offline measurement tool — see the distinction in `COMPLIANCE.md`):
`annotate_positions.py`, `annotate_incremental_gen0.py`, and
`_annotate_chunk_worker_gen0.py` — all three belong to gen0, moved here
from `pipeline/annotate/` (where they used to sit alongside the compliant
scripts) specifically to make `pipeline/annotate/` clean **by
construction**: anyone reading only that folder finds no Stockfish call,
without having to check file by file. They're isolated here not to mark
one special file, but because the entire gen0 category doesn't belong to
the compliant pipeline: these aren't errors to fix, they're historical
artifacts not to be reused.
