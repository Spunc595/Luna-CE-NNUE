# Luna CE NNUE

Data provenance, training pipeline and results for the NNUE networks of
**Luna Chess Engine** — not to be confused with Thomas Mergener's *Luna*,
a different engine.

## Current shipped network

The network in Luna CE
[v4.0.0](https://github.com/Spunc595/Luna-Chess-Engine/releases/tag/v4.0.0)
(`resources/net.bin`, sha256
`ecd8a917fd8d6f1e900f64ec1721494178cd610ab5f02b4c91c0ca1950446940`): trained
by the author, with his own training pipeline, on public Leela Chess Zero
data (`phase-1` line, not the `gen1`/`gen2`/`gen3` line below). Measured in
the engine's own search against akimbo's network: **statistically
indistinguishable, +0.3 ± 10.7 Elo (95% CI, 2,000 games)** — parity, not a
win. Full provenance: `PROVENANCE.md`. Data source and license: `DATA.md`.
Result detail: `results/RESULTS_v4.0.0.md`. Traps hit along the way:
`LESSONS.md`.

**The network shipped in v4.0.0 comes from a separate line of work** (the
`phase-1` pipeline, see `results/`) from the fully self-play
`gen1`/`gen2`/`gen3` line described below, which is a different, ongoing
effort — nothing from that line has been shipped yet.

**Every label used to train these networks was produced by Luna's own search,
and every position comes from Luna's own self-play.** The one external
influence anywhere in the chain — Stockfish filtering gen1's opening pool, a
selection of starting positions and not a label — is documented, not hidden.
`LINEAGE.md` traces each network back to its ancestors, `COMPLIANCE.md`
states how each stage of the pipeline meets that claim, and `RESULTS.md` holds
the measurements — with the raw per-position data in `results/`, so every
number here can be recomputed.

This repository holds the history of *how* each network was made and measured.
The engine's source code lives in [its own repository](https://github.com/Spunc595/Luna-Chess-Engine).

## Documents

| File | Covers |
|---|---|
| `PROVENANCE.md` | v4.0.0 network: trainer, architecture, config, machine, quantisation gates |
| `DATA.md` | v4.0.0 training data: source and license, two levels (Lc0 games / Linrock's conversion) |
| `results/RESULTS_v4.0.0.md` | v4.0.0 network: match results table |
| `LESSONS.md` | Traps found during the phase-1 line, with evidence |
| `LINEAGE.md` | `gen1`/`gen2`/`gen3` line: ancestry of each network |
| `COMPLIANCE.md` | `gen1`/`gen2`/`gen3` line: how each stage meets the self-play-only claim |
| `RESULTS.md` | `gen1`/`gen2`/`gen3` line: measurements |

The numbers are not always flattering: the compliant network currently ranks
below `gen0` (trained on externally produced labels, kept only as a reference
point) and below the third-party *akimbo* network (used as a yardstick, never
to generate data). They are published anyway. A record that shows the
inconvenient numbers is worth more than a provenance claim nobody can check.
