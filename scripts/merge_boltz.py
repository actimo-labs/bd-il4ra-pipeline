#!/usr/bin/env python
"""
merge_boltz.py -- fold Boltz-2 cross-check metrics into candidates.tsv.

Split out of 13_overnight_chain.sh for the same reason as merge_manifests.py.

Asserts a NON-EMPTY join on the FULL candidate_id. CLAUDE.md section 6 trap 5: a prefix
match on design ids silently blanked an entire comparison in a prior campaign, so this
refuses to write rather than produce a manifest whose Boltz columns are quietly all
not_run.

Usage: merge_boltz.py <candidates.tsv> <boltz_results.json>
"""
import csv
import json
import sys
from pathlib import Path


def main():
    man, bj = Path(sys.argv[1]), Path(sys.argv[2])
    if not bj.exists():
        print(f"[merge-boltz] no boltz results at {bj}")
        return
    res = {r["candidate_id"]: r for r in json.loads(bj.read_text())
           if isinstance(r, dict) and "candidate_id" in r}
    if not res:
        print("[merge-boltz] boltz results file contains no candidates")
        return
    rows = list(csv.DictReader(open(man), delimiter="\t"))
    if not rows:
        print("[merge-boltz] manifest is empty")
        return
    cols = list(rows[0].keys())

    hit = sum(1 for r in rows if r["candidate_id"] in res)
    if hit == 0:
        sys.exit(
            f"REFUSING TO WRITE: Boltz join matched 0 of {len(rows)} manifest rows on "
            f"full candidate_id. Sample manifest id: {rows[0]['candidate_id']!r}; "
            f"sample boltz id: {next(iter(res))!r}. A silently empty join would leave "
            f"every boltz column as not_run and look like 'Boltz was never run'.")

    n_set = 0
    for r in rows:
        b = res.get(r["candidate_id"])
        if not b:
            continue
        if b.get("boltz2_iface_mean5") is not None:
            r["boltz2_iface_mean5"] = b["boltz2_iface_mean5"]
            n_set += 1
        if b.get("boltz2_iface_sd5") is not None:
            r["boltz2_iface_sd5"] = b["boltz2_iface_sd5"]
    with open(man, "w") as w:
        w.write("\t".join(cols) + "\n")
        for r in rows:
            w.write("\t".join(str(r.get(c, "not_run")) for c in cols) + "\n")
    print(f"[merge-boltz] joined {hit}/{len(rows)} rows on full candidate_id; "
          f"{n_set} boltz2_iface_mean5 values written")


if __name__ == "__main__":
    main()
