# Lambda sweep, Phase 2 (2026-09-21)

Six runs, lambda in {1.0, 0.4, 0.0} x seeds {101, 202}, plus A1 and B of Phase 1 as the lambda 0.7 point (same
seeds). Everything as in Phase 1 and gen3 except the targets, rebuilt per lambda (Amendment 2 of
`results/lambda_sweep_decision_rule.md`: the binary dataset bakes lambda; `make_lambda_targets.py`, validated at 0.7,
byte-identical to the published targets). Rule: Amendment 1 (`28849bd`) and Amendment 2 (`c2d4c9b`), tooling
(`02cfa9e`), all committed before the first run. Oracle, CPU, 4 threads, one run after the other, the lichess bot and
the upload watchers stopped (the two idle annotators were left running, at 0% CPU). The runs took 25-27 minutes
(1.0), 17-19 (0.4, 0.0). No anomaly: every run ended by the early stop, with 8-13 epochs, and every export passed the
gates. Only numbers are published; checkpoints and networks stay on the server.

## Verdict under the registered rule (stated before any comment)

* **Prediction A** (rho(e, gen2) at lambda 0.0 below the value at 1.0 by more than 3 x 0.0070 = 0.021):
  **MET.** `0.5474 - 0.4594 = +0.0880`.
* **Prediction B** (excursion of rho(e, akimbo) over the four lambdas below 0.021): **NOT MET.**
  Excursion `0.4022 - 0.3545 = 0.0477`.
* **Reading of the combination: A yes, B no** -> lowering lambda makes the network noisier and less in agreement with
  **everybody**; **not demonstrated** that the inheritance is specific to the master.
* **Lambda of generation 4** (static rho): the spread of the four means is 0.0485 (> 0.0103, so not flat); the best
  lambda is 1.0 (0.7037) but its advantage over 0.7 (0.6979) is +0.0058, **not above 0.0103**: **generation 4 stays
  at lambda 0.7.**

## Per network (sha256 next to every row; identity gate 20/20 for all eight)

| run | lambda | seed | static rho | rho(e, gen2) | rho(e, gen1) | rho(e, akimbo) | min val loss (epoch) | epochs | sha256 of the `.nnue` |
|---|---|---|---|---|---|---|---|---|---|
| L1.0_s101 | 1.0 | 101 | 0.7046 | 0.5533 | 0.4722 | 0.3772 | 0.012597 (6) | 12 | `72175311541cce866dfce2cf763b55dad250a168f7c040187d8932bbdecc720b` |
| L1.0_s202 | 1.0 | 202 | 0.7027 | 0.5414 | 0.4832 | 0.3950 | 0.012566 (7) | 13 | `e82f93e6ae8c4dd72eacdbf485d7d126ea668aef7983e6daf4269c106db83493` |
| A1 | 0.7 | 101 | 0.6932 | 0.5485 | 0.4822 | 0.4015 | 0.022296 (3) | 9 | `a5580def88bb1b80ba4b08fbae14e8def55491f34513ecbf5f99aacfb740a66e` |
| B | 0.7 | 202 | 0.7025 | 0.5433 | 0.4757 | 0.4028 | 0.022210 (3) | 9 | `a8b4ad4458ca789219313ab36e6b69f270a46eaa5f716254ac2f0fb3e9975cbc` |
| L0.4_s101 | 0.4 | 101 | 0.6727 | 0.4998 | 0.4162 | 0.3677 | 0.048383 (3) | 9 | `9db4ab53b76ab389bbcee30d294d1d5df9b664064b5f0e10b528e4019205f2cd` |
| L0.4_s202 | 0.4 | 202 | 0.6839 | 0.5434 | 0.4467 | 0.3573 | 0.047769 (2) | 8 | `315e188f896a7bf43fc6c602485688ac5f171f9d9781cc484db1141fc8b497de` |
| L0.0_s101 | 0.0 | 101 | 0.6513 | 0.4595 | 0.4172 | 0.3646 | 0.106014 (2) | 8 | `adfe23a56220319f58cc05891de29c400aed10109b9b9437aaba094c21a2ee1a` |
| L0.0_s202 | 0.0 | 202 | 0.6591 | 0.4593 | 0.4347 | 0.3443 | 0.106401 (2) | 8 | `77ea4c16f5b3890261fc120f6d1ec434136af39432138400bd1bd2c10107fbd7` |

Per-lambda means (two seeds each):

| lambda | static rho | rho(e, gen2) | rho(e, gen1) | rho(e, akimbo) |
|---|---|---|---|---|
| 1.0 | 0.7037 | 0.5474 | 0.4777 | 0.3861 |
| 0.7 | 0.6979 | 0.5459 | 0.4789 | 0.4022 |
| 0.4 | 0.6783 | 0.5216 | 0.4315 | 0.3625 |
| 0.0 | 0.6552 | 0.4594 | 0.4259 | 0.3545 |

Monotone over the four points (reported, not required): rho(e, gen2) 0.5474 > 0.5459 > 0.5216 > 0.4594, yes; static rho
0.7037 > 0.6979 > 0.6783 > 0.6552, yes; rho(e, akimbo) is not monotone (the 0.7 point is the highest).

## Preflight of every lambda (validation positions, before any epoch)

Validation losses are not comparable between lambdas (they measure different targets); each is read against its own
baseline. Expected and confirmed: the target variance and the material-only MSE both grow as lambda falls, and the
untrained network sits about 1% above the variance in every case (the targets are loaded right).

| lambda | target variance | MSE of material alone | MSE untrained (per seed) | best val loss of the runs | best / material |
|---|---|---|---|---|---|
| 1.0 | 0.120380 | 0.027849 | 0.121853, 0.122681 | 0.012566-0.012597 | 0.45 |
| 0.7 | 0.128605 | 0.035448 | 0.129986, 0.130698 (A1, B) | 0.022210-0.022296 | 0.63 |
| 0.4 | 0.152365 | 0.058596 | 0.153669, 0.154264 | 0.047769-0.048383 | 0.82 |
| 0.0 | 0.208211 | 0.113649 | 0.209434, 0.209874 | 0.106014-0.106401 | 0.93 |

At lambda 0.0 (game result alone, targets 0 / 0.5 / 1) the network never gets far below the material baseline (0.106 against
0.114): the minimum is at epoch 2 and the validation loss then rises (0.106 -> 0.125 by epoch 8) while the training loss
falls: it memorises the results of the games. At 0.4 the same, with the minimum at epoch 2-3. At 1.0 the minimum is at
epoch 6-7. That is an outcome to report, not a fault.

## What the numbers do not say, and what the seeds do

* The registered floors (static rho 0.0103; rho(e, gen2) 0.0070) were measured at lambda 0.7 with three seeds. With two
  seeds at the other lambdas the scatter between seeds is sometimes larger: rho(e, gen2) 0.5533 vs 0.5414 at 1.0 (0.012),
  0.4998 vs 0.5434 at 0.4 (**0.044**), 0.4595 vs 0.4593 at 0.0; rho(e, akimbo) 0.3772 vs 0.3950 at 1.0 (0.018), 0.3646 vs
  0.3443 at 0.0 (0.020). The floor measured at 0.7 may understate the seed scatter elsewhere. The registered comparisons
  are decided on means of two seeds against the registered thresholds, as written; this scatter is the caveat on how
  hard each mean can be leaned on.
* Post hoc, NOT part of the rule and deciding nothing: all three references fall as lambda falls (gen1 0.4777 -> 0.4259,
  akimbo 0.3861 -> 0.3545, gen2 0.5474 -> 0.4594), gen2 the most. The gap rho(gen2) - rho(akimbo) is 0.161, 0.144, 0.159,
  0.105 at lambda 1.0, 0.7, 0.4, 0.0.
* Static rho against Stockfish is 0.7037 at lambda 1.0 and 0.6979 at 0.7 (a difference inside the floor of 0.0103) and
  falls clearly below 0.7: 0.6783 at 0.4 (-0.0196), 0.6552 at 0.0 (-0.0427). Within the range measured, more weight on
  the master's evaluation does not lower rho, less weight does.

Nothing here produces generation 4 or changes a filter or the pipeline. Files: `results/lambda_sweep_phase2/` (per-run
CSVs, logs, preflight and epoch summaries, the manifest `runs.json`, `phase2_report.txt`, `phase2_result.json`).
