#!/bin/bash
# 15_round2_gen.sh -- round-2 generation for DIVERSITY, with the sequon prefilter inline.
#
# Why: after honest 5-seed scoring the pool collapsed to 24 survivors in 11 CDR-H3
# clusters, and three clusters supply 11 of the selected 20 (two H3s are identical).
# The constraint is no longer candidate COUNT, it is cluster diversity -- which only new
# backbones can supply. Resampling the existing 9 surviving backbones cannot create new
# clusters, and the <=3-per-cluster cap already binds.
#
# Arms: E1 and E2 only. E3 is invalidated (N134 mask correction) and a fresh E3v2 arm
# would need its own pilot, which there is no time to validate properly.
#
# Every stage is resumable; batches with a non-empty 4_rf2/ are skipped.
set -uo pipefail
source /mnt/comp5data/bd-il4r/env.sh
REPO="${REPO:-/home/HarjasG/tnf-track3/bd-il4ra-pipeline}"
NBB="${1:-70}"; BATCH=10; NSEQ=16; TEMP=0.2; MIN_ROOT_GB=10
declare -A SHARE=( [E1]=70 [E2]=30 )
OUT="$BDIL4R/out/round2"; LOGDIR="$BDIL4R/logs/round2"
mkdir -p "$OUT" "$LOGDIR"
FRAMEWORK="$BDIL4R/target/frameworks/hu4D5-8_Fv_HLT.pdb"
CKPT="$BDIL4R/rfantibody/weights/RFdiffusion_Ab.pt"
LOOPS="H1:7,H2:6,H3:9-15,L1:8-13,L2:7,L3:9-11"   # H3 shifted LONGER: 31% of round-1
                                                  # compute went to H3<=7, and 8 of the
                                                  # first selected 20 had H3<=7. Natural
                                                  # CDR-H3 is longer and H3 dominates
                                                  # antigen contact.
echo "=============================================================="
echo "ROUND 2 (diversity)  started $(date -u +%FT%TZ)"
echo "backbones $NBB  seqs/backbone $NSEQ  loops $LOOPS"
echo "=============================================================="
declare -A NB
for E in E1 E2; do NB[$E]=$(( NBB * ${SHARE[$E]} / 100 / BATCH )); done
cd "$BDIL4R/rfantibody"
MAX=0; for E in E1 E2; do [ ${NB[$E]} -gt $MAX ] && MAX=${NB[$E]}; done
for ((b=0;b<MAX;b++)); do
  for E in E1 E2; do
    [ $b -ge ${NB[$E]} ] && continue
    FREE=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
    [ "$FREE" -lt "$MIN_ROOT_GB" ] && { echo "ABORT: root ${FREE}G"; exit 2; }
    TAG=$(printf "%s_r2b%03d" "$E" "$b"); W="$OUT/$E/$(printf 'r2b%03d' $b)"
    if [ -d "$W/4_rf2" ] && [ "$(ls -A "$W/4_rf2" 2>/dev/null|wc -l)" -gt 0 ]; then
      echo "[$(date -u +%T)] $TAG done, skip"; continue; fi
    mkdir -p "$W"/{1_rfdiff,2_mpnn,3_clean,4_rf2}
    HS=$(python3 -c "import json;print(json.load(open('$BDIL4R/target/crops/manifest.json'))['$E']['hotspot_string'])")
    T0=$(date +%s)
    uv run rfdiffusion -t "$BDIL4R/target/crops/${E}_target_HLT.pdb" -f "$FRAMEWORK" \
      -o "$W/1_rfdiff/$TAG" -n "$BATCH" -l "$LOOPS" -h "$HS" -w "$CKPT" --no-trajectory \
      > "$LOGDIR/${TAG}_rfdiff.log" 2>&1
    NBK=$(ls "$W"/1_rfdiff/*.pdb 2>/dev/null|wc -l)
    [ "$NBK" -eq 0 ] && { echo "  !! $TAG no backbones"; continue; }
    uv run proteinmpnn -i "$W/1_rfdiff" -o "$W/2_mpnn" -n "$NSEQ" -t "$TEMP" \
      > "$LOGDIR/${TAG}_mpnn.log" 2>&1
    NM=$(ls "$W"/2_mpnn/*.pdb 2>/dev/null|wc -l)
    ~/miniforge3/bin/conda run -n boltz python "$REPO/scripts/07_prefilter.py" \
      --in "$W/2_mpnn" --out "$W/3_clean" --report "$W/prefilter.json" \
      > "$LOGDIR/${TAG}_prefilter.log" 2>&1
    NC=$(ls "$W"/3_clean/*.pdb 2>/dev/null|wc -l)
    [ "$NC" -eq 0 ] && { echo "[$(date -u +%T)] $TAG bb=$NBK mpnn=$NM clean=0 -- no RF2"; continue; }
    uv run rf2 -i "$W/3_clean" -o "$W/4_rf2" -r 10 --hotspot-show-prop 0.1 \
      > "$LOGDIR/${TAG}_rf2.log" 2>&1
    NP=$(ls "$W"/4_rf2/*.pdb 2>/dev/null|wc -l)
    echo "[$(date -u +%T)] $TAG bb=$NBK mpnn=$NM clean=$NC folded=$NP  ($(( $(date +%s)-T0 ))s)"
  done
done
echo "ROUND 2 COMPLETE $(date -u +%FT%TZ)  designs: $(ls "$OUT"/*/*/4_rf2/*.pdb 2>/dev/null|wc -l)"
