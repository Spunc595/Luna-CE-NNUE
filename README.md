# luna-nnue

Data provenance, pipeline, and results for the NNUE networks of
[Luna Chess Engine](https://github.com/Spunc595/Luna-Chess-Engine).
A separate repository from the engine itself: this is where the history
of *how* each network was generated and measured lives, not the engine's
own code.

Public. The numbers in here don't always look good (the compliant network
sits below gen0, which sits below akimbo) — publishing them is the choice,
not a compromise: a record that shows the uncomfortable numbers too is
worth more than any unverifiable provenance claim.

## Where to start

- **[`LINEAGE.md`](LINEAGE.md)** — what each presented network descends
  from. The most important question we'll be asked.
- **[`COMPLIANCE.md`](COMPLIANCE.md)** — the TCEC NNUE compliance
  declaration, phase by phase, with an explicit list of every place
  Stockfish appears in the repository and why it isn't a violation.
- **[`RESULTS.md`](RESULTS.md)** — the tables. Every number is
  recomputable from the `.csv` files in `results/`.

## Structure

```
LINEAGE.md            the network ancestry graph
COMPLIANCE.md          the TCEC declaration, point by point
RESULTS.md             the tables
results/
  eval_set.epd          the shared evaluation position set
  *.csv                 raw evaluations, one row per position
  scripts/              the scripts that produce them and compute rho
pipeline/
  generate/ annotate/ dataset/ train/ measure/    code, no data
manifests/ gen1/ gen2/ gen3/                       per-shard manifests
nets/                  luna_gen1.nnue, luna_gen2.nnue (+ .sha256)
checksums/ gen1/ gen2/                             dataset hashes
non_conforme/           gen0: what it is, why it doesn't count, isolated script
```

## How to reproduce a generation

1. `pipeline/generate/` — self-play (`run_selfplay_genN.sh`) + position
   extraction + manifest construction, driven by `generate_shards_genN.sh`
   (an arithmetic assert on pool sizing before it starts).
2. `pipeline/annotate/` — incremental, trailing annotation
   (`annotate_incremental_genN*.py`), global dedup via `global_seen.bin`,
   WDL correction for truncated games.
3. `pipeline/dataset/` — `build_training_dataset_genN.py` assembles
   train/val (split by game), `convert_to_binary.py` converts to a
   memory-mapped format for training.
4. `pipeline/train/` — `train.py`, with the three preflight numbers
   printed automatically before every run as a sanity check.
5. `pipeline/measure/` — the gate on the master before every new
   generation, static and search-based Spearman measurements for
   `RESULTS.md`.

The data itself (shards, assembled datasets, checkpoints) is not in this
repository — it lives on Oracle Cloud and an OCI bucket. This repository
holds the code to reproduce it and the measurements to verify it.

## Compliance rule

All training data from gen1 onward comes from the engine's own search
and/or evaluation — never from Stockfish, never from a third-party engine.
Full details, including why "Stockfish" still appears in the code (as an
offline measurement tool, never as a label source), in `COMPLIANCE.md`.
