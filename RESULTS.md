# Results

Every number in this document was **recomputed from the `.csv` files in
`results/`** at the time of writing (2026-09-15/16), not copied from
earlier private working notes — see 5.2 for the constraint and the two
real discrepancies found while recomputing.

## 1. Networks compared — static measurement

Static evaluation (UCI `eval` command, **no search**), same set of 2,000
positions (`results/eval_set.epd`, sampled with seed=7 from a shared
reference validation set, details in 5.3), Stockfish depth 8 as the
reference.

| Network | ρ vs Stockfish |
|---|---|
| gen1 | 0.5874 |
| gen2 | 0.6790 |
| gen3 *(opening pool re-filtered with the gen2 network, not reused from gen2 — this step is attributable to network **and** opening distribution together, not the master alone; see 5.8)* | 0.7005 |
| gen0 *(non-compliant — see `non_conforme/README.md`)* | 0.7850 |
| akimbo *(third-party network, MIT, reference only — never used to generate data)* | 0.8522 |

Script: `results/scripts/measure_static_vs_stockfish.py`. CSV:
`results/gen1_vs_stockfish.csv`, `gen2_vs_stockfish.csv`,
`gen3_vs_stockfish.csv`, `gen0_vs_stockfish.csv`, `akimbo_vs_stockfish.csv`.
Engine commit `076defcb93d4a1dc834d4ecd5132f45ba9a311d2` (gen1, gen2, gen3,
gen0 — gen0's checkpoint was exported fresh under this commit's export.py,
2026-09-16, and recomputes to the exact historical 0.7850, confirming it
wasn't just copied forward); akimbo: separate
reference build (v3.1.2, embedded akimbo network, no external network
loaded). Date: 2026-09-15/16. No search involved: static evaluation uses no
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
table reported the values from earlier private working notes for gen1
(0.8072 / 0.8285 / 0.8413) while the surrounding text already claimed the
table was recomputed from the CSVs — the table itself wasn't,
contradicting its own note. **The table above now uses the recomputed
values** (0.8072 / 0.8249 / 0.8428): at 10,000 nodes it matches the
earlier figure, at 20,000 and 50,000 it doesn't (a real gap, not rounding
noise). gen2 recomputes within 0.0004 in all three cases. Unverified
hypothesis for why: the original measurement for gen1 may straddle the
`076defc` fix (a real quiescence
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
| gen3 | 0.9475 |

## 4. The datasets

| Generation | Total positions | Unique | Uniqueness rate | Games | Yield (pos/game) | Self-play nodes | Annotation nodes | Master network | Machine | Commit |
|---|---|---|---|---|---|---|---|---|---|---|
| gen1 | 3,300,643 | 2,135,009 | 64.7% | 230,000 | 14.3506 | 3,000 | 10,000 | classical (PST) | Oracle (self-play), PC (annotation) | self-play `b0cfb937` / annotation `076defc` |
| gen2 | 3,083,063 | 2,972,944 | 96.4% | 265,000 | 11.6342 | 3,000 | 20,000 | gen1 (search) | Oracle (self-play and, after reconciliation, annotation) | `076defc` (both) |
| gen3 | 3,210,755 | 3,112,004 | 96.9% | 270,000 | 11.8917 | 3,000 | 20,000 | gen2 (search) | Oracle (entire generation) | `076defc` (both) |

**Yield denominator, declared for all three**: raw extracted positions /
**completed games**. Explicitly verified for all three generations that
completed games = assigned games (100% in each, no failed/lost games) —
the denominator isn't ambiguous here, but it must be re-checked for every
future generation, not assumed.

Note on gen3's game count in the dataset: `gen3_dataset_composition.json`
reports 259,932 games among the deduplicated training rows, lower than
the 270,000 completed self-play games — some games contributed zero
surviving positions after dedup (all their extracted positions were
duplicates of positions from other games), so they don't appear once
`build_training_dataset_gen3.py` joins by game_id. Expected, not an error;
same structural behavior as gen1/gen2.

**Note on gen1**: the "14.2 pos/game" figure that circulated earlier
(private working notes and conversations) came from a **preliminary 3-shard trial**
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
| gen3 | 0.022381 | 3 | 9 (early stop, patience 6) | 0.128605 | 0.035448 | 0.130053 |

**Val loss is not comparable across generations: the scales differ**
(different dataset, different target). Look at ratios (fraction of
variance explained, distance from material), not the absolute value.
For gen3: val loss ends 82.6% below variance and 36.9% below the
material-only baseline — same qualitative shape as gen2, plateau reached
even earlier (epoch 3 vs. epoch 4), so more epochs would not have helped.

gen1's three preflight numbers weren't recovered in this session (TODO:
pull them from `gen1_train.log` on request, not urgent).

### 5.4a Export and structural checks (gen3)

- **Exported file size**: 6,297,664 bytes — exact match to the expected
  size (a free structural check: a wrong size means a broken export, and
  every downstream measurement would be meaningless).
- **Round-trip (PyTorch model output vs. engine's static eval)**, 20
  hand-picked + sampled positions: **max 37.07cp, avg 12.84cp**. Recomputed
  the identical check against gen2's already-shipped checkpoint for
  calibration: max 24.33cp, avg 11.22cp — same order of magnitude, same
  known quantization gap already documented for this project (dominated by
  output-layer rounding), not a new regression specific to gen3.
- **SIMD safety gate**: `max|output_weight| = 4` (limit 128, the point
  past which the 16-bit multiply in the SIMD dot product could overflow) —
  wide margin, zero clamped weights across all 9 training epochs.

## 5.5 Overlap check

`results/eval_set.epd` (the 2,000 positions used in every table above) is
a sample of a validation set (`val_final.tsv`, 274,226 positions) held out
of training since its creation (gen0). **Checked in full, not sampled**
(literal FEN comparison, cheap even over millions of rows, no heavy CPU):

| Training dataset | Rows checked | Overlaps found |
|---|---|---|
| gen1 (`gen1_train.tsv`) | 2,080,991 | 0 |
| gen2 (`gen2_train.tsv`) | 2,899,216 | 0 |
| gen3 (`gen3_train.tsv`) | 3,033,768 | 0 |

Zero overlaps confirmed for all three generations: the Spearman
measurements aren't rewarding memorization.

## 5.6 What is measured, and what still isn't

**Updated 2026-09-16 — the Spearman/Elo link moved from inferred to
measured.** This section originally put that link in the "inferred, not
measured" category; §6 (below) now reports a direct measurement, so the
categorization changes.

- **Measured directly**: rank correlation (Spearman), both static
  (table 1) and in fixed-node search (table 2). And, as of §6, **relative
  playing strength between three network configurations of the identical
  binary/search** (akimbo, gen0, gen3), via a 1,500-game round-robin —
  including two local Spearman-to-Elo slopes (327 and 698 Elo per 0.10 ρ,
  §6) rather than the single averaged figure an earlier draft reported.
- **Still inferred, not measured**: that this relative-Elo relationship,
  measured between three specific networks on one machine/binary/TC,
  generalizes to networks outside this range, to different search
  conditions, or to a different engine's Spearman/Elo curve entirely.
  Three points fix a direction and a visible curvature; they are not a
  validated general function.
- **Still not measured at all**: gen1, gen2, or gen3's **absolute** Elo —
  where any of them would land on a public rating list. §6's numbers are
  differences between configurations on an arbitrary internal scale, not
  anchored to CCRL or any other external reference (see §6's own opening
  note on why that anchoring wasn't attempted on Oracle's ARM hardware).
  No SPRT against an external baseline was run for gen1 or gen2 either.

## 5.7 The two gen3 predictions (registered 2026-09-15, before the result)

1. **Static trend** (from an earlier internal note): 0.5874 → 0.6790 is
   +0.0916; with shrinking steps, expected **0.73-0.76**.
2. **Student/master ratio**: gen2 delivered 0.6790/0.8285 = **0.8196** of
   its own master (in search at 20k nodes, original private-notes value — see
   the table 2 discrepancy note if recomputing with 0.8249 instead); with
   a gen3 master at 0.8760, gen3 would land at **~0.718**.

Do not revise the first prediction after seeing partial results: both are
registered now, and whichever wins gets noted once gen3 closes.

**Result (2026-09-16): ρ = 0.7005.** Both predictions overshot — neither
was hit — but the **student/master ratio estimator (~0.718) came closer**
(off by 0.0175) than the **static-trend estimator (0.73-0.76)** (off by at
least 0.0295 from its own lower bound). Recomputing estimator 2 with the
table-2-discrepancy-corrected gen2 ratio (0.6790/0.8249 = 0.8232, master
at 0.8760) gives ~0.7211 — still the closer estimator either way. Step
from gen2: 0.7005 − 0.6790 = **+0.0215**, positive (the cycle has not
stalled per the stop condition in `gen3.md`) but much smaller than the
gen1→gen2 step of +0.0916 — a real deceleration beyond what either
pre-registered estimator expected. The ratio estimator came closer, but
**not because the transfer ratio is actually stable** — see 5.10, it
isn't. Both estimators overshot for a related reason: the trend estimator
assumed the *step* stays roughly constant, the ratio estimator assumed
the *ratio* stays roughly constant, and neither quantity did. The ratio
estimator merely decayed more slowly than the trend one did over this
single step — not evidence its mechanism is sound, just evidence it's
less wrong so far.

## 5.10 The transfer ratio is declining, not constant

The reason both 5.7 predictions overshot: the fraction of the master's
score that the student actually captures is **falling**, not holding
steady as estimator 2 assumed.

| Generation | Student (static ρ) | Master (ρ in search, 20k nodes) | Ratio |
|---|---|---|---|
| gen2 | 0.6790 | 0.8249 | **0.8231** |
| gen3 | 0.7005 | 0.8758 | **0.7998** |

The master improved by +0.0509 (table 2) from gen1→gen2's master to
gen2→gen3's master; the student improved by only +0.0215. A plausible
structural reason: as the master gets stronger, more of its strength
comes from **search** — plies of lookahead a static network cannot
reproduce by construction, no matter how well it's trained on the
master's output. If this holds, the ratio keeps falling every generation,
and a naive continuation of the gen1→gen2→gen3 step sequence
(+0.0916 → +0.0215, roughly a 4.3× drop in one generation) would put a
plateau around **~0.707** — below gen0 (0.7850) and well below akimbo
(0.8522) — for another full, expensive generation cycle. This is the
reasoning behind not running a gen4 exactly like gen1-gen3 and running
the capacity experiment in `gen3-dopo-il-plateau.md` Part A instead.

**Capacity experiment result (2026-09-16)**: retrained the identical gen3
dataset (same split, seed, scheduler, epoch budget, patience) with only
`HIDDEN` doubled from 1024 to 2048. Val loss minimum arrived at the same
epoch (3) as the 1024 run, then rose the same way — the signal that
matters more than the loss value itself, since a genuinely
capacity-starved model keeps improving for longer once given more of it.
Static ρ vs Stockfish: **0.6951, lower than the 1024 run's 0.7005**
(Δ = −0.0054, well below the pre-registered +0.01 "ambiguous" floor, let
alone the +0.02 bar for "capacity was the bottleneck"). nps at depth 12,
same position: 460,989 (2048) vs 625,699 (1024), ~26% slower. **Capacity
is not the bottleneck** — doubling the hidden layer cost real search
speed and did not improve rank correlation. The 1536 follow-up called for
in that document's decision rule is skipped: the rule was to check it
only if 2048 landed in the ambiguous band, and it didn't. The lever for
gen4, if there is one, is elsewhere — annotation depth, data
distribution, or an architecture change other than raw width. CSV:
`results/gen3_l2048_vs_stockfish.csv` (same script, same eval_set.epd,
same protocol as every other static measurement in this document).

## 5.11 Quiet-position filter census

Archived here even though it hasn't yet driven a decision — the data is
worth keeping regardless of what's done with it next. Census only (no
engine, no evaluation), on the full assembled gen3 dataset
(3,112,004 positions): what fraction has a `bestmove` that's a capture
(a common "not quiet" signal in NNUE training pipelines), broken down by
where the position's game originated and by piece count.

| | Count | % |
|---|---|---|
| `bestmove` is a capture (incl. en passant) | 613,683 / 3,112,004 | **19.72%** |
| Promotion without capture | 24,499 / 3,112,004 | 0.79% |

| Origin | Total | Captures | % |
|---|---|---|---|
| Normal-opening pool | 2,663,583 | 580,889 | **21.81%** |
| Endgame pool | 448,421 | 32,794 | **7.31%** |

| Pieces on board | Total | Captures | % |
|---|---|---|---|
| ≤8 | 910,678 | 70,449 | 7.74% |
| 9-12 | 523,124 | 84,255 | 16.11% |
| 13-20 | 841,870 | 215,169 | 25.56% |
| 21-32 | 836,332 | 243,810 | 29.15% |

Already discarded upstream by the existing check-position filter
(`extract_positions.py`, unrelated to captures): **491,246** positions
across all 54 shards.

**Two notes for whoever uses this next**: a capture filter removing
~20.5% of the dataset would cost nothing in *quantity* — training
saturates by epoch 3 with 3.11M positions (§3 and the training table),
well before running short of data would matter. But the piece-count
monotonicity means such a filter isn't just noise removal — it's also a
**reweighting of the position distribution** toward fewer pieces
(endgames, already only 7.31% capture-rate, are barely touched, while
normal-opening-derived, higher-piece-count positions lose over a fifth of
their volume). Know that before applying it.

**TODO, not done here**: verify the actual premise for filtering — that
capture positions really do show a larger static-vs-search evaluation gap
than quiet ones in this project's own data. This census establishes how
much a filter would remove, not whether removing it would help.

Script: `results/scripts/census_captures.py` (committed for
recomputability; the underlying game_origins/positions/annotated files it
reads are gen3's training data and are not committed, per this
repository's standing rule).

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

An earlier internal note's pre-registered expectation for gen2 was **0.76-0.78**. The
actual result was **0.6790** — a large miss, and that wrong number is
sitting inside all 99 committed manifests, so a reader will find it
regardless of whether this section exists.

**Why it missed**: the expectation was built by multiplying the master's
*search* ρ (gen1 network in search, 0.8072-0.8413 depending on nodes) by
the net-to-master ρ seen in gen1 (0.9230). That product is not a valid
transfer coefficient — it mixes a search-based quantity with a
static-network-vs-master quantity, exactly the kind of comparison this
whole project has repeatedly gotten burned by (see the "compare only
homogeneous quantities" rule adopted from generation 3 onward, and the
distinction kept strict throughout this document between tables 1-2 and
table 3).

**A pre-registration that never admits missing the round before is
decorative.** Admitting it is what makes gen3's pre-registration (5.7)
worth trusting.

---

## 6. Three-network round-robin — the Spearman/Elo exchange rate, measured

**These numbers are NOT CCRL ratings.** They are pairwise Elo
*differences* between three configurations of the identical binary and
search — only the network file changes. No external engine, no anchor,
no absolute scale. Answers "how many Elo does one point of static ρ cost
in this project," not "where does Luna sit on any public list." That
second question needs external anchors and wasn't attempted here (see
`tasso-di-cambio.md` Part B for why the originally planned CCRL-anchored
gauntlet was replaced by this design — cross-compiling anchor engines to
Oracle's ARM would have measured a different artifact than their
published x86 rating). This section is a distinct kind of quantity from
tables 1-3 and is kept separate from them for the same reason static and
search-based ρ are kept apart.

**Conditions**: engine commit `076defcb93d4a1dc834d4ecd5132f45ba9a311d2`
— **note**: this predates the `v3.1.4` tag (`8b219b4`) by three commits;
it has the quiescence-timeout fix that matters for search correctness but
not the TT-aging fix, the AI-generation-marker removal, or the SIMD
attribution added for v3.1.4. Binary verified byte-identical across all
three branches (same file, only `luna.nnue` differs), so this doesn't
bias the *relative* comparisons the round-robin measures — TT aging's
replacement-policy effect, if any, applies equally to all three arms —
but it means these numbers describe `076defc`, not the binary in the
v3.1.4 release, and that distinction is worth having on the record rather
than assumed away. Oracle, aarch64. TC 20+0.2 (seconds). 500 games per
pairing. Concurrency 3. Book: `8moves_v3.pgn` (public, 16 plies). Ponder
off. Hash 64MB / Threads 1, identical for every arm. Date: 2026-09-16.

Verified before playing: the three networks report three different
static evaluations on the same test position (akimbo +65cp, gen0 +43cp,
gen3 −15cp), and each branch's `luna.nnue` hash was checked against the
exact committed `nets/luna_genN.nnue` file it was supposed to be —
including a live re-check mid-tournament for the gen3 branch after its
99.4%+ score raised the "is this really loading what I think" question on
its own.

| Pairing | Score | Games | Score % | Elo difference | LOS |
|---|---|---|---|---|---|
| akimbo vs gen0 | 445–8–47 | 500 | 93.7% | **+469.0 ± 49.6** | 100% |
| akimbo vs gen3 | 494–0–6 | 500 | **99.4%** | **+887.7 ± 188.9** | 100% |
| gen0 vs gen3 | 381–50–69 | 500 | 83.1% | **+276.7 ± 35.5** | 100% |

**gen3 won zero of its 500 games against akimbo.** Zero time losses, zero
illegal moves, zero crashes across all 1,500 games — the first real
multi-hundred-game tournament run with this codebase. **Correction: this
robustness result belongs to commit `076defc`, not to the released
`v3.1.4` binary** (see the conditions note above — they differ by three
commits, including the TT-aging fix, which touches the replacement policy
and therefore search behavior). `v3.1.4` as released has not itself
played a multi-hundred-game tournament; see §6a below for that check.
PGNs: `results/girone/girone_AB_akimbo_vs_gen0.pgn`,
`girone_AC_akimbo_vs_gen3.pgn`, `girone_BC_gen0_vs_gen3.pgn` (raw data,
1,500 games total).

**Internal calibration check, reported first**: an old, informal
measurement (`non_conforme/README.md`) had gen0 losing to akimbo by
−339.8 ± 94.8 Elo over 113 games, on an older binary with a different TC
and book. This run's akimbo-vs-gen0 result (+469.0 ± 49.6) is the same
pairing, same sign, same order of magnitude (hundreds of Elo, both
statistically overwhelming) — but the confidence intervals don't overlap
([419, 519] now vs [245, 435] then). Expected given how much changed
between the two measurements (binary, TC, book, x86→ARM); reported
because a calibration check that silently drops an inconvenient gap
isn't a calibration check.

**Transitivity holds — the earlier draft of this section was wrong to
say otherwise.** Chaining the two narrower-CI results (akimbo−gen0 =
469.0 ± 49.6, gen0−gen3 = 276.7 ± 35.5) gives an indirect estimate of
akimbo−gen3 = 745.7 ± 61.0 (SE combined in quadrature: √(49.6²+35.5²)).
The direct measurement, 887.7 ± 188.9, has a 95%-ish interval of roughly
[698.8, 1076.6] — **745.7 falls inside it.** Testing the 142.0 Elo gap
between the two estimates against its own standard error gives z≈1.4,
p≈0.16: not a significant discrepancy, just the imprecision expected at a
99.4% score, where the derivative of the logistic curve is steep and a
small movement in win rate corresponds to a large movement in the implied
Elo (hence the direct estimate's own wide ±188.9). Consequence: **the
indirect path is about three times more precise than the direct one**,
because it routes through the two better-measured pairings. Combining
direct and indirect by inverse-variance weighting:

**akimbo − gen3 ≈ 759 ± 58 Elo** — used as the reference estimate for
the compliance cost below, in preference to the noisier direct
measurement, precisely because it's built from the two pairings the
logistic model estimates most precisely.

**The Spearman/Elo relationship is concave, not linear — report the two
local slopes, not one average.** A single three-point regression gives
≈574 Elo per 0.10 of ρ, but that number is misleading: it averages over a
relationship that clearly bends.

| Segment | Δρ | ΔElo | Elo per 0.10 ρ |
|---|---|---|---|
| gen3 → gen0 | 0.0845 | 276.7 | **327** |
| gen0 → akimbo | 0.0672 | 469.0 | **698** |

The slope more than doubles between the low segment and the high one. The
segment that matters for where Luna actually is today is the low one,
**327 Elo per 0.10 of ρ** — not 574. Concretely: moving static ρ from
0.70 to 0.75 is worth **≈165 Elo** on the low-segment slope, not the
≈287 Elo a single average slope would suggest. Three points describe a
direction and a visible curvature, not a quantified curve — this is a
first measurement, not a fitted function, and should be read as such.
This is nonetheless the first *measured* value for the quantity
`RESULTS.md` 5.6 previously called "inferred, not measured."

**The compliance cost**: akimbo vs gen3 is the pairing that answers "what
does TCEC-conformant training cost, in Elo, right now" —
**≈759 ± 58 Elo** (combined estimate; the direct measurement alone gives
887.7 ± 188.9, even lower-bounded at ≈699 it clears the same threshold).
Against the +250 threshold fixed in advance (`girone-tre-reti.md` §6):
**evaluation is where the work is** — the quiet-position filter and other
eval-side levers take priority over another bootstrap generation,
unambiguously, not a borderline call, regardless of which of the two
estimates (759 or 887.7) is used.

**The uncomfortable conclusion, stated without softening it**: three
generations of this bootstrap chain do not produce a network competitive
with what the project already had — gen3 costs ~759 Elo against akimbo
and, more pointedly, **~277 Elo against gen0, a network this same project
already trained, using external labels**. That 277 Elo figure is the
real cost of conformance as currently practiced here: not the distance to
a third party, the distance to this project's own prior, non-compliant
attempt. This is not a claim that training on one's own data doesn't
work. It's a claim that this pipeline, at its current scale and method
(millions of positions rather than the hundreds of millions typical
elsewhere, 20,000-node labels, no quiet-position filter), is far from
what competitive self-training requires — and that closing that gap with
more generations shaped like gen1-gen3 is not the lever: the bootstrap
scale already plateaued (step +0.0916 → +0.0215), the transfer ratio is
declining (0.8231 → 0.7998), and capacity is demonstrably not the
bottleneck (§5.10). The lever is elsewhere, starting with evaluation
quality itself.

**Three pre-registered predictions, made before their results existed,
collected in one place**: gen2's expectation (0.76-0.78) missed (§5.9,
actual 0.6790). gen3's two expectations (0.73-0.76 and ~0.718) both
missed, though the ratio-based one came closer (§5.7, actual 0.7005).
This round-robin's decision rule (>250 Elo ⇒ evaluation work has
priority, fixed in `girone-tre-reti.md` before any game was played) is
the third prediction and the first to land decisively — the measured
cost clears the threshold by roughly 3× even at its most conservative
reading. Two misses and one clear hit is the record as it stands. The
two misses aren't a reason to discount the practice of pre-registering;
they're the reason this third result can be trusted as a genuine test
rather than a foregone conclusion dressed up afterward — a method that
only ever confirms itself isn't measuring anything.

## 6a. Does the released binary hold up? v3.1.4 vs 076defc

Triggered by the discovery above (§6's conditions note): the round-robin's
zero-crash/zero-timeloss/zero-illegal-move result belongs to `076defc`,
not to the `v3.1.4` binary actually released. `v3.1.4` differs by three
commits — the TT-aging fix (`tt.rs`, changes the replacement policy),
AI-generation-marker removal, and a SIMD attribution comment — of which
only the first can plausibly touch playing strength.

Rather than repeat all 1,500 round-robin games for a label correction, a
single focused match: `v3.1.4` vs `076defc`, **same network on both
sides** (akimbo, embedded — no external `luna.nnue` on either branch, so
this isolates the binary/search-code as the only variable), 400 games,
TC 20+0.2, concurrency 3, same book (`8moves_v3.pgn`, 16 plies), Ponder
off, Hash 64MB / Threads 1, Oracle aarch64, started 2026-09-16.

Verified before playing: `v3.1.4` branch binary sha256
`f1701745983c57ce3e1562753b0c040029c4c351ed20dbf6d8bfb7ffbc57c1f7`
(matches the tagged release build), `076defc` branch binary sha256
`f9edde89027b781e3640fd8de809b03d37b4952ab8ff9724af42c7e85d44f55b`
(matches the round-robin's binary) — both fall back to the embedded net
as expected, confirmed via UCI startup banner on each.

This gives two things from one match: whether the actually-shipped binary
holds up over several hundred games (the check the announcement needs),
and, as a side effect, the first measured Elo value for the TT-aging fix
itself — previously untested.

**TODO: results pending, match in progress as of this writing.** PGN and
final Elo table to be added here once it completes; `results/*.csv` for
this comparison is not applicable (no Stockfish/rho measurement here —
raw PGN and cutechess log under `results/girone/` once copied over, same
as the three-network round-robin).

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
