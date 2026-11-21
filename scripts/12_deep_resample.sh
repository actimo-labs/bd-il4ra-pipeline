#!/bin/bash
# 12_deep_resample.sh -- deep sequence resampling on backbones that already work.
#
# PIPELINE.md section 3 rule 2: "More sequence draws on a backbone that already works
# beats more geometry" -- ~27x the hit rate at a fifth of the GPU cost in prior
# campaigns. Our own measured numbers say the same thing for this system:
#   new backbone   = 94 s (marginal, batch 10)
#   new sequence   = 2.25 s MPNN + 26.5 s RF2 = 28.75 s
#
# Plus the pilot finding: ProteinMPNN makes CDR N-glycosylation sequons often enough
# that folding every draw wastes most of the RF2 budget. So draws are screened on
# sequence FIRST (07_prefilter.py) and only clean ones reach RF2.
#
# Usage: bash scripts/12_deep_resample.sh [N_SEQS] [MAX_BACKBONES]

set -uo pipefail
source /mnt/comp5data/bd-il4r/env.sh

NSEQ="${1:-12}"
MAXBB="${2:-60}"
TEMP=0.25          # slightly above round 1's 0.2 to buy sequence diversity on a fixed backbone
RECYCLES=10
MIN_ROOT_GB=10

REPO="${REPO:-/home/HarjasG/tnf-track3/bd-il4ra-pipeline}"
[ -f "$REPO/scripts/07_prefilter.py" ] || { echo "FATAL: cannot find scripts/ under REPO=$REPO"; exit 1; }
SRC="$BDIL4R/out/production"
OUT="$BDIL4R/out/resample"
LOGDIR="$BDIL4R/logs/resample"
SEL="$OUT/selected_backbones.tsv"
mkdir -p "$OUT" "$LOGDIR"

echo "=============================================================="
echo "DEEP RESAMPLE   started $(date -u +%FT%TZ)"
echo "seqs/backbone $NSEQ   max backbones $MAXBB   temp $TEMP"
echo "=============================================================="

# ---- pick the backbones worth resampling, from round-1 RF2 metrics ----
# NOTE: this used to be an inline heredoc piped to `conda run`. It silently did nothing,
# because conda run does not reliably forward stdin. Now a real file, and the exit
# status is checked.
~/miniforge3/bin/conda run -n boltz python "$REPO/scripts/select_backbones.py" \
  "$SRC" "$SEL" "$MAXBB" || { echo "FATAL: backbone selection failed"; exit 1; }
[ -s "$SEL" ] || { echo "FATAL: $SEL was not written"; exit 1; }

N=$(( $(wc -l < "$SEL") - 1 ))
if [ "$N" -le 0 ]; then
  echo "No backbones passed interaction_pae < 10. Nothing to resample."
  exit 0
fi
echo
echo "resampling $N backbones x $NSEQ sequences"
echo "est. GPU: $(python3 -c "print(f'{$N*($NSEQ*2.25)/3600:.2f} h MPNN + up to {$N*$NSEQ*26.5/3600:.2f} h RF2 before prefiltering')")"
echo

cd "$BDIL4R/rfantibody"
tail -n +2 "$SEL" | while IFS=$'\t' read -r ARM BATCH BB IPAE RMSD PLDDT; do
  FREE=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
  [ "$FREE" -lt "$MIN_ROOT_GB" ] && { echo "ABORT: root free ${FREE}G"; exit 2; }

  SRCPDB="$SRC/$ARM/$BATCH/1_rfdiff/${BB}.pdb"
  [ -s "$SRCPDB" ] || { echo "  missing $SRCPDB, skipping"; continue; }

  W="$OUT/$ARM/${BATCH}_${BB}"
  if [ -d "$W/4_rf2" ] && [ "$(ls -A "$W/4_rf2" 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "[$(date -u +%T)] $ARM/$BATCH/$BB already resampled, skipping"; continue
  fi
  mkdir -p "$W"/{1_bb,2_mpnn,3_clean,4_rf2}
  cp "$SRCPDB" "$W/1_bb/"

  uv run proteinmpnn -i "$W/1_bb" -o "$W/2_mpnn" -n "$NSEQ" -t "$TEMP" \
    > "$LOGDIR/${ARM}_${BATCH}_${BB}_mpnn.log" 2>&1
  NM=$(ls "$W"/2_mpnn/*.pdb 2>/dev/null | wc -l)

  # sequence-level screen BEFORE spending RF2. Raw 2_mpnn is never modified.
  ~/miniforge3/bin/conda run -n boltz python "$REPO/scripts/07_prefilter.py" \
    --in "$W/2_mpnn" --out "$W/3_clean" --report "$W/prefilter.json" \
    > "$LOGDIR/${ARM}_${BATCH}_${BB}_prefilter.log" 2>&1
  NC=$(ls "$W"/3_clean/*.pdb 2>/dev/null | wc -l)

  if [ "$NC" -eq 0 ]; then
    echo "[$(date -u +%T)] $ARM/$BATCH/$BB  mpnn=$NM clean=0  -- no RF2 spend"
    continue
  fi

  uv run rf2 -i "$W/3_clean" -o "$W/4_rf2" -r "$RECYCLES" --hotspot-show-prop 0.1 \
    > "$LOGDIR/${ARM}_${BATCH}_${BB}_rf2.log" 2>&1
  NP=$(ls "$W"/4_rf2/*.pdb 2>/dev/null | wc -l)
  echo "[$(date -u +%T)] $ARM/$BATCH/$BB  mpnn=$NM clean=$NC folded=$NP  (saved $(( (NM-NC)*27 ))s of RF2)"
done

echo "=============================================================="
echo "DEEP RESAMPLE COMPLETE  $(date -u +%FT%TZ)"
echo "designs: $(ls "$OUT"/*/*/4_rf2/*.pdb 2>/dev/null | wc -l)"
df -h / | tail -1
