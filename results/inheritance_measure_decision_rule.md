# Inheritance measure — decision rule (registered before any correlation is computed)

Written and committed BEFORE the script that computes the correlations exists or is run;
the commit timestamp is the proof of ordering. Nothing below is edited after seeing numbers;
any later change is a new dated amendment at the end of this file. No training is involved:
everything is computed from networks that already exist.

## Why this measure, and what came before it

The lambda sweep, Phase 1 (`results/lambda_sweep_phase1.md`) measured the seed-to-seed floor
of the capture/quiet ratio of the static-vs-search gap: **0.3307** (1.6551, 1.5852, 1.3244 on
three identical runs). The difference the inheritance hypothesis was built on, gen2 (master)
1.385 against gen3 (student) 1.362, is **0.023**: fourteen times smaller than the noise. The
ratio of two medians therefore cannot measure inheritance, and the prediction registered for
Phase 2 in `results/lambda_sweep_decision_rule.md` cannot be checked with it.

This file registers a more direct and more stable measure, and, before it is used to design
generation 4 around it, a test of whether the inheritance exists at all.

## The measure

For every network `X` and every position `p` of the evaluation set (`results/eval_set.epd`,
the 2,000-position sample of RESULTS.md table 1), the **static error** is

    e_X(p) = sigmoid(K * search_X(p)) - sigmoid(K * static_X(p))          (signed)

with `K = ln(10)/400` (read from `pipeline/train/dataset.py`), `static_X` the `eval` of the
engine with network X, and `search_X` the 20,000-node search **with the same network X**,
1 thread, as in `pipeline/measure/diagnose_static_search_gap.py`. Each network is compared with
itself: `e_X` is the network's own blind spot, not a comparison between different networks.

The **inheritance** between a student S and a reference R is the correlation of the two error
vectors over the positions valid for both (the diagnostic drops positions with a mate score, so
the set differs slightly between networks: the join is by FEN, and `n` is reported):

    rho(S, R) = Spearman( e_S , e_R )

Spearman with average ranks for ties (the `spearman` of `diagnose_static_search_gap.py`) is the
primary measure and the one the decision is taken on. Pearson is reported as a secondary
figure and decides nothing.

## The control that makes it interpretable

Two networks can have correlated errors simply because both are static evaluators facing the
same positions: a tactically alive position is hard for anyone. A high correlation between
student and master does not by itself show that the student copied THAT master. So the same
correlation is computed against networks that are not the master of the student:

| reference | what it is |
|---|---|
| `gen2` | the real master: gen3 was labelled by gen2's search |
| `gen1` | an ancestor, not the master |
| `akimbo` | the embedded network of the engine, no relationship |

The students are the three Phase 1 runs **A1, B, C** (lambda 0.7, seeds 101, 202, 303; the same
recipe as gen3, different seed only). A2 is byte-identical to A1 and adds nothing. The published
gen3 network is also measured and reported against the same three references, as information; it
takes no part in the decision.

Networks and their identity: every network used is identified by the sha256 of its `.nnue`,
printed next to each result, and passes an identity gate before its errors are used. For the
students and for gen1 and gen2 that is the gate of the diagnostic (the first 20 positions,
`eval` with the network and with the embedded network must differ on all 20). For akimbo, which
IS the embedded network, the gate is the mirror image: its `eval` must equal the embedded
engine's on all 20 positions and differ from gen3's on all 20.

## The floor, at no cost

A1, B and C have the same lambda and differ only in the seed, so `rho(A1, gen2)`,
`rho(B, gen2)`, `rho(C, gen2)` are three measurements of the same quantity. The floor of this
measure is

    floor = max - min   over  rho(A1, gen2), rho(B, gen2), rho(C, gen2)

Also reported, not used in the decision: `rho(A1, B)`, `rho(A1, C)` (siblings: same master, same
lambda), which show how high this correlation can go when the inheritance is certainly there,
and serve as a yardstick for the other numbers.

## The decision

**The inheritance is sustained** only if, for each of the three students S in {A1, B, C}:

    rho(S, gen2) - rho(S, gen1)   >  floor       and
    rho(S, gen2) - rho(S, akimbo) >  floor

(strict inequalities on unrounded values; all six must hold).

**If it is not sustained**, the conclusion is that this measure reads the difficulty of the
position and not the kinship, and **the whole inheritance line is closed**: a fourth measure is
not sought to make it come out. That is written down and we move on, and Phase 2 stays judged on
rho (static Spearman against Stockfish), where the floor is 0.0103 and the question "which
lambda" has an answer regardless.

**If it is sustained**, that shows the inheritance exists as measured here and nothing more: it
does not by itself authorize any filter or any change of generation 4, and the Phase 2
prediction would have to be restated in terms of this measure, with this floor, in an amendment
committed before any Phase 2 run.

## Correction of RESULTS.md 5.12

Independently of the outcome, the sentence of RESULTS.md 5.12 that reads the closeness of the
gen2 and gen3 ratios as evidence that the profile is a property of the position class is
corrected (the measurements stay; the inference changes): the Phase 1 floor of the ratio (0.3307)
against the gen2-gen3 difference (0.023), and the bootstrap intervals already published in 5.13
(1.385 [1.223; 1.597] and 1.362 [1.169; 1.565]), show the two generations cannot be told apart on
that ratio. What is kept: the **direction** is robust (capture-class gap above quiet-class gap in
every run measured, ratio well above 1), so "captures are harder for a static evaluator" remains
a property of the position class.
