# Lambda sweep, Phase 1: the floor (2026-09-19)

Four runs at lambda = 0.7, everything as gen3 (binary dataset `gen3_train_bin` /
`gen3_val_bin`, batch 8192, lr 1e-3, cosine over 25 epochs, patience 6, split seed 42),
run one after the other on the Oracle machine (CPU, 4 torch threads) with the lichess bot
and the status-upload watchers stopped. Rule registered before any run:
`results/lambda_sweep_decision_rule.md` (commit `ff6d3c9`); code: commit `ff6d3c9`
(`train.py --train-seed`). Measurements: `pipeline/measure/sweep_measure.py`, engine binary
sha256 `f9edde89...` (the one of the gen2/gen3 diagnostic), 20,000 nodes. Only numbers are
published: the four checkpoints and networks stay on the server.

The seed varies the weight initialisation only (the loader does not shuffle, as in gen1-gen3).

## Results, one row per network (sha256 of the exported network in the row)

| run | seed | sha256 of `net.nnue` | identity gate | rho (static vs Stockfish) | ratio capture/quiet | min val loss (epoch) | epochs run |
|---|---|---|---|---|---|---|---|
| A1 | 101 | `a5580def88bb1b80ba4b08fbae14e8def55491f34513ecbf5f99aacfb740a66e` | 20/20 | 0.6932 | 1.6551 | 0.022296 (3) | 9 |
| B  | 202 | `a8b4ad4458ca789219313ab36e6b69f270a46eaa5f716254ac2f0fb3e9975cbc` | 20/20 | 0.7025 | 1.5852 | 0.022210 (3) | 9 |
| C  | 303 | `6ffa016023a8e0dcdfee4c4bf94880aff4da14efe37e335fd7de2a00a7d4f675` | 20/20 | 0.7035 | 1.3244 | 0.022161 (3) | 9 |
| A2 | 101 | `a5580def88bb1b80ba4b08fbae14e8def55491f34513ecbf5f99aacfb740a66e` | 20/20 | 0.6932 | 1.6551 | 0.022296 (3) | 9 |
| gen3 (published net, measured today, calibration only) | - | `82aa1bf0d4e0a4351d070f08b51c7ccbaa41f2c02a68ad3fbbbd1eb7e7320954` | 20/20 | 0.7005 | 1.3622 | 0.022381 (3), from its log | 9 |

Calibration: the published gen3 network measured today with the same procedure gives
rho 0.7005 and ratio 1.3622, the published values (0.7005; 1.362), so the measurement
procedure reproduces. Reference ratios of RESULTS.md 5.12: gen2 1.385, gen3 1.362.

## The floor

Defined in the rule as `max - min` over A1, B, C, separately for each quantity:

* rho: 0.7035 - 0.6932 = **0.0103**
* ratio: 1.6551 - 1.3244 = **0.3307**

## A1 against A2 (same seed)

**Identical.** The exported networks are byte-identical (same sha256), the best checkpoints
are byte-identical, and the training logs are identical in every column except the wall-clock
seconds (max difference of the training loss: 0.0). On this machine (CPU, 4 threads) the
training is deterministic given the seed.

## Continuation condition (stated before any comment)

"At least one of the four runs reproduces the published gen3 rho (0.7005) within the floor
itself", `|rho_run - 0.7005| <= 0.0103`: A1 0.0073, B 0.0020, C 0.0030, A2 0.0073.
**Satisfied**, by all four runs.

## What is not concluded

Lambda did not vary in this phase, and nothing about lambda is concluded here. Phase 2 is not
started; the rule for how its results are judged is still to be written as an amendment before
its first run.

Files: `results/lambda_sweep_phase1/` (training logs of the four runs, export logs, the
per-network diagnostic reports with the identity-gate line, and the timelines).
