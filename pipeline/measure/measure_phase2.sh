#!/bin/bash
# Phase 2 measurements, after the six runs (nothing else running): per network the identity gate 20/20 (inside the
# diagnostic), the per-position gap CSV (static vs 20,000-node search) and the static-rho CSV against Stockfish.
set -u
S=$HOME/scratch_sweep2
R=$S/repo
ENG=$HOME/diagnostica_gap/gen3/luna            # the engine binary of the earlier diagnostics (same for every net)
EMB=$HOME/diagnostica_gap/embedded/luna         # the same binary WITHOUT a luna.nnue next to it
mkdir -p $S/meas && cd $S/meas
echo "engine sha256 $(sha256sum $ENG | cut -c1-64)" > meas_timeline.txt
for run in L1.0_s101 L1.0_s202 L0.4_s101 L0.4_s202 L0.0_s101 L0.0_s202; do
  d=$S/meas/$run; mkdir -p $d
  cp $ENG $d/luna; cp $S/run_$run/net.nnue $d/luna.nnue
  echo "$run net sha256 $(sha256sum $d/luna.nnue | cut -c1-64) start $(date -u +%T)" >> meas_timeline.txt
  python3 $R/pipeline/measure/diagnose_static_search_gap.py --eval-set $R/results/eval_set.epd --engine $d/luna \
      --embedded-engine $EMB --label $run --out $d/${run}_gap.csv > $d/${run}_gap_report.txt 2>&1
  python3 $R/results/scripts/measure_static_vs_stockfish.py --eval-set $R/results/eval_set.epd --engine $d/luna \
      --label $run --out $d/${run}_vs_stockfish.csv > $d/${run}_static.txt 2>&1
  echo "$run done $(date -u +%T): $(grep -m1 'identity gate' $d/${run}_gap_report.txt)" >> meas_timeline.txt
done
touch $S/meas_done
