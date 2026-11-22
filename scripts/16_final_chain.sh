#!/bin/bash
# 16_final_chain.sh -- the LAST GPU run. Bounded, chained end to end, then stops.
#
# Purpose: buy CDR-H3 cluster diversity and nothing else. The current 20 is valid and
# honestly scored, but 11 clusters cover 20 designs and the largest two supply 9 of
# them, from only 12 backbones. Resampling existing backbones cannot create new
# clusters. Only new backbones can.
#
# Deliberately small: ~30 backbones, not 70. Everything is chained so the GPU is never
# idle between stages -- twice this campaign a stage boundary cost hours of idle A100.
#
# Budget: ~2.5 GPU-h. After this, no further generation.
#
# Usage: bash scripts/16_final_chain.sh
set -uo pipefail
source /mnt/comp5data/bd-il4r/env.sh
REPO="${REPO:-/home/HarjasG/tnf-track3/bd-il4ra-pipeline}"
CONDA=~/miniforge3/bin/conda
LOG="$BDIL4R/logs/final_chain.log"
MIN_ROOT_GB=10
BATCH=10
NSEQ=16
TEMP=0.2
LOOPS="H1:7,H2:6,H3:9-15,L1:8-13,L2:7,L3:9-11"
SCREEN_PAE=14.0      # permissive single-sample screen; 5 seeds decide properly later
SEEDS=(1001 2002 3003 4004 5005)
OUT="$BDIL4R/out/round2"
FRAMEWORK="$BDIL4R/target/frameworks/hu4D5-8_Fv_HLT.pdb"
CKPT="$BDIL4R/rfantibody/weights/RFdiffusion_Ab.pt"

say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
guard() { FREE=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
          [ "$FREE" -lt "$MIN_ROOT_GB" ] && { say "ABORT: root ${FREE}G"; exit 2; } || true; }

say "=== FINAL CHAIN START (last GPU run) ==="
cd "$BDIL4R/rfantibody"

# ---- 1. generate: 2 E1 batches + 1 E2 batch = 30 backbones -------------------
for SPEC in "E1:0" "E1:1" "E2:0"; do
  E="${SPEC%%:*}"; b="${SPEC##*:}"
  guard
  TAG=$(printf "%s_r2b%03d" "$E" "$b"); W="$OUT/$E/$(printf 'r2b%03d' $b)"
  if [ -d "$W/4_rf2" ] && [ "$(ls -A "$W/4_rf2" 2>/dev/null|wc -l)" -gt 0 ]; then
    say "$TAG already done, skipping"; continue; fi
  mkdir -p "$W"/{1_rfdiff,2_mpnn,3_clean,4_rf2}
  HS=$(python3 -c "import json;print(json.load(open('$BDIL4R/target/crops/manifest.json'))['$E']['hotspot_string'])")
  T0=$(date +%s)
  uv run rfdiffusion -t "$BDIL4R/target/crops/${E}_target_HLT.pdb" -f "$FRAMEWORK" \
    -o "$W/1_rfdiff/$TAG" -n "$BATCH" -l "$LOOPS" -h "$HS" -w "$CKPT" --no-trajectory \
    > "$BDIL4R/logs/${TAG}_rfdiff.log" 2>&1
  NBK=$(ls "$W"/1_rfdiff/*.pdb 2>/dev/null|wc -l)
  [ "$NBK" -eq 0 ] && { say "$TAG produced no backbones"; continue; }
  uv run proteinmpnn -i "$W/1_rfdiff" -o "$W/2_mpnn" -n "$NSEQ" -t "$TEMP" \
    > "$BDIL4R/logs/${TAG}_mpnn.log" 2>&1
  NM=$(ls "$W"/2_mpnn/*.pdb 2>/dev/null|wc -l)
  $CONDA run -n boltz python "$REPO/scripts/07_prefilter.py" --in "$W/2_mpnn" \
    --out "$W/3_clean" --report "$W/prefilter.json" > "$BDIL4R/logs/${TAG}_pf.log" 2>&1
  NC=$(ls "$W"/3_clean/*.pdb 2>/dev/null|wc -l)
  [ "$NC" -eq 0 ] && { say "$TAG bb=$NBK mpnn=$NM clean=0 -- no RF2 spend"; continue; }
  uv run rf2 -i "$W/3_clean" -o "$W/4_rf2" -r 10 --hotspot-show-prop 0.1 \
    > "$BDIL4R/logs/${TAG}_rf2.log" 2>&1
  say "$TAG bb=$NBK mpnn=$NM clean=$NC folded=$(ls "$W"/4_rf2/*.pdb 2>/dev/null|wc -l) ($(( $(date +%s)-T0 ))s)"
done
say "round-2 designs: $(ls "$OUT"/*/*/4_rf2/*.pdb 2>/dev/null|wc -l)"

# ---- 2. harvest round 2 -------------------------------------------------------
say "--- harvest round 2 ---"
$CONDA run -n boltz python "$REPO/scripts/06_harvest.py" \
  --root "$OUT" --pattern "*/*/4_rf2/*.pdb" \
  --out "$BDIL4R/out/candidates_round2.tsv" 2>&1 | tail -15 | tee -a "$LOG"

# ---- 3. 5-seed rescore the promising round-2 designs --------------------------
say "--- multi-seed rescore of round-2 screens (pae < $SCREEN_PAE) ---"
MS="$BDIL4R/out/multiseed_r2"
mkdir -p "$MS/in"
$CONDA run -n boltz python - "$BDIL4R/out/candidates_round2.tsv" "$MS" "$SCREEN_PAE" <<'PYEOF' 2>&1 | tee -a "$LOG"
import csv, json, os, shutil, sys
from pathlib import Path
man, out, cut = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
rows = list(csv.DictReader(open(man), delimiter="\t"))
def num(v):
    try: return float(v)
    except: return None
keep, mapping = [], {}
for r in rows:
    if r.get("eligibility_status") != "pass" or r.get("novelty_status") == "fail":
        continue
    p = num(r.get("rf2_iface_hl_vs_t"))
    if p is None or p >= cut:
        continue
    src = r["artifact_paths"].replace("/4_rf2/", "/3_clean/").replace("_best.pdb", ".pdb")
    if not os.path.exists(src):
        continue
    name = r["candidate_id"][:80]
    shutil.copy2(src, out / "in" / f"{name}.pdb")
    mapping[name] = r["candidate_id"]
    keep.append(name)
(out / "name_to_candidate.json").write_text(json.dumps(mapping, indent=2))
print(f"[r2-rescore] {len(rows)} round-2 designs -> {len(keep)} to rescore at 5 seeds")
PYEOF
N=$(ls "$MS"/in/*.pdb 2>/dev/null | wc -l)
if [ "$N" -gt 0 ]; then
  say "rescoring $N designs x 5 seeds (~$(python3 -c "print(f'{$N*5*24.1/3600:.1f}')") GPU-h)"
  for S in "${SEEDS[@]}"; do
    guard
    D="$MS/seed_$S"; mkdir -p "$D"
    [ "$(ls "$D"/*.pdb 2>/dev/null|wc -l)" -ge "$N" ] && { say "seed $S done, skip"; continue; }
    uv run rf2 -i "$MS/in" -o "$D" -r 10 --hotspot-show-prop 0.1 --seed "$S" \
      > "$BDIL4R/logs/r2_seed_$S.log" 2>&1
    say "seed $S: $(ls "$D"/*.pdb 2>/dev/null|wc -l)/$N"
  done
  $CONDA run -n boltz python "$REPO/scripts/aggregate_multiseed.py" \
    "$MS" "$BDIL4R/out/candidates_round2.tsv" 2>&1 | tee -a "$LOG"
else
  say "no round-2 designs passed the screen; nothing to rescore"
fi

# ---- 4. merge, select, build --------------------------------------------------
say "--- merge + final select ---"
cp "$REPO/candidates.tsv" "$BDIL4R/out/lkg/candidates_preRound2Merge.tsv"
$CONDA run -n boltz python "$REPO/scripts/merge_manifests.py" \
  "$REPO/candidates.tsv" "$BDIL4R/out/candidates_round2.tsv" 2>&1 | tee -a "$LOG"
python3 "$REPO/scripts/08_rank_select.py" --tsv "$REPO/candidates.tsv" 2>&1 | tee -a "$LOG"
$CONDA run -n boltz python "$REPO/scripts/build_submission.py" \
  --manifest "$REPO/candidates.tsv" --out "$BDIL4R/out/lkg/round1_FINAL.xlsx" \
  --expect 20 --rename 2>&1 | grep -E "checks passed|write\]|REFUS" | tee -a "$LOG"
cp "$REPO/candidates.tsv" "$BDIL4R/out/lkg/candidates_FINAL.tsv"

say "=== FINAL CHAIN COMPLETE. No further generation. ==="
nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader | tee -a "$LOG"
