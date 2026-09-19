# Lambda sweep — decision rule (registered before any training run)

Written and committed BEFORE the first training run of the sweep; the commit
timestamp is the proof of ordering. Nothing below is edited after seeing numbers;
any later change is a new, dated amendment at the end of this file.

## Hypothesis

In the label `lambda * sigmoid(K*eval) + (1-lambda) * WDL` the `eval` component
comes entirely from the master network; the WDL is the only part that does not come
from it. The static-vs-search diagnostic (RESULTS.md 5.12) showed that gen3
inherited the static blind spots of gen2 (nearly identical gap profiles per class).
The hypothesis is that it is the **weight of the WDL component** that determines how
much the student copies the master's limits.

## Registered prediction

As lambda falls, `|ratio_student - 1.385|` **grows monotonically**.

`ratio` is the median static-vs-search gap of the capture class over the median gap of
the quiet class, in sigmoid space (defined exactly below); 1.385 is gen2's (the
master's), 1.362 is gen3's (the student's). The ratio is chosen because it is
**scale-free**: a network trained at a low lambda may be worse calibrated in
centipawns and inflate every gap in absolute value, and a ratio does not notice.

**Nothing is predicted about rho.** A label weighted more on the WDL is also noisier:
it could break the inheritance while making rho worse. These are two separate
questions: the **mechanism** is decided by the ratio, the **lambda of gen4** is decided
by rho.

## Design

Two phases. **Neither phase produces gen4**: they produce the number that gen4 will be
designed with.

### Phase 1 — the floor (lambda does not vary)

Four runs at **lambda = 0.7**, everything identical to gen3: same binary dataset
(`gen3_train_bin` / `gen3_val_bin`, the published gen3 dataset), batch size 8192,
learning rate 1e-3, cosine schedule over a 25-epoch budget, patience 6, same split
(seed 42, fixed when the dataset was built), same code (`pipeline/train/`, commit that
adds `--train-seed`), same machine and environment as measured in `LINEAGE.md`
("Training environment": Oracle, CPU only, 4 torch threads, torch 2.14.0+cu130), runs
one after the other, the lichess bot and the status-upload watchers stopped for the
duration.

| run | training seed |
|-----|---------------|
| A1  | A = 101 |
| B   | B = 202 |
| C   | C = 303 |
| A2  | A = 101 again |

The three seeds were chosen arbitrarily and are declared here before any run.

What the seed varies: the weight initialisation. It does **not** vary the order of the
batches: the loader does not shuffle, in this sweep as in gen1-gen3 (the data were
shuffled once when the dataset was built), and changing that would make the runs
different from gen3's.

The network taken from each run is the one exported from the **best-validation
checkpoint** (as for the published gen3), with the current `export.py` (gates included).

* **A1, B, C** measure the variance due to the seed. **The floor** is, separately for
  rho and for ratio, `max - min` over A1, B and C.
* **A1 versus A2** measure something else: if two runs with the **same** seed differ,
  the training is not deterministic (on a multi-threaded CPU that is not a given), a
  reproducibility fact the repository must know whatever lambda does. Reported as: sha256
  of the exported nets identical or not, and the difference in rho, ratio and validation
  curve. No threshold; A2 does not enter the floor.

### Continuation condition (Phase 1 -> Phase 2)

At least one of the four runs must reproduce the published gen3 rho (**0.7005**) within
the floor itself: `|rho_run - 0.7005| <= floor_rho` for at least one run of A1, B, C, A2.
**If none does, the sweep does not start**: something changed between then and now, and
it must be found first.

### Phase 2 — only if Phase 1 passes (declared now, run later)

`lambda in {1.0, 0.4, 0.0}`, two seeds each (A = 101 and B = 202), everything else as in
Phase 1. **An effect of lambda counts only if it exceeds the floor of Phase 1**, on the
quantity it is claimed for (ratio for the mechanism, rho for the choice of gen4's
lambda). The decision rules for Phase 2 (how the monotonicity is judged with two seeds
per point) are written in an amendment to this file, committed before the first Phase 2
run.

## What is measured on each network

The network exported from each run is identified before anything else is measured: its
sha256 goes next to every result row, and it passes the identity gate of the
static-vs-search diagnostic: the first 20 positions of the evaluation set, `eval` with
the network and with the embedded network, **the values must differ on all 20** (20/20).

Then, per network:

1. **rho**: Spearman between Stockfish's recorded eval and the network's static `eval`,
   on the 2,000-position sample of RESULTS.md table 1 (`measure_static_vs_stockfish.py`,
   then `pipeline/measure/sweep_measure.py`, all 2,000 rows, raw values). The same
   computation gives 0.7005 for gen3 from the committed CSV.
2. **ratio**: `diagnose_static_search_gap.py` (20,000 nodes), then
   `pipeline/measure/sweep_measure.py`: median gap of the capture class over median gap of
   the quiet class, `gap = |sigmoid(K*search) - sigmoid(K*static)|`, `K = ln(10)/400`. The
   same computation gives 1.385 for gen2 and 1.362 for gen3 (1.3848 and 1.3622).
3. the epoch of the minimum validation loss, and its value.

For calibration the published gen3 network is also measured today with the same
procedure and engine; that row is a reference for the procedure and takes no part in the
floor or in the continuation condition (which uses the published 0.7005).

## Artifacts

The four checkpoints (about 38 MB each) and four networks (6.3 MB) stay on the Oracle
server in a dedicated scratch directory and are **not published**: until it is known what
is worth keeping, the repository gets the **numbers**, not the weights. Deletion is manual,
when decided, looking at what is deleted.
