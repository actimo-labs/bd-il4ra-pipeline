#!/usr/bin/env python
"""
merge_manifests.py -- append rows from an extra manifest into the main one.

Split out of 13_overnight_chain.sh: `conda run` does not forward a heredoc on stdin,
so the inline version was a silent no-op. See RUNLOG 2026-11-21.

Usage: merge_manifests.py <main.tsv> <extra.tsv>
"""
import csv
import sys
from pathlib import Path


def main():
    main_p, extra_p = Path(sys.argv[1]), Path(sys.argv[2])
    if not extra_p.exists():
        print(f"[merge] no extra manifest at {extra_p}, nothing to merge")
        return
    a = list(csv.DictReader(open(main_p), delimiter="\t")) if main_p.exists() else []
    b = list(csv.DictReader(open(extra_p), delimiter="\t"))
    if not a and not b:
        print("[merge] both manifests empty")
        return
    cols = list(a[0].keys()) if a else list(b[0].keys())
    seen = {r["candidate_id"] for r in a}
    add = [r for r in b if r["candidate_id"] not in seen]
    with open(main_p, "w") as w:
        w.write("\t".join(cols) + "\n")
        for r in a + add:
            w.write("\t".join(str(r.get(c, "not_run")) for c in cols) + "\n")
    print(f"[merge] {len(a)} existing + {len(add)} new = {len(a)+len(add)} candidates "
          f"-> {main_p}")


if __name__ == "__main__":
    main()
