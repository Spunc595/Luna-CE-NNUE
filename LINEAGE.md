# Lineage

Luna's NNUE is bootstrapped generation by generation: each net becomes the
self-play evaluator and annotation master for the next generation's data.
This document is the answer to the one question that actually matters —
**what does the presented net descend from** — because conformance is a
property of the whole chain: one link touched by an external label source
contaminates everything downstream.

As of this writing (2026-09-16), **gen3 is the current presentation
candidate.**

**Amendment to the candidacy rule (2026-09-16), written down rather than
applied silently.** The original rule (`RESULTS.md` 5.7) said gen3 would
replace gen2 as candidate only if its ρ landed inside the pre-registered
0.73-0.76 interval. It measured 0.7005 — outside that interval — and by
the letter of the original rule gen2 would stay candidate. That rule is
now judged to have been the wrong criterion, for a specific reason: the
0.73-0.76 interval was a **test of a prediction method** (does the
static-trend extrapolation forecast well), not a **test of the network's
merit**. Gen3 is the objectively better network by the only quantity this
project measures for this purpose — ρ 0.7005 vs Stockfish, against gen2's
0.6790, on the identical 2,000-position set, same script, same protocol.
Holding a better-measured network out of the candidate slot because a
*forecast about it* missed would be optimizing the wrong target.

The prediction failure itself is not discarded — it's recorded in full in
`RESULTS.md` 5.7/5.10, including the finding that drove this amendment
(the master/student transfer ratio is declining, not constant, which is
why both pre-registered estimators overshot). That failure stays exactly
as embarrassing as it was; it just doesn't get to also disqualify the
network it happened to be a bad prediction about.

**Chess-strength note, now measured, not just flagged as pending.** This
amendment concerns Spearman-based candidacy specifically. Playing
strength is a different quantity, and it says something less comfortable:
`RESULTS.md` §6 measured gen3 losing **~759 Elo to akimbo and ~277 Elo to
gen0** (a network this project already had, trained on external labels)
in a 1,500-game round-robin. **The distributed binary still embeds
akimbo, not gen3, and this is why**: gen3 is the better-measured network
on the one axis this repository's bootstrap methodology optimizes for
(ρ vs Stockfish), and it is a substantially weaker *player* than what
this project already shipped. Both facts are true at once and both are
recorded — candidacy for this repository's own lineage tracking is not
the same claim as fitness to be the default embedded network, and
conflating them would misrepresent either one.

```
classical eval  (no external source)
      │   self-play + annotation via Luna's own SEARCH
      ▼
    gen1   nets/luna_gen1.nnue   engine 076defc (labels) / b0cfb937 (self-play)   ρ 0.5874
      ▼
    gen2   nets/luna_gen2.nnue   engine 076defc (labels and self-play)            ρ 0.6790
      ▼
    gen3   nets/luna_gen3.nnue   engine 076defc (labels and self-play)            ρ 0.7005   ← current candidate (amended rule, see above)

separate branch, NOT an ancestor of any presented network:
    external labels (Stockfish) ──► gen0   ρ 0.7850   [NON-COMPLIANT]
```

**The presented network does not have gen0 among its ancestors.** gen0
exists only as a comparison reference (see table 1 in `RESULTS.md`) and
did not contribute any training data to gen1 or later networks — it
predates the TCEC rule applied from gen1 onward within this project
(details in `non_conforme/README.md`).

## Train/validation split, and the two scripts `train.py` used to name

> **Provenance warning.** `split_train_val.py`, `resolve_truncated_wdl.py` and `pov.py`
> in `pipeline/dataset/` are **not** the chain that produced the published gen1-gen3
> datasets. Those used `build_training_dataset_gen*.py` (per-game split, seed 42,
> val fraction 0.025). The three scripts work on the older 6-column layout and are
> published for completeness, not as provenance; each carries the same warning in its
> docstring.

`train.py`'s docstring used to name a chain `extract_positions.py ->
annotate_positions.py -> resolve_truncated_wdl.py -> split_train_val.py`, and
the last two scripts were not in this repository. They have been found and are
now published in `pipeline/dataset/` (with `pov.py`, which `resolve_truncated_wdl.py`
imports), but **they are not what produced the gen1-gen3 datasets**:

* They belong to the older 6-column chain (`fen, result, game_id, eval_cp,
  is_mate, bestmove`), whose first annotation step, `annotate_positions.py`,
  is the Stockfish-based one kept in `non_conforme/`. The 6-column output cannot
  be read by the current `dataset.py`, which accepts 5 columns only.
* For gen1-gen3 the correction of the result of truncated games is done inside
  the annotators (`annotate_incremental_gen*.py`, same 200 cp band as `pov.py`),
  and the per-game split is done by `pipeline/dataset/build_training_dataset_gen{1,2,3}.py`.
  What cannot be established from the files that still exist is whether
  `resolve_truncated_wdl.py` was also executed on any gen1 data before the
  annotators took over its job; the published annotators do not call it.

**The split of the published datasets is reproducible**, without those two
scripts. Per-game split, `random.Random(42)` over the games in file order, the
first `round(n_games * 0.025)` games to validation (recorded in each
generation's `dataset_composition` file as `val_fraction_requested: 0.025`,
`seed: 42`). Until 2026-09-19 the scripts had `--val-fraction` defaulting to
`0.03` (and `split_train_val.py` to `0.05`): running them without the flag
silently gave a split different from the published one. Both `--val-fraction`
and `--seed` are now required on the command line, in all five scripts, so the
value that ends up in the composition file has always been declared by whoever
ran the command.
Checked on 2026-09-19, re-running the published scripts (as at commit `644c923`) on
the original data, into scratch directories, with the exact arguments recorded in
each generation's composition file:

| Generation | Run on | Command (from `pipeline/dataset/`) | Result |
|---|---|---|---|
| gen1 | PC (Windows) | `build_training_dataset_gen1.py --start 1 --end 46 --val-fraction 0.025 --seed 42` | `gen1_train.tsv` / `gen1_val.tsv` **byte-identical** to `checksums/gen1/dataset.txt` |
| gen2 | Oracle (Linux) | `build_training_dataset_gen2.py --start 1 --end 53 --val-fraction 0.025 --seed 42` | `gen2_train.tsv` / `gen2_val.tsv` **byte-identical** to `checksums/gen2/dataset.txt` (row counts and game counts also equal to the composition file) |
| gen3 | PC (Windows) | `build_training_dataset_gen3.py --start 1 --end 54 --val-fraction 0.025 --seed 42` | rows identical, in the same order; hash equal to `checksums/gen3/dataset.txt` after converting CRLF to LF (see below) |

All three published splits are regenerated exactly by the scripts in this repository.
Consequently no list of train/validation game IDs is published.

**Line endings.** The published checksums differ in line endings for a historical
reason: gen1 was built on Windows (CRLF checksums), gen2 and gen3 on Linux (LF), because
the scripts opened their output files without specifying the terminator and Python
translates `
` on Windows. Since 2026-09-19 every write-mode `open()` in the
split scripts passes `newline="
"`, so **the output is LF on every platform**.
After that change, gen3 rebuilt on Windows matches `checksums/gen3/dataset.txt` raw,
with no conversion, and gen2 rebuilt again on Linux is unchanged. The gen1 CRLF
checksums stay as they are: they are a historical fact about how that file was
produced, not an error to correct and not something to regenerate. Rebuilt with the
current scripts, gen1 gives the same rows with LF endings, whose hash is the published
one computed after removing the CRs (`310e0476...` / `3b4a2398...`).

## Annotation failures, and the rejection threshold for generation 4

**What was measured** (details in `RESULTS.md` 5.14): the annotators drop a
position silently when its annotation fails and never stored how many. The counts
were on disk only for gen1 (all shards) and gen2 shards 1-9 (a superseded PC run); the
Oracle logs of gen2 and gen3 are 0 bytes (stdout was redirected without flushing). The
gen2 and gen3 counts were nevertheless still in the memory of the idle annotators, and
were recovered from there on 2026-09-20 (`results/annotation_recovered/`). Rebuilt
from the surviving input and output files and checked against the original counts,
shard by shard, for all three generations: **zero failed annotations in gen1, gen2 and
gen3**, the reconstruction equal to the original counts (no mismatch), and every distinct position of
each input appears in its output, so no position was lost for good. The gen3
annotator that ran on Oracle used a worker named `_annotate_chunk_worker_gen3.py`; it is
byte-identical to the gen2 worker, and the published gen3 annotator points at the
gen2 worker file (same code, one file fewer to publish).

**What changes from generation 4** (`annotate_incremental_gen4_oracle.py`; nothing
already published was regenerated or edited): failed FENs are written to a separate
file, never into the dataset; the counts `annotation_n_input`, `_n_new`, `_n_dup`,
`_n_force`, `_n_written`, `_n_failed` go into every shard manifest; stdout is
line-buffered.

**Rejection threshold, declared on 2026-09-19, before any generation-4 annotation
exists:** a generation is **not used for training** if the failure rate
`failed / (new + force)` exceeds **0.1%** (1 in 1,000). It is enforced twice: the
annotator refuses to write any single shard above it and stops, and
`pipeline/measure/check_annotation_failure_rate.py` checks the whole generation from
the manifests (and refuses a generation whose manifests lack the counts). The number
is arbitrary and was chosen before seeing any data of the generation it will judge:
observing zero failures in about 8.5 million annotations, any measurable rate would
point at the environment (crashes, memory, timeouts) and not at the positions, and at
the limit the hole would be at most ~3,000 positions in 3 million.

## Training environment

None of the training logs records the software they ran on, so the "Training
machine" row of each generation is reconstructed, and this is how far it can be
trusted:

* **Hardware**: read from the machines that trained the networks (the PC for gen1,
  the Oracle VM for gen2 and gen3); the logs confirm `Device: cpu` for all three, and
  neither machine has a usable GPU.
* **Python and torch versions: not recorded.** They are deduced from the only
  installation on each machine and its install date: on Oracle torch 2.14.0+cu130 is
  the only torch present (user site, `pip`), installed on 2026-09-09, before the gen2
  training (ended 2026-09-15) and the gen3 training (2026-09-16), with no later
  install or upgrade in the same site-packages; on the PC torch 2.13.0+cpu was
  installed on 2026-08-06 and Python 3.14.0 on 2025-10-07, both before the gen1
  training (2026-09-12), with no later install of either. This holds unless a
  package was replaced without leaving a newer install record; it is an inference from
  file dates, not a record.
* **Not recorded and not deducible**: the number of torch threads used at the time
  (the default on a 4-thread/4-core machine is 4), the load of the machine during
  training (on Oracle a lichess bot shares the machine), the exact command line (it
  is reconstructed from the logs: binary format, 25-epoch budget, batch size 8192,
  learning rate 1e-3, eval lambda 0.7, patience 6 for gen3).

Speed check of the environment as it is today (2026-09-19, Oracle): 300 batches of
the gen3 training at gen3's parameters, batch 8192, ran at 3.06 batch/s (25,035
positions/s) with 4 torch threads, i.e. about 121 s of training per epoch of 371
batches plus about 1.7 s of validation, consistent with the 122.5-128.6 s per epoch
that the gen3 log records. Re-exporting the gen3 best checkpoint (`gen3_checkpoint.best.pt`,
37,791,889 bytes) with today's `model.py` and `export.py` reproduces
`nets/luna_gen3.nnue` byte for byte (sha256 `82aa1bf0...`).

## Generation 1

| Field | Value |
|---|---|
| Network | `nets/luna_gen1.nnue` (`sha256`: see `nets/luna_gen1.nnue.sha256`) |
| Self-play master | classical PST evaluation (no network, no external source) |
| Engine commit — self-play | `b0cfb9378fad417bf03d6bf662d4738d7adadc66` |
| Engine commit — annotation | `076defcb93d4a1dc834d4ecd5132f45ba9a311d2` |
| Commit divergence note | self-play started before the quiescence fix (`076defc`); annotation used it. The fix only concerns node/time budget enforcement inside `quiescence`, not move legality — positions extracted under the earlier commit remain valid, only the label comes from the fixed commit. |
| Self-play nodes | 3,000 |
| Annotation nodes | 10,000 |
| Machine | Oracle (self-play and annotation) |
| Training machine | PC (Windows 11 Home), AMD Ryzen 3 3200U, x86-64, 2 cores / 4 threads, 5.9 GB RAM; **CPU only** (the training log says `Device: cpu`). Python 3.14.0, torch 2.13.0+cpu — **deduced, not recorded at the time** (see below). Epochs of 294-301 s in the log (12 epochs). |
| Shards | 46 (`gen1_shard_00001`..`00046`) |
| Games | 230,000 (assigned = completed, 100%) |
| Raw positions | 3,300,643 |
| Unique positions | 2,135,009 (64.7%) |
| Yield | 14.3506 pos/game (denominator: completed games = assigned games) |
| Train/val dataset | 2,080,991 / 54,018 positions, 209,480 / 5,371 games (split by game, seed 42) |
| Minimum val loss | 0.013316 |
| ρ vs own master | 0.9230 |
| ρ vs Stockfish (static) | 0.5874 |
| Dataset checksum | TODO — see `checksums/gen1/README.md` |
| Opening pool | **filtered with Stockfish** (depth 6, ±200cp threshold) — see note below |

**Note on the opening filter** (found while re-reading the code, not
correctly declared until now — corrected 2026-09-15):
`pipeline/generate/gen_random_openings.py`, used by
`generate_shards_gen1.sh`, discards openings with `|eval| > 200cp` by
querying **Stockfish**, not Luna's classical evaluation. From gen2 onward
the filter uses the previous generation's network (Luna itself) —
correct there, not here.

**This is not an error to hide, nor to fix by regenerating**: redoing gen1
would mean redoing gen2 and gen3 too (weeks, for a *selection*
contamination, not a *label* one). It stays declared as-is.

**How it propagates**: no gen1 position or label was produced by
Stockfish — only the *selection* of self-play starting positions. gen2
regenerated its own openings with the internal filter (gen1 network), so
the external influence survives only indirectly, through the gen1 network
used as master — **it attenuates with each generation, it does not
compound**. A fully clean chain would require regenerating from gen1: not
done, cost disproportionate to the goal.

## Generation 2

| Field | Value |
|---|---|
| Network | `nets/luna_gen2.nnue` (`sha256`: see `nets/luna_gen2.nnue.sha256`) |
| Self-play and annotation master | gen1 network, in search |
| Engine commit — self-play | `b0cfb9378fad417bf03d6bf662d4738d7adadc66` |
| Engine commit — annotation | `076defcb93d4a1dc834d4ecd5132f45ba9a311d2` |
| Self-play nodes | 3,000 |
| Annotation nodes | 20,000 (chosen: knee of the 10k/20k/50k curve) |
| Machine | Oracle (self-play, and — after reconciliation, see below — the entire annotation too) |
| Training machine | Oracle VM (OCI `VM.Standard.A1.Flex`, KVM), ARM Neoverse-N1, aarch64, 4 cores (1 thread each), 23 GB RAM, Ubuntu 24.04.4; **CPU only** (no GPU on the machine; the training log says `Device: cpu`). Python 3.12.3, torch 2.14.0+cu130 (CUDA build, CUDA unavailable). Versions **deduced, not recorded at the time** (see below). Epochs of 121-174 s in the log (10 epochs, mean 149 s). |
| Shards | 53 (`gen2_shard_00001`..`00053`) |
| Games | 265,000 (assigned = completed, 100%) |
| Raw positions | 3,083,063 |
| Unique positions | 2,972,944 (96.4%) |
| Yield | 11.6342 pos/game (denominator: completed games = assigned games) |
| Train/val dataset | 2,899,216 / 73,728 positions, 249,020 / 6,385 games (split by game, seed 42) |
| Minimum val loss | 0.018874 (epoch 4, early stop at epoch 10) |
| ρ vs own master | 0.9508 |
| ρ vs Stockfish (static) | 0.6790 |
| Dataset checksum | TODO — see `checksums/gen2/README.md` |

**Provenance incident (declared, not hidden)**: annotation was meant to
move from the PC to Oracle midway through the generation. The PC process
didn't stop, due to a harness permission error, and re-annotated shards
3-8 in parallel with Oracle (which had already done them), producing for
some shards a real mismatch between the `.tsv` (from one run) and the
manifest (from the other) — a fault invisible in the numbers themselves:
the dataset looked healthy, the provenance was false. Caught and fixed by
reconciling everything onto the Oracle run (the sole authoritative source
for shards 3-53). It later turned out that shards 1-2 didn't come from
the Oracle run either (no `annotation_machine` field in the manifest,
timestamps from the original PC run): **redone on Oracle** under the same
`global_seen.bin` used for the other 51, instead of letting two dedup
states coexist in the same script. The whole final gen2 dataset comes
from a single continuous run. Full detail kept in the author's private
development notes (not published).

A record that documents a caught-and-fixed fault is more credible than a
spotless one: the latter suggests the checks don't exist, not that they
never found anything.

## Generation 3

Complete and measured. **The current presentation candidate** — see the
amendment note at the top of this document: its ρ (0.7005) landed below
the originally pre-registered 0.73-0.76 interval, but that interval
tested a prediction method, not the network's merit, and gen3 is the
objectively better network of the two.

| Field | Value |
|---|---|
| Network | `nets/luna_gen3.nnue` (`sha256`: see `nets/luna_gen3.nnue.sha256`) |
| Self-play and annotation master | gen2 network, in search |
| Engine commit | `076defcb93d4a1dc834d4ecd5132f45ba9a311d2` (self-play and annotation, same commit from the start — no divergence) |
| Self-play nodes | 3,000 |
| Annotation nodes | 20,000 (master gate: ρ 0.8537/0.8760/0.8887 at 10k/20k/50k, above the gen2 master's 0.8072/0.8285/0.8413) |
| Machine | Oracle, sole machine start to finish (method rule fixed after the gen2 incident) |
| Training machine | Oracle VM (OCI `VM.Standard.A1.Flex`, KVM), ARM Neoverse-N1, aarch64, 4 cores (1 thread each), 23 GB RAM, Ubuntu 24.04.4; **CPU only** (no GPU on the machine; the training log says `Device: cpu`). Python 3.12.3, torch 2.14.0+cu130 (CUDA build, CUDA unavailable). Versions **deduced, not recorded at the time** (see below). Epochs of 122.5-128.6 s in the log (9 epochs before the early stop). |
| Shards | 54 (`gen3_shard_00001`..`00054`) |
| Games | 270,000 (assigned = completed, 100%, verified) |
| Raw positions | 3,210,755 |
| Unique positions | 3,112,004 (96.9%) |
| Yield | 11.8917 pos/game (denominator: completed games = assigned games, verified) |
| Dataset train/val | 3,033,768 / 78,236 positions, 253,434 / 6,498 games (split by game, seed 42) |
| Minimum val loss | 0.022381 (epoch 3, early stop at epoch 9 of a 25-epoch budget) |
| ρ vs own master | 0.9475 |
| ρ vs Stockfish (static) | **0.7005** |
| Dataset checksum | `checksums/gen3/` |
| Known confound | the normal-opening pool was regenerated with the gen2 network's filter (not reused from gen2). The gen2→gen3 step in ρ is therefore attributable to network **and** opening distribution together, not the master alone — repeated in `RESULTS.md` table 1's own row, see 5.8. |

**Gate 0 (master-identity check, done before assembling anything)**: 20
positions sampled from shard 1, re-evaluated at `go nodes 20000`/1 thread
in three configurations — deterministic at fixed nodes, so the match had
to be exact, not approximate. External gen2 network: **20/20 exact
match**. Classical eval: 0/20. Embedded akimbo network: 0/20. Confirms the
annotation labels genuinely came from the gen2 network, not a
misconfigured fallback.

**Round-trip (PyTorch vs. engine, on export)**: max 37.07cp / avg 12.84cp
over 20 positions. Re-ran the identical check against the already-shipped
gen2 checkpoint for calibration: max 24.33cp / avg 11.22cp — same order of
magnitude, same known quantization gap documented for the whole project
(see RESULTS.md and the engine repository's own notes on it), not a new
regression specific to gen3.
