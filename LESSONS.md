# Lessons from the phase-1 / v4.0.0 training line

One entry per trap, with the evidence that surfaced it. Distilled from this
project's own working notes (`PROTOCOLLO.md`, phase reports); dates are when
each was found, not when it was fixed.

**Spearman saturates above rho ~0.90.** Measured in both directions: a
search-side change accepted by SPRT at +44.8 Elo showed a Spearman
difference statistically indistinguishable from zero ([-0.0015, +0.0005]);
a network configuration rejected by SPRT at about -54 Elo showed a Spearman
difference of only -0.0011 (0.9026 vs 0.9036). Above ~0.90, Spearman is an
entry filter, not a shipping gate — SPRT decides. A Spearman difference
below measurement resolution can still be worth tens of Elo.

**bullet's lambda is the WDL (game-result) fraction, not the evaluation
weight** — the opposite convention from this project's own earlier
terminology (`nnue_phase3_report.md`, "Lambda direction"). Luna's own
`lambda` (weight of the search evaluation) = 1 - bullet's. Confusing the two
silently inverts a ramp's intent.

**bullet's mirroring direction was initially assumed, not read from the
source, and was backwards.** A first implementation of the horizontal-mirror
logic went the opposite way from bullet's actual `Chess768hm`
(`chess768hm.rs`), producing systematic evaluation errors up to 1,794 cp
before the real source was read and the direction corrected
(`nnue_phase3_report.md`).

**bullet does not shuffle training data by itself, and the loader reads
sequentially** — "distinct positions" in a data file is not the same claim
as "randomly ordered." Shuffling (via `bullet-utils shuffle` or an
equivalent tool) is a separate, explicit step; skipping it was measured to
cost a small but real amount of quality (shuffled runs consistently ahead of
unshuffled ones on the same data, `nnue_phase3_report.md`).

**A reimplementation is validated against the real code, never against a
second reimplementation.** Two independent transcriptions of the same
misunderstanding can agree with each other and both be wrong — that is not
a check, it is two errors hiding one another. Case (2026-09-28): a first
Python transcription of bullet's bucket layout had 25,227/35,278 rows wrong.
Fixed by writing a Rust probe that calls bullet's own
`ChessBoard::from_str`/`ChessBucketsMirrored::map_features` directly, then
correcting the Python against that probe's output (0/604 mismatches) before
comparing to Luna's own code (0/35,278 mismatches).

**A rescaling coefficient alone doesn't say how much of a difference is
scale.** On a scale comparison (line through the origin), R² and the
residual standard deviation say whether two networks differ mostly by scale
(high R², small residual) or by scale plus real disagreement (lower R²,
larger residual). Case (2026-09-27): coefficient 1.1164, R²=0.969, residual
149 cp (~20% of signal std) — the `SCALE` correction was still justified,
but the measured SPRT gain from it (+15.9 Elo) was not expected to close the
full gap, and didn't.

**The R²/residual self-consistency identity is itself a gate.**
`resid_std ≈ sqrt(1-R²) * RMS(y)` must hold when both numbers come from the
same pair of vectors; if it doesn't, the two "comparable" measurements were
taken on different populations. Case (2026-09-29): an apparently-good
R²=0.9815 for the bucket network, compared against R²=0.969 for the
no-bucket network measured the day before, hid the fact that the bucket
measurement had used a different position-sampling method (random self-play
walks instead of the same `eval_set.epd` seed-7 set) — caught because the
implied total-eval standard deviation for the *same* reference binary
differed by nearly 2x between the two measurements, which is impossible for
one binary unless the position populations differ.

**Centipawn-denominated engine constants (`SCALE`, RFP/futility margins,
aspiration window, delta margin, the material factor) belong to the
network's evaluation configuration, not to the engine.** They are calibrated
against one specific network's output distribution. A new network isn't
safely measurable in games until its scale has been compared to the network
it replaces — the slope between the two networks' static evals on the same
position set, with any such correction disabled on both sides so the two
variables aren't mixed. Spearman is blind to this by construction (invariant
to monotone transforms); it is not a gate for this question at any rho.

**The match preamble is the gate, not a reminder — read it every time, even
one minute after writing the script.** Case (2026-09-27): a queue script
copy-pasted the wrong SPRT-bounds variant (`elo0=-5 elo1=5` instead of the
intended `elo0=0 elo1=10`); reading the preamble immediately after launch
caught it after 2 games, not after hours.

**Kill the worker's real PID, never the wrapper that launched it — and
verify nothing survives.** Case (2026-09-28): killing a queue script and
its training process "in the same breath" killed only the wrapper; bash
does not kill foreground children when it dies by signal, it orphans them.
The training process was found still alive by a follow-up `pgrep`.

**`set -e` turns an informative nonzero exit into a silent abort.** A
command whose nonzero exit is an expected, meaningful outcome (`diff`,
`cmp`, `grep -c`, `pgrep`, `test`, `sha256sum -c`, `git diff --quiet`) must
sit where `errexit` doesn't apply (an `if`/`while`/`until` condition, after
`!`, non-final in `&&`/`||`), with its status captured explicitly. Case
(2026-09-27): a build script with `set -e` and `n=$(grep -c differ file)`
terminated silently, before the `if` meant to read `n`, on exactly the
expected-difference case.
