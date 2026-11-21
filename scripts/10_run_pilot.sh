#!/bin/bash
# 10_run_pilot.sh -- 2-design end-to-end pilot. This is the G1 gate.
#
# Times every stage so G2 can be sized on measured numbers rather than guesses
# (PIPELINE.md section 3: "Measure, then size. Do not guess.").
#
# Usage: bash scripts/10_run_pilot.sh [EPITOPE] [NUM_DESIGNS]

set -uo pipefail
source /mnt/comp5data/bd-il4r/env.sh

EPI="${1:-E1}"
N="${2:-2}"
TAG="${EPI}_n${N}"
OUT="$BDIL4R/out/pilot/$TAG"
LOG="$BDIL4R/logs/pilot_$TAG"
mkdir -p "$OUT"/{1_rfdiff,2_mpnn,3_rf2} "$LOG"

TARGET="$BDIL4R/target/crops/${EPI}_target_HLT.pdb"
FRAMEWORK="$BDIL4R/target/frameworks/hu4D5-8_Fv_HLT.pdb"
CKPT="$BDIL4R/rfantibody/weights/RFdiffusion_Ab.pt"
HOTSPOTS=$(python3 -c "import json;print(json.load(open('$BDIL4R/target/crops/manifest.json'))['$EPI']['hotspot_string'])")
LOOPS="H1:7,H2:6,H3:5-13,L1:8-13,L2:7,L3:9-11"
NSEQ=2
TEMP=0.2

echo "=================================================="
echo "PILOT  epitope=$EPI  designs=$N"
echo "target   : $TARGET"
echo "framework: $FRAMEWORK"
echo "hotspots : $HOTSPOTS"
echo "loops    : $LOOPS"
echo "out      : $OUT"
echo "started  : $(date -u +%FT%TZ)"
echo "=================================================="

# fail fast rather than discovering a missing input mid-run
for f in "$TARGET" "$FRAMEWORK" "$CKPT"; do
  [ -s "$f" ] || { echo "FATAL: missing or empty $f"; exit 1; }
done
[ -n "$HOTSPOTS" ] || { echo "FATAL: empty hotspot string"; exit 1; }

cd "$BDIL4R/rfantibody"

note() { echo; echo "----- $* -----"; date -u +%FT%TZ; }
secs() { python3 -c "print(f'{$2-$1:.1f}')"; }

# ---------------------------------------------------------------- stage 1
note "STAGE 1/3  RFdiffusion_Ab  ($N designs)"
T0=$(date +%s.%N)
uv run rfdiffusion \
  --target "$TARGET" \
  --framework "$FRAMEWORK" \
  --output "$OUT/1_rfdiff/${EPI}" \
  --num-designs "$N" \
  --design-loops "$LOOPS" \
  --hotspots "$HOTSPOTS" \
  --weights "$CKPT" \
  --no-trajectory \
  > "$LOG/1_rfdiff.log" 2>&1
RC1=$?
T1=$(date +%s.%N)
S1=$(secs $T0 $T1)
NB=$(ls "$OUT"/1_rfdiff/*.pdb 2>/dev/null | wc -l)
echo "rc=$RC1  elapsed=${S1}s  backbones=$NB"
[ "$NB" -gt 0 ] || { echo "FATAL: RFdiffusion produced no PDBs"; tail -40 "$LOG/1_rfdiff.log"; exit 1; }

# ---------------------------------------------------------------- stage 2
note "STAGE 2/3  ProteinMPNN  ($NSEQ seqs/backbone, temp $TEMP)"
T2=$(date +%s.%N)
uv run proteinmpnn \
  --input-dir "$OUT/1_rfdiff" \
  --output-dir "$OUT/2_mpnn" \
  --seqs-per-struct "$NSEQ" \
  --temperature "$TEMP" \
  > "$LOG/2_mpnn.log" 2>&1
RC2=$?
T3=$(date +%s.%N)
S2=$(secs $T2 $T3)
NS=$(ls "$OUT"/2_mpnn/*.pdb 2>/dev/null | wc -l)
echo "rc=$RC2  elapsed=${S2}s  sequences=$NS"
[ "$NS" -gt 0 ] || { echo "FATAL: ProteinMPNN produced no PDBs"; tail -40 "$LOG/2_mpnn.log"; exit 1; }

# ---------------------------------------------------------------- stage 3
note "STAGE 3/3  RF2_ab  (10 recycles)"
T4=$(date +%s.%N)
uv run rf2 \
  --input-dir "$OUT/2_mpnn" \
  --output-dir "$OUT/3_rf2" \
  --num-recycles 10 \
  --hotspot-show-prop 0.1 \
  > "$LOG/3_rf2.log" 2>&1
RC3=$?
T5=$(date +%s.%N)
S3=$(secs $T4 $T5)
NP=$(ls "$OUT"/3_rf2/*.pdb 2>/dev/null | wc -l)
echo "rc=$RC3  elapsed=${S3}s  predictions=$NP"

# ---------------------------------------------------------------- summary
note "PILOT TIMING SUMMARY"
python3 - <<PY | tee "$OUT/timing.json"
import json
d = {
  "epitope": "$EPI", "n_designs": $N, "n_seqs_per_backbone": $NSEQ,
  "rfdiffusion": {"rc": $RC1, "total_s": $S1, "n_out": $NB,
                  "s_per_design": round($S1/max($NB,1), 1)},
  "proteinmpnn": {"rc": $RC2, "total_s": $S2, "n_out": $NS,
                  "s_per_backbone": round($S2/max($NB,1), 1)},
  "rf2":         {"rc": $RC3, "total_s": $S3, "n_out": $NP,
                  "s_per_design": round($S3/max($NP,1), 1)},
}
print(json.dumps(d, indent=2))
PY

echo
echo "finished : $(date -u +%FT%TZ)"
echo "logs     : $LOG"
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv
df -h / | tail -1
