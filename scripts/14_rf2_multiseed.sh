#!/bin/bash
# 14_rf2_multiseed.sh -- re-score candidates with multiple RF2 seeds.
#
# WHY THIS EXISTS
# ---------------
# RF2 is stochastic, and on this system the spread is large enough to decide
# pass/fail. Same sequence, same target, same 10 recycles, five runs:
#
#   design                 noseed-1  noseed-2  seed101  seed202   spread
#   E1_b007_3_dldesign_9       4.26     16.21     4.03     5.35    12.18
#   E1_b008_9_dldesign_13      4.42     14.76    14.83     3.95    10.88
#   E1_b002_4_dldesign_8       4.90     13.17    13.68    14.82     9.92
#   E1_b000_3_dldesign_11      6.82     13.79     7.31    12.62     6.97
#   E1_b010_6_dldesign_0      13.97     14.12    13.21    14.51     1.30
#
# Four of five straddle the <10 threshold. A single-sample `interaction_pae < 10`
# gate is close to a coin flip for anything near the boundary, so the 58 "survivors"
# and the selected 20 are substantially a seed lottery. Note the last row: a
# consistently-bad design stays bad, so the metric is not pure noise -- it just needs
# averaging. This is PIPELINE.md s3 rule 1 (rho +0.239 at 1 sample vs +0.846 at 5).
#
# Scope deliberately includes designs that FAILED the pae gate on their single roll:
# those are exactly the ones a bad roll may have wrongly killed.
#
# Resumable: RF2 --cautious (default) skips outputs that already exist, so re-running
# this script continues where it stopped.
#
# Usage: bash scripts/14_rf2_multiseed.sh [N_SEEDS]

set -uo pipefail
source /mnt/comp5data/bd-il4r/env.sh
REPO="${REPO:-/home/HarjasG/tnf-track3/bd-il4ra-pipeline}"
NSEEDS="${1:-5}"
SEEDS=(1001 2002 3003 4004 5005 6006 7007 8008)
OUT="$BDIL4R/out/multiseed"
LOGDIR="$BDIL4R/logs/multiseed"
MIN_ROOT_GB=10
mkdir -p "$OUT/in" "$LOGDIR"

# ---- assemble the input set -------------------------------------------------
~/miniforge3/bin/conda run -n boltz python "$REPO/scripts/collect_rescore_inputs.py" \
  "$REPO/candidates.tsv" "$OUT/in" || { echo "FATAL: input collection failed"; exit 1; }
N=$(ls "$OUT"/in/*.pdb 2>/dev/null | wc -l)
[ "$N" -gt 0 ] || { echo "FATAL: no inputs collected"; exit 1; }

echo "=============================================================="
echo "RF2 MULTI-SEED RE-SCORE   started $(date -u +%FT%TZ)"
echo "designs: $N   seeds: $NSEEDS   est GPU: $(python3 -c "print(f'{$N*$NSEEDS*24.1/3600:.2f} h')")"
echo "=============================================================="

cd "$BDIL4R/rfantibody"
for ((i=0; i<NSEEDS; i++)); do
  S=${SEEDS[$i]}
  FREE=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
  [ "$FREE" -lt "$MIN_ROOT_GB" ] && { echo "ABORT: root free ${FREE}G"; exit 2; }

  D="$OUT/seed_$S"
  DONE=$(ls "$D"/*.pdb 2>/dev/null | wc -l)
  if [ "$DONE" -ge "$N" ]; then echo "[$(date -u +%T)] seed $S already complete, skipping"; continue; fi
  mkdir -p "$D"
  echo "[$(date -u +%T)] seed $S  ($DONE/$N already done)"
  T0=$(date +%s)
  uv run rf2 -i "$OUT/in" -o "$D" -r 10 --hotspot-show-prop 0.1 --seed "$S" \
    > "$LOGDIR/seed_$S.log" 2>&1
  T1=$(date +%s)
  echo "[$(date -u +%T)] seed $S done: $(ls "$D"/*.pdb 2>/dev/null | wc -l)/$N in $((T1-T0))s"
done

echo "--- aggregating ---"
~/miniforge3/bin/conda run -n boltz python "$REPO/scripts/aggregate_multiseed.py" \
  "$OUT" "$REPO/candidates.tsv" | tee "$LOGDIR/aggregate.log"

echo "=============================================================="
echo "MULTI-SEED COMPLETE  $(date -u +%FT%TZ)"
df -h / | tail -1
