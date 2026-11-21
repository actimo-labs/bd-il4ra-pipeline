#!/usr/bin/env python
"""
select_backbones.py -- choose which round-1 backbones are worth deep-resampling.

Split out of 12_deep_resample.sh because `conda run` does NOT reliably forward a
heredoc on stdin: the inline version ran, printed nothing, wrote no file, and the
caller then reported "No backbones passed" -- a silent no-op that would have wasted
the entire resample round. Caught by test-running the script before the night.

A BACKBONE is judged by its BEST sequence, not its mean: we are resampling geometry
that works, and one good sequence is evidence the geometry can support one.

Usage: select_backbones.py <production_dir> <out_tsv> <max_backbones> [max_ipae]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def scores(p: Path):
    d = {}
    for line in p.read_text().splitlines():
        if line.startswith("SCORE"):
            try:
                k, v = line[6:].split(":")
                d[k.strip()] = float(v)
            except ValueError:
                pass
    return d


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    maxbb = int(sys.argv[3])
    max_ipae = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0

    best = {}
    n_pdb = 0
    for p in sorted(src.glob("*/*/3_rf2/*.pdb")):
        n_pdb += 1
        s = scores(p)
        if "interaction_pae" not in s:
            continue
        arm = next((x for x in ("E1", "E2", "E3") if x in p.parts), None)
        m = re.match(r"(.+?)_dldesign_\d+_best$", p.stem)
        if not arm or not m:
            continue
        key = (arm, p.parts[-3], m.group(1))
        cur = best.get(key)
        if cur is None or s["interaction_pae"] < cur["ipae"]:
            best[key] = {"ipae": s["interaction_pae"],
                         "rmsd": s.get("target_aligned_antibody_rmsd", 999.0),
                         "plddt": s.get("pred_lddt", 0.0)}

    passing = [(k, v) for k, v in best.items() if v["ipae"] < max_ipae]
    passing.sort(key=lambda kv: (kv[1]["ipae"], kv[1]["rmsd"]))
    chosen = passing[:maxbb]

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as w:
        w.write("arm\tbatch\tbackbone\tbest_ipae\tbest_rmsd\tplddt\n")
        for (arm, batch, bb), v in chosen:
            w.write(f"{arm}\t{batch}\t{bb}\t{v['ipae']:.2f}\t{v['rmsd']:.2f}\t"
                    f"{v['plddt']:.3f}\n")

    print(f"[select] scanned {n_pdb} RF2 PDBs -> {len(best)} distinct backbones")
    print(f"[select] {len(passing)} backbones have a sequence with "
          f"interaction_pae < {max_ipae}; taking top {len(chosen)}")
    for (arm, batch, bb), v in chosen[:10]:
        print(f"         {arm} {batch} {bb}  ipae={v['ipae']:.2f} rmsd={v['rmsd']:.2f}")
    print(f"[select] wrote {out}")


if __name__ == "__main__":
    main()
