# Luna CE NNUE

Data provenance, training pipeline and results for the NNUE networks of
**Luna Chess Engine** — not to be confused with Thomas Mergener's *Luna*,
a different engine.

**Every position and every label used to train these networks was produced by
Luna's own search.** No external engine contributed data at any point in the
chain. `LINEAGE.md` traces each network back to its ancestors, `COMPLIANCE.md`
states how each stage of the pipeline meets that claim, and `RESULTS.md` holds
the measurements — with the raw per-position data in `results/`, so every
number here can be recomputed.

This repository holds the history of *how* each network was made and measured.
The engine's source code lives in [its own repository](https://github.com/Spunc595/Luna-Chess-Engine).

The numbers are not always flattering: the compliant network currently ranks
below `gen0` (trained on externally produced labels, kept only as a reference
point) and below the third-party *akimbo* network (used as a yardstick, never
to generate data). They are published anyway. A record that shows the
inconvenient numbers is worth more than a provenance claim nobody can check.
