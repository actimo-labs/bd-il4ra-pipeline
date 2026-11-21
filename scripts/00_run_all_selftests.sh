#!/bin/bash
# 00_run_all_selftests.sh -- regression gate. Run after any edit, before any long job.
# Exits non-zero if ANY module's self-test fails.
cd "$(dirname "$0")/.." || exit 1
CONDA=~/miniforge3/bin/conda
fail=0; tot=0
run() {  # run <interpreter> <script>
  tot=$((tot+1))
  out=$($1 "$2" --self-test 2>&1); rc=$?
  line=$(echo "$out" | grep -E "^self-test:" | tail -1)
  # Parse the summary line, do NOT grep for the word FAIL: several test NAMES legitimately
  # contain "HARD FAILS", which made this gate report a false positive on 05_novelty.py.
  passed=$(echo "$line" | sed -nE 's#^self-test: ([0-9]+)/([0-9]+) passed$#\1#p')
  total=$(echo "$line"  | sed -nE 's#^self-test: ([0-9]+)/([0-9]+) passed$#\2#p')
  if [ -n "$passed" ] && [ "$passed" = "$total" ] && [ "$rc" -eq 0 ]; then
    echo "  ok    $(basename "$2")  $line"
  else
    echo "  FAIL  $(basename "$2")  ${line:-no summary line} (rc=$rc)"
    echo "$out" | grep -E "^  \[FAIL\]" | head -3 | sed 's/^/        /'
    fail=$((fail+1))
  fi
}
echo "=== self-test regression gate $(date -u +%FT%TZ) ==="
echo "-- stdlib (bare python3, no env) --"
for s in scripts/qc_liabilities.py scripts/05_novelty.py scripts/08_rank_select.py scripts/build_submission.py; do
  run python3 "$s"
done
echo "-- boltz env (numpy/biopython) --"
for s in scripts/01_target_prep.py scripts/02_epitopes.py scripts/03_crop_hlt.py \
         scripts/04_interface.py scripts/06_harvest.py scripts/07_prefilter.py \
         scripts/09_boltz_crosscheck.py; do
  run "$CONDA run -n boltz python" "$s"
done
echo "-- shell syntax --"
for s in scripts/*.sh; do
  tot=$((tot+1))
  if bash -n "$s" 2>/dev/null; then echo "  ok    $(basename "$s")  syntax";
  else echo "  FAIL  $(basename "$s")  syntax"; fail=$((fail+1)); fi
done
echo "=== $((tot-fail))/$tot modules clean ==="
exit $(( fail > 0 ))
