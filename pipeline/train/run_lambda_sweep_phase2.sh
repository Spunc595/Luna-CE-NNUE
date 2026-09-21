#!/bin/bash
# Lambda sweep, Phase 2 (results/lambda_sweep_decision_rule.md, Amendments 1 and 2): six runs, one after the other,
# lambda in {1.0, 0.4, 0.0} x seeds {101, 202}, everything else as gen3. Data: the published gen3 feature arrays with the
# targets rebuilt per lambda (make_lambda_targets.py) under $S/data/lam_<lambda>/ (read-only here).
# Stops after the first anomaly (Amendment 1: "stop and report"): a run that ends after fewer than 3 epochs, a training
# process that exits with an error, or a network refused by the export gate. It never relaunches a run.
set -u
S=$HOME/scratch_sweep2
export PYTHONPATH=$S/repo/pipeline/train:$S/repo/pipeline/dataset
D=$HOME/gen3_classical/halfka_training          # only for the preflight TSV of the validation positions
cd $S
echo "phase2 start $(date -u +%FT%TZ) commit $(cat repo/COMMIT)" > timeline2.txt
for spec in 1.0:101 1.0:202 0.4:101 0.4:202 0.0:101 0.0:202; do
  lam=${spec%%:*}; seed=${spec##*:}
  name=L${lam}_s${seed}
  R=$S/run_$name
  mkdir -p $R
  echo "$name lambda=$lam seed=$seed start $(date -u +%FT%TZ)" >> timeline2.txt
  python3 -u repo/pipeline/train/train.py \
    --train $S/data/lam_$lam/gen3_train_bin --val $S/data/lam_$lam/gen3_val_bin --preflight-val $D/gen3_val.tsv \
    --format binary --epochs 25 --batch-size 8192 --lr 1e-3 --eval-lambda $lam --patience 6 \
    --train-seed $seed \
    --out $R/checkpoint.pt --log-csv $R/train_log.csv --best-out $R/checkpoint.best.pt \
    > $R/train.log 2>&1
  rc=$?
  epochs=$(( $(wc -l < $R/train_log.csv 2>/dev/null || echo 1) - 1 ))
  echo "$name train exit=$rc epochs=$epochs end $(date -u +%FT%TZ)" >> timeline2.txt
  if [ $rc -ne 0 ]; then echo "ANOMALY $name: training exit code $rc" >> timeline2.txt; touch anomaly; exit 1; fi
  python3 repo/pipeline/train/export.py --checkpoint $R/checkpoint.best.pt --out $R/net.nnue > $R/export.log 2>&1
  erc=$?
  echo "$name export exit=$erc $(sha256sum $R/net.nnue 2>/dev/null | cut -c1-64)" >> timeline2.txt
  if [ $erc -ne 0 ]; then echo "ANOMALY $name: export refused (exit $erc)" >> timeline2.txt; touch anomaly; exit 1; fi
  if [ $epochs -lt 3 ]; then echo "ANOMALY $name: only $epochs epoch(s) run" >> timeline2.txt; touch anomaly; exit 1; fi
done
echo "phase2 runs done $(date -u +%FT%TZ)" >> timeline2.txt
touch phase2_done
