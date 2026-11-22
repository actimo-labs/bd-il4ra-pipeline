#!/usr/bin/env python
"""
collect_rescore_inputs.py -- gather RF2 inputs for multi-seed re-scoring.

Selects every design that passes all hard gates EXCEPT interaction_pae. Those are
precisely the designs a single unlucky RF2 roll may have wrongly eliminated.

Usage: collect_rescore_inputs.py <candidates.tsv> <out_dir>
"""
import csv
import json
import os
import shutil
import sys
from pathlib import Path


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def passes_except_pae(r):
    if r.get("eligibility_status") != "pass":
        return False
    if r.get("novelty_status") == "fail":
        return False
    cr = num(r.get("rf2_framework_aligned_cdr_rmsd"))
    if cr is not None and cr > 2.0:
        return False
    b = num(r.get("bsa_a2"))
    if b is not None and b < 400:
        return False
    mf = num(r.get("masked_contact_frac"))
    if mf is not None and mf > 0.40:
        return False
    return True


def rf2_input_for(artifact):
    """The RF2 output path maps back to the ProteinMPNN/clean input it was folded from."""
    p = (artifact.replace("/4_rf2/", "/3_clean/")
                 .replace("/3_rf2/", "/2_mpnn/")
                 .replace("_best.pdb", ".pdb"))
    return p if os.path.exists(p) else None


def main():
    man, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(man), delimiter="\t"))
    cand = [r for r in rows if passes_except_pae(r)]

    copied, missing, collisions = 0, 0, 0
    seen, mapping = {}, {}
    for r in cand:
        src = rf2_input_for(r["artifact_paths"])
        if src is None:
            missing += 1
            continue
        # RF2 keys outputs on the input FILENAME, so names must be unique across the
        # whole set -- resample and round-1 files can share a basename.
        base = Path(src).stem
        name = base
        if name in seen and seen[name] != src:
            collisions += 1
            name = f"{r['candidate_id']}"[:80]
        seen[name] = src
        mapping[name] = r["candidate_id"]
        shutil.copy2(src, out / f"{name}.pdb")
        copied += 1

    print(f"[collect] {len(rows)} in manifest, {len(cand)} pass all gates except pae")
    print(f"[collect] copied {copied}, missing input {missing}, renamed on collision {collisions}")
    n_on_disk = len(list(out.glob("*.pdb")))
    # RF2 keys outputs on filename, so we must be able to get back to candidate_id
    (out.parent / "name_to_candidate.json").write_text(json.dumps(mapping, indent=2))
    print(f"[collect] {n_on_disk} unique inputs in {out}")
    print(f"[collect] wrote {out.parent/'name_to_candidate.json'} ({len(mapping)} entries)")
    if n_on_disk != copied:
        print(f"[collect] WARNING: {copied} copies but {n_on_disk} files -- name collisions "
              f"silently overwrote inputs; results would be mis-attributed")
        sys.exit(1)


if __name__ == "__main__":
    main()
