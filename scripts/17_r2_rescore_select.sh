#!/bin/bash
# 17_r2_rescore_select.sh -- 5-seed rescore the round-2 screens, then final select.
# Fixes the contamination caused by the heredoc bug in 16_final_chain.sh: 5 round-2
# designs entered the submitted 20 on single RF2 samples, ranked against 15 that had
# 5-seed means. NO heredocs in this file.
set -uo pipefail
source /mnt/comp5data/bd-il4r/env.sh
REPO="${REPO:-/home/HarjasG/tnf-track3/bd-il4ra-pipeline}"
CONDA=~/miniforge3/bin/conda
MS="$BDIL4R/out/multiseed_r2"
LOG="$BDIL4R/logs/r2_rescore.log"
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
N=$(ls "$MS"/in/*.pdb 2>/dev/null | wc -l)
[ "$N" -gt 0 ] || { say "FATAL: no inputs in $MS/in"; exit 1; }
say "=== ROUND-2 RESCORE: $N designs x 5 seeds ==="
cd "$BDIL4R/rfantibody"
for S in 1001 2002 3003 4004 5005; do
  FREE=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
  [ "$FREE" -lt 10 ] && { say "ABORT: root ${FREE}G"; exit 2; }
  D="$MS/seed_$S"; mkdir -p "$D"
  if [ "$(ls "$D"/*.pdb 2>/dev/null|wc -l)" -ge "$N" ]; then say "seed $S done, skip"; continue; fi
  uv run rf2 -i "$MS/in" -o "$D" -r 10 --hotspot-show-prop 0.1 --seed "$S" \
    > "$BDIL4R/logs/r2_seed_$S.log" 2>&1
  say "seed $S: $(ls "$D"/*.pdb 2>/dev/null|wc -l)/$N"
done
say "--- aggregate (refuses below 3 seeds) ---"
$CONDA run -n boltz python "$REPO/scripts/aggregate_multiseed.py" \
  "$MS" "$BDIL4R/out/candidates_round2.tsv" 2>&1 | tee -a "$LOG"
say "--- rebuild main manifest from scratch, then merge round 2 ---"
cp "$BDIL4R/out/lkg/candidates_preRound2Merge.tsv" "$REPO/candidates.tsv"
$CONDA run -n boltz python "$REPO/scripts/merge_manifests.py" \
  "$REPO/candidates.tsv" "$BDIL4R/out/candidates_round2.tsv" 2>&1 | tee -a "$LOG"
say "--- final select ---"
python3 "$REPO/scripts/08_rank_select.py" --tsv "$REPO/candidates.tsv" 2>&1 | tee -a "$LOG"
$CONDA run -n boltz python "$REPO/scripts/build_submission.py" \
  --manifest "$REPO/candidates.tsv" --out "$BDIL4R/out/lkg/round1_FINAL.xlsx" \
  --expect 20 --rename 2>&1 | grep -E "checks passed|write\]|REFUS" | tee -a "$LOG"
cp "$REPO/candidates.tsv" "$BDIL4R/out/lkg/candidates_FINAL.tsv"
say "=== DONE ==="
