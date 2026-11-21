#!/bin/bash
# 11_run_production.sh -- round-1 production generation across E1/E2/E3.
#
# SIZING (from the measured pilot, RUNLOG 2026-11-21):
#   RFdiffusion 174.0 s/design | ProteinMPNN 2.25 s/seq | RF2 26.5 s/design
#   cost/backbone at k=2 seqs = 174 + 2*28.75 = 231.5 s
#   budget 14 GPU-h = 50400 s -> ~218 backbones -> ~436 designs
#
# ROUND-ROBIN BY EPITOPE, IN SMALL BATCHES. Deliberate: if this is killed at any
# point, all three arms have proportional coverage. Running E1 to completion first
# would leave E3 with nothing if we stop early.
#
# RESUMABLE: a batch whose RF2 output directory is already populated is skipped.
#
# Usage: bash scripts/11_run_production.sh [TOTAL_BACKBONES]

set -uo pipefail
source /mnt/comp5data/bd-il4r/env.sh

TOTAL="${1:-218}"
BATCH=10          # backbones per batch
NSEQ=2            # MPNN sequences per backbone in round 1; survivors get deep-resampled
TEMP=0.2
LOOPS="H1:7,H2:6,H3:5-13,L1:8-13,L2:7,L3:9-11"
RECYCLES=10
MIN_ROOT_GB=10

# proportional to slot targets, weighted up slightly for the two better patches
declare -A SHARE=( [E1]=50 [E2]=28 [E3]=22 )

ROOT="$BDIL4R/out/production"
LOGDIR="$BDIL4R/logs/production"
PROGRESS="$ROOT/progress.tsv"
mkdir -p "$ROOT" "$LOGDIR"
[ -f "$PROGRESS" ] || echo -e "utc\tepitope\tbatch\tstage\tn\telapsed_s" > "$PROGRESS"

FRAMEWORK="$BDIL4R/target/frameworks/hu4D5-8_Fv_HLT.pdb"
CKPT="$BDIL4R/rfantibody/weights/RFdiffusion_Ab.pt"

declare -A TARGET HOTSPOT NBATCH
for E in E1 E2 E3; do
  TARGET[$E]="$BDIL4R/target/crops/${E}_target_HLT.pdb"
  HOTSPOT[$E]=$(python3 -c "import json;print(json.load(open('$BDIL4R/target/crops/manifest.json'))['$E']['hotspot_string'])")
  n=$(( TOTAL * ${SHARE[$E]} / 100 ))
  NBATCH[$E]=$(( (n + BATCH - 1) / BATCH ))
  [ -s "${TARGET[$E]}" ] || { echo "FATAL: missing ${TARGET[$E]}"; exit 1; }
  [ -n "${HOTSPOT[$E]}" ] || { echo "FATAL: empty hotspots for $E"; exit 1; }
done

echo "=============================================================="
echo "PRODUCTION ROUND 1   started $(date -u +%FT%TZ)"
echo "total backbones : $TOTAL   batch $BATCH   seqs/backbone $NSEQ"
for E in E1 E2 E3; do
  echo "  $E: ${NBATCH[$E]} batches x $BATCH = $(( ${NBATCH[$E]} * BATCH )) backbones   hotspots ${HOTSPOT[$E]}"
done
echo "est. GPU time   : $(python3 -c "print(f'{$TOTAL*(174+$NSEQ*28.75)/3600:.1f} h')")"
echo "=============================================================="

cd "$BDIL4R/rfantibody"
MAXB=0; for E in E1 E2 E3; do [ ${NBATCH[$E]} -gt $MAXB ] && MAXB=${NBATCH[$E]}; done

log() { echo -e "$(date -u +%FT%TZ)\t$1\t$2\t$3\t$4\t$5" >> "$PROGRESS"; }

for (( b=0; b<MAXB; b++ )); do
  for E in E1 E2 E3; do
    [ $b -ge ${NBATCH[$E]} ] && continue

    # disk guard -- a full root on a shared box is worse than a missed gate
    FREE=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
    if [ "$FREE" -lt "$MIN_ROOT_GB" ]; then
      echo "ABORT: root free ${FREE}G < ${MIN_ROOT_GB}G at $(date -u +%FT%TZ)"
      exit 2
    fi

    TAG=$(printf "%s_b%03d" "$E" "$b")
    OUT="$ROOT/$E/$(printf 'b%03d' $b)"
    if [ -d "$OUT/3_rf2" ] && [ "$(ls -A "$OUT/3_rf2" 2>/dev/null | wc -l)" -gt 0 ]; then
      echo "[$(date -u +%T)] $TAG already done, skipping"
      continue
    fi
    mkdir -p "$OUT"/{1_rfdiff,2_mpnn,3_rf2}

    echo "[$(date -u +%T)] $TAG  RFdiffusion x$BATCH"
    T0=$(date +%s)
    uv run rfdiffusion -t "${TARGET[$E]}" -f "$FRAMEWORK" -o "$OUT/1_rfdiff/$TAG" \
      -n "$BATCH" -l "$LOOPS" -h "${HOTSPOT[$E]}" -w "$CKPT" --no-trajectory \
      > "$LOGDIR/${TAG}_1_rfdiff.log" 2>&1
    T1=$(date +%s); NB=$(ls "$OUT"/1_rfdiff/*.pdb 2>/dev/null | wc -l)
    log "$E" "$b" rfdiffusion "$NB" "$((T1-T0))"
    if [ "$NB" -eq 0 ]; then
      echo "  !! RFdiffusion produced nothing for $TAG; see $LOGDIR/${TAG}_1_rfdiff.log"
      continue
    fi

    echo "[$(date -u +%T)] $TAG  ProteinMPNN x$NSEQ  (${NB} backbones, rfdiff $((T1-T0))s)"
    T2=$(date +%s)
    uv run proteinmpnn -i "$OUT/1_rfdiff" -o "$OUT/2_mpnn" -n "$NSEQ" -t "$TEMP" \
      > "$LOGDIR/${TAG}_2_mpnn.log" 2>&1
    T3=$(date +%s); NS=$(ls "$OUT"/2_mpnn/*.pdb 2>/dev/null | wc -l)
    log "$E" "$b" proteinmpnn "$NS" "$((T3-T2))"
    [ "$NS" -eq 0 ] && { echo "  !! MPNN produced nothing for $TAG"; continue; }

    echo "[$(date -u +%T)] $TAG  RF2 (${NS} seqs)"
    T4=$(date +%s)
    uv run rf2 -i "$OUT/2_mpnn" -o "$OUT/3_rf2" -r "$RECYCLES" --hotspot-show-prop 0.1 \
      > "$LOGDIR/${TAG}_3_rf2.log" 2>&1
    T5=$(date +%s); NP=$(ls "$OUT"/3_rf2/*.pdb 2>/dev/null | wc -l)
    log "$E" "$b" rf2 "$NP" "$((T5-T4))"

    DONE=$(ls "$ROOT"/*/*/3_rf2/*.pdb 2>/dev/null | wc -l)
    echo "[$(date -u +%T)] $TAG DONE  batch=$((T5-T0))s  pool now $DONE designs"
  done
done

echo "=============================================================="
echo "PRODUCTION ROUND 1 COMPLETE  $(date -u +%FT%TZ)"
echo "designs: $(ls "$ROOT"/*/*/3_rf2/*.pdb 2>/dev/null | wc -l)"
for E in E1 E2 E3; do
  echo "  $E: $(ls "$ROOT/$E"/*/3_rf2/*.pdb 2>/dev/null | wc -l)"
done
du -sh "$ROOT"; df -h / | tail -1
