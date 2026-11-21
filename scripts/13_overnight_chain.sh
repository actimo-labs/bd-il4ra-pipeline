#!/bin/bash
# 13_overnight_chain.sh -- keep the GPU busy after round 1 finishes.
#
# Waits for production round 1 to exit, then runs, in order:
#   1. deep resample on backbones that already work (pre-RF2 sequon filter)
#   2. harvest the full pool into candidates.tsv
#   3. Boltz-2 orthogonal cross-check on the top survivors
#   4. harvest again, merging Boltz metrics, then rank and select
#
# Every stage is resumable and logs to RUNLOG-adjacent files. Nothing here submits
# anything, spends Geodesic credits, or pushes to a remote.
#
# Usage: bash scripts/13_overnight_chain.sh

set -uo pipefail
source /mnt/comp5data/bd-il4r/env.sh
REPO="${REPO:-/home/HarjasG/tnf-track3/bd-il4ra-pipeline}"
CONDA=~/miniforge3/bin/conda
LOG="$BDIL4R/logs/overnight_chain.log"
MIN_ROOT_GB=10

say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

say "=== OVERNIGHT CHAIN START ==="

# ---- 1. wait for round 1 ------------------------------------------------
say "waiting for production round 1 (tmux session 'prod') to finish"
while tmux has-session -t prod 2>/dev/null && \
      tmux list-panes -t prod -F '#{pane_pid}' >/dev/null 2>&1 && \
      pgrep -f "11_run_production.sh" >/dev/null; do
  sleep 60
done
say "production round 1 is no longer running"
say "pool: $(ls "$BDIL4R"/out/production/*/*/3_rf2/*.pdb 2>/dev/null | wc -l) designs"
for E in E1 E2 E3; do
  say "  $E: $(ls "$BDIL4R/out/production/$E"/*/3_rf2/*.pdb 2>/dev/null | wc -l) designs"
done

FREE=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
[ "$FREE" -lt "$MIN_ROOT_GB" ] && { say "ABORT: root free ${FREE}G"; exit 2; }

# ---- 2. deep resample ---------------------------------------------------
say "--- STAGE: deep resample ---"
bash "$REPO/scripts/12_deep_resample.sh" "${RESAMPLE_NSEQ:-16}" "${RESAMPLE_MAXBB:-80}" 2>&1 | tee -a "$LOG"
say "resample designs: $(ls "$BDIL4R"/out/resample/*/*/4_rf2/*.pdb 2>/dev/null | wc -l)"

# ---- 3. harvest everything ---------------------------------------------
say "--- STAGE: harvest (production + resample) ---"
$CONDA run -n boltz python "$REPO/scripts/06_harvest.py" \
  --out "$REPO/candidates.tsv" 2>&1 | tee -a "$LOG"
$CONDA run -n boltz python "$REPO/scripts/06_harvest.py" \
  --root "$BDIL4R/out/resample" --pattern "*/*/4_rf2/*.pdb" \
  --out "$BDIL4R/out/candidates_resample.tsv" 2>&1 | tee -a "$LOG"

# merge the two manifests, keeping full-name joins
$CONDA run -n boltz python - "$REPO/candidates.tsv" "$BDIL4R/out/candidates_resample.tsv" <<'PY' 2>&1 | tee -a "$LOG"
import csv, sys
from pathlib import Path
main, extra = Path(sys.argv[1]), Path(sys.argv[2])
if not extra.exists():
    print("[merge] no resample manifest, nothing to merge"); raise SystemExit
a = list(csv.DictReader(open(main), delimiter="\t")) if main.exists() else []
b = list(csv.DictReader(open(extra), delimiter="\t"))
cols = list(a[0].keys()) if a else list(b[0].keys())
seen = {r["candidate_id"] for r in a}
add = [r for r in b if r["candidate_id"] not in seen]
with open(main, "w") as w:
    w.write("\t".join(cols) + "\n")
    for r in a + add:
        w.write("\t".join(str(r.get(c, "not_run")) for c in cols) + "\n")
print(f"[merge] {len(a)} production + {len(add)} resample = {len(a)+len(add)} candidates")
PY

# ---- 4. Boltz-2 cross-check on the top survivors ------------------------
say "--- STAGE: Boltz-2 cross-check ---"
N_BOLTZ="${N_BOLTZ:-80}"
say "cross-checking up to $N_BOLTZ survivors at ~121 s each (~$(python3 -c "print(f'{$N_BOLTZ*121/3600:.1f}')") GPU-h)"
$CONDA run -n boltz python "$REPO/scripts/09_boltz_crosscheck.py" \
  --manifest "$REPO/candidates.tsv" --limit "$N_BOLTZ" \
  --out "$BDIL4R/out/boltz" 2>&1 | tail -200 | tee -a "$LOG"

# fold Boltz metrics back into the manifest, asserting a non-empty full-name join
$CONDA run -n boltz python - "$REPO/candidates.tsv" "$BDIL4R/out/boltz/boltz_results.json" <<'PY' 2>&1 | tee -a "$LOG"
import csv, json, sys
from pathlib import Path
man, bj = Path(sys.argv[1]), Path(sys.argv[2])
if not bj.exists():
    print("[merge-boltz] no boltz results"); raise SystemExit
res = {r["candidate_id"]: r for r in json.loads(bj.read_text()) if "candidate_id" in r}
rows = list(csv.DictReader(open(man), delimiter="\t"))
cols = list(rows[0].keys())
# CLAUDE.md s6 trap 5: match on FULL ids and assert the join is non-empty
hit = sum(1 for r in rows if r["candidate_id"] in res)
assert hit > 0, (f"Boltz join matched 0 of {len(rows)} rows on full candidate_id. "
                 f"Refusing to write a manifest with a silently empty join.")
for r in rows:
    b = res.get(r["candidate_id"])
    if not b:
        continue
    if b.get("boltz2_iface_mean5") is not None:
        r["boltz2_iface_mean5"] = b["boltz2_iface_mean5"]
    if b.get("boltz2_iface_sd5") is not None:
        r["boltz2_iface_sd5"] = b["boltz2_iface_sd5"]
with open(man, "w") as w:
    w.write("\t".join(cols) + "\n")
    for r in rows:
        w.write("\t".join(str(r.get(c, "not_run")) for c in cols) + "\n")
print(f"[merge-boltz] joined {hit}/{len(rows)} rows on full candidate_id")
PY

# ---- 5. rank and select -------------------------------------------------
say "--- STAGE: rank + select ---"
python3 "$REPO/scripts/08_rank_select.py" --tsv "$REPO/candidates.tsv" 2>&1 | tee -a "$LOG"

# ---- 6. last-known-good pool -------------------------------------------
say "--- STAGE: last-known-good snapshot ---"
mkdir -p "$BDIL4R/out/lkg"
cp "$REPO/candidates.tsv" "$BDIL4R/out/lkg/candidates_$(date -u +%Y%m%dT%H%M%SZ).tsv"
python3 "$REPO/scripts/build_submission.py" --manifest "$REPO/candidates.tsv" \
  --out "$BDIL4R/out/lkg/round1_draft.xlsx" --expect 20 2>&1 | tee -a "$LOG" || \
  say "submission builder refused (expected if fewer than 20 selected) -- see above"

say "=== OVERNIGHT CHAIN COMPLETE ==="
say "pool: $(ls "$BDIL4R"/out/production/*/*/3_rf2/*.pdb "$BDIL4R"/out/resample/*/*/4_rf2/*.pdb 2>/dev/null | wc -l) designs"
df -h / /mnt/comp5data | tail -2 | tee -a "$LOG"
