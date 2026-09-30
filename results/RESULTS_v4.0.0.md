# Results: the v4.0.0 network (phase-1 line)

Covers the network shipped in Luna CE v4.0.0, trained by the author, with
his own training pipeline, on public Leela Chess Zero data (`DATA.md`). Not
the `gen1`/`gen2`/`gen3` self-play line — that line's numbers are in the
root `RESULTS.md`.

All matches below were run in Luna's own search (not static evaluation),
cutechess-cli, preamble-verified (TC, bounds, binaries' sha256 recorded
before trusting any result). Full records are the linked files.

| Measurement | Result | Conditions |
|---|---|---|
| First network (no king buckets) vs akimbo | −49.8 ± 10.9 Elo (2,000 games, 95% CI) | Material scale factor off on both sides; not shipped. `results/match_no_d3.md` |
| Output-scale correction (`SCALE=358` vs default 400), same no-bucket network | +15.9 ± 11.9 Elo | SPRT, 1,443 games, LOS 99.5%. Folded into the release. `results/sprt_scale358_result.md` |
| 4 king buckets vs the no-bucket network, both at `SCALE=358` | +36.9 ± 20.5 Elo | SPRT, 529 games. `results/bucket_experiment_part4_report.md` |
| Shipped network (buckets, `SCALE=358`) vs akimbo's own network | +0.3 ± 10.7 Elo (2,000 games, 95% CI, no losses on time) | Statistically indistinguishable — the interval runs roughly −10 to +11 Elo. `results/match_bucket_vs_akimbo.md` |

The last row is the release decision: **statistically indistinguishable**
from akimbo's network. Not "stronger," not "at least equal" — parity, from
a single training run, not a statistical population of runs.
