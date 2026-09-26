# SPRT of the first self-trained net: pre-registration (written 2026-09-26, BEFORE the match starts)

Net: `step_8ep.nnue`, sha256 `43546e8eff855fb0dda5c028b0e66507015f774a23037bfbf72dff3d298339e4`, 6,297,664 bytes (checked on both sides).
1.0 G distinct S2 positions x 8 epochs = 8.0 G samples, 19 h 43 m on Oracle. Static Spearman on the SF18 set 0.9026 [0.9017, 0.9035] vs
embedded 0.9036: -0.0011 [-0.0013, -0.0008]. Static correlation is not a prediction of playing strength (D1: null Spearman, SPRT +44.8 Elo).

## Fixed before the run
```
A (patch) : v3.1.7 (tag, b93f9d8) with resources/net.bin replaced by step_8ep.nnue   (engines/net_patch)
B (base)  : v3.1.7 (tag, b93f9d8) unchanged                                            (engines/net_base)
SPRT      : elo0 = -5, elo1 = +5, alpha = beta = 0.05
cap       : 8,000 games (4,000 rounds)
tc        : 20+0.2, Hash 64, Threads 1, concurrency 2, no book, 8moves_v3.pgn, adjudication as in every earlier match
validity  : one game lost on time invalidates the match (investigate, do not just rerun)
futility  : from 2,000 games, stop if Elo + 95% CI half-width < 5 (sprt_stop_rule2.sh); Elo and CI recorded at the stop
bot       : OFF for the whole match (control match 2026-09-21 ran with no bot activity: none between 13:36 and 17:00 UTC); restarted at the end
```
Why -5/+5 and not 0/+10: the question is "can we switch to a net of our own without losing strength?", and parity is already a reason to ship
(with a net of our own every later net is measured against the previous one, not against a frozen external target). Same width as
[0, +10], so the same cost in games. Moving the bar on the very test one wants to pass is only legitimate because the reason is written
here first; going back to [0, +10] after a failure to "retry" would be cheating. (If [0, +10] is wanted instead, only elo0/elo1 change.)

## Gates already passed (numbers)
- SIMD: max|output weight| = **127** -> 255 x 127 = 32,385 <= 32,767 (pass, margin 382; 52 of 2,048 output weights are at >= 126, i.e. at
  bullet's AdamW clip of about +-1.98 x 64). References: gen1 6, gen2 6, gen3 4, pilot 36. Mutation check: an output weight of 2.5 (160) is refused.
- Accumulator: worst case +7,220 / -10,201 vs +-32,767 (margins 25,547 / 22,567); max|feature weight| 462, max|bias| 225. Mutation check:
  32 weights of 7.0 in one column are refused (57,068).
- Converter round-trip against the independent reference: 0 differences on 2,000 positions (and the round-trip is inside the converter).
- Size 6,297,664 bytes; sha256 identical on PC and Oracle.
- Swap gates: `resources/net.bin` differs (base b3faa88a..., patch 43546e8e...); the two trees are identical apart from net.bin; engine
  binaries differ (base `f817914f...` = the bot binary built from the tag on 2026-09-25, patch `3dd87686...`); kiwipete static eval
  base -294 cp vs patch -251 cp, depth 12 base cp -123 (359,149 nodes) vs patch cp -269 (269,528 nodes): the swap took.

## Decision rules (not renegotiated after the run)
- **H1 accepted**: ship: the net becomes `resources/net.bin` on a new commit, the notes say what it is (first net trained entirely on our data,
  1 G x 8 epochs, Spearman 0.9026, SPRT at [-5, +5]); only then re-measure D3 (its factor was tuned on akimbo's net).
- **H0 accepted**: statically equal, weaker in play: Spearman stops being the gate and becomes an entry filter; the next long run increases
  the DISTINCT positions (not the epochs): three points (0.25 G 0.8870, 1 G 1 epoch 0.8952, 1 G 8 epochs 0.9026) say fresh data bought more per
  sample than repetition.
- **Futility stop**: counts as rejected for shipping; Elo and SE at the stop are recorded (a near-zero Elo with a narrow SE is a measured parity).
- **Loss on time**: match invalid, cause investigated before any rerun.

## Prediction, declared now
With -0.0011 static I expect a result between -5 and +5 Elo (parity likely). On [-5, +5] I expect acceptance; on [0, +10] I would give
it 25-30%. If wrong, it goes in the report.

## Started 2026-09-26 18:36 UTC (A = patch, B = base, seed 1207) - note added after the start, parameters unchanged
Observed rate at 20+0.2 with concurrency 2: **28 games in 13 minutes = about 129 games/hour**, half of the ~267/hour used for the time
estimate (that figure belongs to 10+0.1). At this rate the 8,000-game cap is about **62 hours**, not ~30; an early stop (LLR bound or the
futility rule from 2,000 games = about 15.5 h) is where the match is expected to end. Nothing was changed: bounds, tc, cap and rules stand as
registered above. Early counts (28 games, 4-9-15) mean nothing at this size.

## AMENDMENT 1 (decided 2026-09-26 at 95 games of the first run; a dated amendment, the text above is NOT rewritten): time control 20+0.2 -> 10+0.1
Everything else stays as registered: cap 8,000 games, elo0 = -5, elo1 = +5, alpha = beta = 0.05, futility rule, one game lost on time
invalidates the match, base v3.1.7 unchanged, bot off, concurrency 2, no book, same openings, same A/B engines (same binaries).
Only the TC changes. The 95 games played at 20+0.2 (Elo about -37, draw ratio 0.60) are kept in `results/sprt_net8ep_on_v3.1.7/` and are
NOT used in the new match or in the verdict.

**Reason (validity, found by measuring, before the data exist):** the TC 20+0.2 was taken from Block 6, the fixed-length match against
v3.1.6, and not from the SPRT campaign, which runs entirely at 10+0.1 (D3, D4, G2b, G5, control: all 10+0.1 at 250-257 games/hour with
`concurrency 2`). It was a transfer of a parameter between contexts, not a choice. It is corrected before the measurement has begun.
Three independent arguments in the same direction: (1) working point: Luna plays lichess and MCEC rapid games, 10+0.1 is closer to
its real use; (2) comparability: at 10+0.1 the Elo of this net can be lined up with D3's +44.8 and the other patches, at 20+0.2 it cannot;
(3) resolution per Oracle hour: 10+0.1 gives 250 games/h (draw ratio ~0.555, SE after one hour ~15.2 Elo), 20+0.2 gives ~120 games/h (higher
draw ratio, SE after one hour ~20.0 Elo): the extra draws of the long TC do not repay the halved rate.
Expected time to the cap: about 32 hours instead of about 62.

**On the record: the difference between two kinds of reason.** "It takes too long" is a reason of convenience and is refused. "The registered
parameter is not the one of the campaign" is a reason of validity, found by measuring; the first is never enough, the second is
enough, and only before the data exist.
Execution log (filled in as it happens): see below.

### Execution log of Amendment 1 (2026-09-26)
- **Authorization:** Daniele authorised terminating the `cutechess-cli` process of the 20+0.2 match and nothing else (document
  "fermare-e-ripartire"). An earlier attempt at 19:3x UTC to stop it was refused by the permission system and was not worked around.
- **Before the kill (Part 0):** `bash -n` passed on `sprt_match5.sh` and `queue_net2.sh`. `sprt_match5.sh` had not run and did **not** log the
  values that matter (only `params.txt`/`header.txt` after the fact), so it was rewritten before the kill (old version kept as
  `sprt_match5.sh.v0-before-preamble`): TC, bounds, cap, concurrency, seed, the two binary paths with sha256, the results name, the literal
  command line and the load / number of luna processes are written as the first lines of `cutechess.log` (and `preamble.txt`) from the same
  variables that build the command. It also refuses an existing results directory and an engine directory with a `luna.nnue`. A dry run with a stub in
  place of cutechess (`results/dryrun_preamble_only_20260926`, left in place, not a match) confirmed the preamble.
- **Queue order (Part 1), read before the kill:** `queue_net2.sh` waits for the old match to end and never stops it; refuses to start if the old
  match ended by itself (>= 8,000 games or an SPRT bound line); then **stops the bot, and only when no `luna` process exists after the stop does it
  break out of the loop** (stop -> verify zero engine processes -> start); the match starts after that; results go to `sprt_net8ep_tc10_on_v3.1.7`
  (and `sprt_match5.sh` refuses an existing directory). Order was right, not changed. One weakness noted, not changed (the queue was already running
  and modifying a running script is what we avoid): if the wait loop ran out its 5,000 iterations (about 4 h) it would go on anyway; and the queue does not
  check the load average (the preamble records it).
- **Snapshot (Part 2), 20:43:58 UTC:** started 18:36:00 UTC; 268 games completed at the snapshot, 269 at the end; A (net) +44 =153 -72 (score 0.4480,
  Elo about -36.3, draw ratio 0.569, SPRT LLR -1.89 of bounds +-2.94, not crossed); **games lost on time: 0**. **These 269 games are discarded, not used
  in the verdict.** Reason: the amendment (TC not that of the campaign), decided at 95 games (Elo then about -37, i.e. in the same direction the data
  had at the kill): the decision was taken before the data could matter and its reason is not the data, but the record says the discarded games leaned
  negative so nobody has to wonder. Directory renamed (moved, nothing deleted) to
  `results/sprt_net8ep_on_v3.1.7_tc20_ABANDONED_amendment1_269games` after its stop-rule watchdog had exited on its own.
- **The kill (Part 3):** 20:44:17 UTC. `pgrep -a -x cutechess-cli` returned exactly one PID, 2212624, whose command line had `tc=20+0.2`;
  `kill -TERM 2212624` (explicit PID). It was gone within 12 s, no escalation needed.
- **Orphans (Part 4):** after the kill no `luna` process from the old match existed (the four `luna` processes present 12 s later all started at
  20:44:23 and have cwd `engines/net_patch` / `engines/net_base` of the NEW match). The queue's guard (`pgrep -x luna` = 0 after the bot stop) was satisfied by
  itself; the preamble records "luna processes running: 0" and load average 1.93 (a trailing average from the old match). Note: the queue started the new
  match 3 s after the kill, so there was no window for a manual load check before the start; the guard is the process count.
- **Restart (Part 5):** new match started 20:44:23 UTC (queue log 20:44:20). The bot: the old queue's exit restarts it, the new queue stopped it again
  within the same second (no game was running); `luna-bot` is inactive during the match. Preamble as written by the script:
  `TC 10+0.1; elo0=-5 elo1=5 alpha=0.05 beta=0.05; cap 8000 games (4000 rounds x 2); concurrency 2; seed 1207; A = engines/net_patch sha256 3dd876860d206a06...87f160;
  B = engines/net_base sha256 f817914f552cfbe7...36d38; results sprt_net8ep_tc10_on_v3.1.7`; the running `cutechess-cli` command line shows `tc=10+0.1`.
  All values are the expected ones.
- **First rate measure:** pending (to be entered here after 30 minutes; expected 240-260 games/hour, ~120 would mean the TC did not change).
- **First rate measure (21:15:06 UTC, 30 min 43 s after the start):** 118 games completed = **230 games/hour**, zero games lost on time, bot inactive,
  load average 2.00. The TC did change (the failure case was ~120/h). It is slightly under the 240-260 window expected from the earlier matches;
  the first half hour includes engine start-up and the ratio of long-to-short games is not yet settled, so it is recorded as observed and re-read
  from the log later. Score at 118 games 21-36-61 (Elo about -44): meaningless at this size, noted only because the previous half-hour showed the same sign.
