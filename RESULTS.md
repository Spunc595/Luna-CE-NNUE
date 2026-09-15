# Results

Every number in this document was **recomputed from the `.csv` files in
`results/`** at the time of writing (2026-09-15), not copied from
RUNBOOK.md — see 5.2 for the constraint and the two real discrepancies
found while recomputing.

## 1. Networks compared — static measurement

Static evaluation (UCI `eval` command, **no search**), same set of 2,000
positions (`results/eval_set.epd`, sampled with seed=7 from a shared
reference validation set, details in 5.3), Stockfish depth 8 as the
reference.

| Network | ρ vs Stockfish |
|---|---|
| gen1 | 0.5874 |
| gen2 | 0.6790 |
| gen0 *(non-compliant — see `non_conforme/README.md`)* | 0.7850 |
| akimbo *(third-party network, MIT, reference only — never used to generate data)* | 0.8522 |

Script: `results/scripts/measure_static_vs_stockfish.py`. CSV:
`results/gen1_vs_stockfish.csv`, `gen2_vs_stockfish.csv`,
`akimbo_vs_stockfish.csv`. Engine commit
`076defcb93d4a1dc834d4ecd5132f45ba9a311d2` (gen1, gen2); akimbo: separate
reference build (v3.1.2, embedded akimbo network, no external network
loaded). Date: 2026-09-15. No search involved: static evaluation uses no
threads, deterministic by construction.

## 2. The engine in search, per generation

**Not the same quantity as table 1** — this measures how the engine
actually plays (fixed-node search), not the isolated network. **1
thread** (UCI default, never overridden in any measurement script in this
repository — reproducible exactly). Same set of 2,000 positions from
`results/eval_set.epd`.

| nodes | Luna + gen1 | Luna + gen2 | step |
|---|---|---|---|
| 10,000 | 0.8072 | 0.8536 | +0.0464 |
| 20,000 | 0.8249 | 0.8758 | +0.0509 |
| 50,000 | 0.8428 | 0.8891 | +0.0463 |

**The step is quite stable across the three node levels** (+0.0464 /
+0.0509 / +0.0463) — "constant" would be a stronger claim than these
three numbers support, but it doesn't swing wildly either. The numbers
are here, without a claim broader than what they hold up.

Script: `results/scripts/measure_search_vs_stockfish.py`. CSV:
`results/gen1_master_vs_stockfish.csv`, `results/gen2_master_vs_stockfish.csv`.
Date: 2026-09-15.

**Note on the gen1 discrepancy, corrected**: an earlier version of this
table reported the RUNBOOK/gen2.md values for gen1 (0.8072 / 0.8285 /
0.8413) while the surrounding text already claimed the table was
recomputed from the CSVs — the table itself wasn't, contradicting its own
note. **The table above now uses the recomputed values** (0.8072 / 0.8249
/ 0.8428): at 10,000 nodes it matches RUNBOOK, at 20,000 and 50,000 it
doesn't (a real gap, not rounding noise). gen2 recomputes within 0.0004 in
all three cases. Unverified hypothesis for why: the original RUNBOOK
measurement for gen1 may straddle the `076defc` fix (a real quiescence
timeout bug, which affects longer searches more — consistent with 10k,
the shortest search, matching exactly while 20k/50k don't). Neither value
was chosen as "the right one": the table above uses the value recomputed
now, under the same engine commit for both generations (so comparable
between them even though it differs from the historical figure). TODO:
verify the exact commit used for the original gen1 measurement, if
recoverable from logs.

## 3. How well each network learned from its own master

**A different quantity from the first two — not comparable to them.**
Measures how faithfully the network reproduces its own master (classical
PST for gen1, the gen1 network in search for gen2): it says nothing about
how close the network is to the truth (that's what tables 1-2 say).

| Generation | ρ vs own master |
|---|---|
| gen1 | 0.9230 |
| gen2 | 0.9508 |

## 4. The datasets

| Generation | Total positions | Unique | Uniqueness rate | Games | Yield (pos/game) | Self-play nodes | Annotation nodes | Master network | Machine | Commit |
|---|---|---|---|---|---|---|---|---|---|---|
| gen1 | 3,300,643 | 2,135,009 | 64.7% | 230,000 | 14.3506 | 3,000 | 10,000 | classical (PST) | Oracle (self-play), PC (annotation) | self-play `b0cfb937` / annotation `076defc` |
| gen2 | 3,083,063 | 2,972,944 | 96.4% | 265,000 | 11.6342 | 3,000 | 20,000 | gen1 (search) | Oracle (self-play and, after reconciliation, annotation) | `076defc` (both) |
| gen3 | *in progress* | *in progress* | *in progress* | *in progress* | 11.88 *(only 5 control shards out of 54, not the full generation)* | 3,000 | 20,000 | gen2 (search) | Oracle (entire generation) | `076defc` (both) |

**Yield denominator, declared for all three**: raw extracted positions /
**completed games**. Explicitly verified for all three generations that
completed games = assigned games (100% in each, no failed/lost games) —
the denominator isn't ambiguous here, but it must be re-checked for every
future generation, not assumed.

**Note on gen1**: the "14.2 pos/game" figure that circulated earlier
(RUNBOOK, conversations) came from a **preliminary 3-shard trial**
(2,400 games), not the full generation. The correct number for all of
gen1 (46 shards, 230,000 games) is **14.3506** — the difference is small
but the wrong number shouldn't propagate: it's the one a future
generation's pools would be sized against if gen1 were reused as a
reference.

## 5. Training

| Generation | Minimum val loss | Epoch | Epochs used | Target variance (preflight) | Material-only MSE (preflight) | Untrained MSE (preflight) |
|---|---|---|---|---|---|---|
| gen1 | 0.013316 | — | 12 (plateau never reached, not worth redoing for this) | — | — | — |
| gen2 | 0.018874 | 4 | 10 (early stop, patience 6) | 0.134622 | 0.030026 | 0.135515 |

**Val loss is not comparable across generations: the scales differ**
(different dataset, different target). Look at ratios (fraction of
variance explained, distance from material), not the absolute value.

gen1's three preflight numbers weren't recovered in this session (TODO:
pull them from `gen1_train.log` on request, not urgent).

## 5.5 Overlap check

`results/eval_set.epd` (the 2,000 positions used in every table above) is
a sample of a validation set (`val_final.tsv`, 274,226 positions) held out
of training since its creation (gen0). **Checked in full, not sampled**
(literal FEN comparison, cheap even over millions of rows, no heavy CPU):

| Training dataset | Rows checked | Overlaps found |
|---|---|---|
| gen1 (`gen1_train.tsv`) | 2,080,991 | 0 |
| gen2 (`gen2_train.tsv`) | 2,899,216 | 0 |
| gen3 | *in progress, to check once the generation completes* | TODO |

Zero overlaps confirmed for gen1 and gen2: the Spearman measurements
aren't rewarding memorization.

## 5.6 What was not measured

- **Measured directly**: rank correlation (Spearman), both static
  (table 1) and in fixed-node search (table 2).
- **Inferred, not measured**: that a higher rank correlation corresponds
  to more playing strength (Elo). A reasonable assumption (the one direct
  SPRT available, gen0 vs akimbo, shows the network with lower Spearman
  losing decisively — consistent, but it's a single data point), not a
  measurement.
- **Not measured at all**: gen1 or gen2's Elo. No SPRT was run in either
  cycle (by explicit instruction — the comparison is between generations
  via Spearman, not generation vs. baseline via Elo).

## 5.7 The two gen3 predictions (registered 2026-09-15, before the result)

1. **Static trend** (from `gen3.md`): 0.5874 → 0.6790 is +0.0916; with
   shrinking steps, expected **0.73-0.76**.
2. **Student/master ratio**: gen2 delivered 0.6790/0.8285 = **0.8196** of
   its own master (in search at 20k nodes, original RUNBOOK value — see
   the table 2 discrepancy note if recomputing with 0.8249 instead); with
   a gen3 master at 0.8760, gen3 would land at **~0.718**.

Do not revise the first prediction after seeing partial results: both are
registered now, and whichever wins gets noted once gen3 closes.

## 5.8 Generation 3's confound

The gen3 normal-opening pool was **regenerated from scratch** with the
gen2 network's filter (gen2 had used the gen1 network's filter, not
reused). **The gen2→gen3 step in ρ vs Stockfish will therefore be
attributable to network AND opening distribution together, not to the
master's improvement alone.** This is not a mistake and it's too late to
undo — but whoever reads the number in six months needs to see this here,
not only in the introductory text: when the gen3 row is added to table 1,
this note must be repeated in the cell or row itself.

## 5.9 The gen2 prediction that missed — and why

`gen2.md`'s pre-registered expectation for gen2 was **0.76-0.78**. The
actual result was **0.6790** — a large miss, and that wrong number is
sitting inside all 99 committed manifests, so a reader will find it
regardless of whether this section exists.

**Why it missed**: the expectation was built by multiplying the master's
*search* ρ (gen1 network in search, 0.8072-0.8413 depending on nodes) by
the net-to-master ρ seen in gen1 (0.9230). That product is not a valid
transfer coefficient — it mixes a search-based quantity with a
static-network-vs-master quantity, exactly the kind of comparison this
whole project has repeatedly gotten burned by (see the "compare only
homogeneous quantities" rule adopted from `gen3.md` onward, and the
distinction kept strict throughout this document between tables 1-2 and
table 3).

**A pre-registration that never admits missing the round before is
decorative.** Admitting it is what makes gen3's pre-registration (5.7)
worth trusting.

---

## Quick file reference

- `eval_set.epd` — 2,000 positions (fen, Stockfish depth-8 eval, bestmove,
  wdl, depth), deterministically sampled (seed=7) from a 274,226-position
  reference validation set never used in any training.
- `*_vs_stockfish.csv` — raw per-position evaluations, one per
  engine/measurement, produced by the scripts in `results/scripts/`.
- `results/scripts/` — code that produces the CSVs above and computes
  Spearman. See `COMPLIANCE.md` for why "stockfish" appearing here isn't
  a violation.
