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


---

## Amendment 1 — Phase 2 (registered 2026-09-20, before the first Phase 2 run)

**Why the amendment.** The original prediction used the capture/quiet ratio, whose seed-to-seed
floor turned out to be 0.3307 against a difference of interest of 0.023: it is not a usable
instrument and is abandoned. The inheritance measure of RESULTS.md 5.15 has a floor of 0.0070 and
replaces it. (Phase 1 also measured the floor of the static rho against Stockfish: 0.0103.)

**What stays open.** 5.15 established that the inheritance exists, but not whether it comes from the
**label** or from the **closeness of the training data**: the order gen2 > gen1 > akimbo is also the
order of distance in the lineage. Varying lambda separates the two, because it keeps data,
architecture and split fixed and changes only how much of the label comes from the master.

**Design.** `lambda in {1.0, 0.4, 0.0}`, **two seeds each: 101 and 202**. They are the seeds of
Phase 1 on purpose: the point `lambda = 0.7` is already measured with the same seeds (runs A1 and B)
and is not redone, and the comparison between lambdas stays paired on the seed. Everything else as
in Phase 1 and gen3 (same binary dataset, batch 8192, lr 1e-3, cosine over 25 epochs, patience 6,
split seed 42, same code and machine, one run after the other, the bot and the watchers stopped).
Every network passes the 20/20 identity gate and its sha256 is printed next to each result row.

**Quantities** (for each of the six new networks, with the known values of A1 and B beside them):
static rho against Stockfish; rho(e_S, e_gen2) (inheritance from the master); rho(e_S, e_akimbo) (the
control: akimbo has nothing to do with the label at any lambda); rho(e_S, e_gen1) (intermediate
reference, as in 5.15); epoch and value of the minimum validation loss and the epochs run. `e_X` is
the vector of signed static errors defined in 5.15, `sigmoid(K*search_X) - sigmoid(K*static_X)`, each
network with its own 20,000-node search. Floors already measured, used as the yardstick: **static
rho 0.0103** (Phase 1), **rho(., gen2) 0.0070** (5.15).

**Prediction A — it goes down.** As lambda falls, `rho(e_S, e_gen2)` decreases. Condition: the value at
`lambda = 0.0` is lower than the value at `lambda = 1.0` by **more than three times the floor**
(> 0.021). Monotonicity over all four points is reported but **not required**: with two seeds per
point a local inversion is expected.

**Prediction B — it stays put.** The excursion of `rho(e_S, e_akimbo)` over all four lambdas is
**less than three times the floor** (< 0.021).

**How the combinations are read** (written now, not afterwards):

* **A yes, B yes** -> the inheritance goes through the label. A strong result, and the lever for
  generation 4 is the design of the target.
* **A yes, B no** (akimbo goes down too) -> lowering lambda makes the network noisier and less in
  agreement with **everybody**. It is not inheritance specific to the master: not demonstrated.
* **A no** -> the weight of the label does not govern the agreement with the master, which comes from
  the distribution of the data and the architecture. **The inheritance line is closed**: a fifth
  measure is not sought.

**The lambda of generation 4 is a separate question**, decided on static rho: the lambda that
maximises it, provided the advantage exceeds the floor of 0.0103. If rho is flat within the floor
over all four lambdas, then **the weight of the target is not a quality lever**: generation 4 stays at
0.7 and the search goes elsewhere. That is a legitimate outcome and is declared as such, not worked
around.

**No outcome of this phase produces generation 4.** It produces the numbers with which to design it.

**Two practical warnings.** `lambda = 0.0` trains on the **game result alone** (the label is 0, 0.5
or 1 and nothing else): the network may stop very early or come out much worse. That is an outcome to
report, not a fault, and it is the extreme that is needed precisely because it zeroes the master's
component. If a run behaves anomalously (early stop in the first epoch, a loss that does not go down, a
network that fails the export gate), **stop and report** instead of relaunching it with other
parameters: a missing point is better than a point obtained by changing the rules midway.

### Operational definitions (added while registering, before any Phase 2 run; they resolve what the text above leaves open, not what it decides)

* **The value of a point** (a lambda) is the **mean of its two seeds** (101 and 202). For lambda 0.7
  the two seeds are A1 and B. The excursion in B is `max - min` over the four per-lambda means of
  rho(e_S, e_akimbo). Per-seed values and the per-seed differences (paired on the seed) are reported
  as well and decide nothing.
* **Prediction A** is judged on `mean_rho(e_S, e_gen2)[lambda 1.0] - mean_rho(e_S, e_gen2)[lambda 0.0] > 0.021`
  (strict, unrounded values).
* **The lambda of generation 4:** static rho per lambda is the mean of its two seeds. If
  `max - min` of the four means is <= 0.0103, rho is flat and generation 4 stays at 0.7. Otherwise the
  best lambda is the one with the highest mean, and it is adopted only if its mean exceeds the mean at
  lambda 0.7 by more than 0.0103 (if the best is 0.7 itself, generation 4 stays at 0.7).
* **Anomaly** (the "stop and report" of the warnings): a run that ends after fewer than three epochs,
  a training process that exits with an error, or a network refused by the export gate. The driver
  stops after such a run; the runs still to do are not started until it is decided what to do.
