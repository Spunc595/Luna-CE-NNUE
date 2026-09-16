# Lineage

Luna's NNUE is bootstrapped generation by generation: each net becomes the
self-play evaluator and annotation master for the next generation's data.
This document is the answer to the one question that actually matters —
**what does the presented net descend from** — because conformance is a
property of the whole chain: one link touched by an external label source
contaminates everything downstream.

As of this writing (2026-09-16), **gen2 remains the current presentation
candidate**, by its own pre-committed rule: gen3 completed and was
measured (ρ 0.7005 static vs Stockfish), but that result landed **below**
the pre-registered 0.73-0.76 interval (`RESULTS.md` 5.7) that was the
condition for gen3 to replace gen2. The rule was written down before the
result existed specifically so this wouldn't become a judgment call after
the fact — gen3 is documented below as a complete, measured generation,
not as the new candidate.

```
classical eval  (no external source)
      │   self-play + annotation via Luna's own SEARCH
      ▼
    gen1   nets/luna_gen1.nnue   engine 076defc (labels) / b0cfb937 (self-play)   ρ 0.5874
      ▼
    gen2   nets/luna_gen2.nnue   engine 076defc (labels and self-play)            ρ 0.6790   ← current candidate
      ▼
    gen3   nets/luna_gen3.nnue   engine 076defc (labels and self-play)            ρ 0.7005   (measured, did not clear the bar to replace gen2)

separate branch, NOT an ancestor of any presented network:
    external labels (Stockfish) ──► gen0   ρ 0.7850   [NON-COMPLIANT]
```

**The presented network does not have gen0 among its ancestors.** gen0
exists only as a comparison reference (see table 1 in `RESULTS.md`) and
did not contribute any training data to gen1 or later networks — it
predates the TCEC rule applied from gen1 onward within this project
(details in `non_conforme/README.md`).

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

Complete and measured. **Not the presentation candidate** — see the note
at the top of this document: its ρ (0.7005) landed below the
pre-registered 0.73-0.76 interval that was the condition for replacing
gen2.

| Field | Value |
|---|---|
| Network | `nets/luna_gen3.nnue` (`sha256`: see `nets/luna_gen3.nnue.sha256`) |
| Self-play and annotation master | gen2 network, in search |
| Engine commit | `076defcb93d4a1dc834d4ecd5132f45ba9a311d2` (self-play and annotation, same commit from the start — no divergence) |
| Self-play nodes | 3,000 |
| Annotation nodes | 20,000 (master gate: ρ 0.8537/0.8760/0.8887 at 10k/20k/50k, above the gen2 master's 0.8072/0.8285/0.8413) |
| Machine | Oracle, sole machine start to finish (method rule fixed after the gen2 incident) |
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
