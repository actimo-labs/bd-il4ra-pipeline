#!/usr/bin/env python
"""
collect_r2_rescore.py -- gather round-2 designs for multi-seed rescoring.

Split out of 16_final_chain.sh because `conda run` does NOT forward a heredoc on stdin.
That bug was found, documented and worked around three times earlier in this campaign,
and I then wrote a fresh heredoc into the final chain. It silently selected zero of 35
eligible designs and let 5 single-sample designs into the submitted 20.

Usage: collect_r2_rescore.py <round2_manifest.tsv> <out_dir> <max_pae>
"""
import csv, json, os, shutil, sys
from pathlib import Path


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    man, out, cut = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
    (out / "in").mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(man), delimiter="\t"))
    mapping, copied, missing = {}, 0, 0
    for r in rows:
        if r.get("eligibility_status") != "pass" or r.get("novelty_status") == "fail":
            continue
        p = num(r.get("rf2_iface_hl_vs_t"))
        if p is None or p >= cut:
            continue
        src = r["artifact_paths"].replace("/4_rf2/", "/3_clean/").replace("_best.pdb", ".pdb")
        if not os.path.exists(src):
            missing += 1
            continue
        name = r["candidate_id"][:80]
        shutil.copy2(src, out / "in" / f"{name}.pdb")
        mapping[name] = r["candidate_id"]
        copied += 1
    (out / "name_to_candidate.json").write_text(json.dumps(mapping, indent=2))
    n = len(list((out / "in").glob("*.pdb")))
    print(f"[r2-collect] {len(rows)} round-2 designs, screen pae < {cut}")
    print(f"[r2-collect] copied {copied}, missing input {missing}, on disk {n}")
    if n != copied:
        sys.exit(f"REFUSING: {copied} copies but {n} files -- name collisions would "
                 f"mis-attribute scores")
    if n == 0:
        sys.exit("REFUSING: zero designs collected. With 145 eligible round-2 designs "
                 "this almost certainly means the screen is broken, not that nothing "
                 "qualified.")
    print(f"[r2-collect] estimated rescore cost: {n*5*24.1/3600:.2f} GPU-h")


if __name__ == "__main__":
    main()
