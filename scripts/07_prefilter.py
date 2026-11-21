#!/usr/bin/env python
"""
07_prefilter.py -- cheap sequence-level screen between ProteinMPNN and RF2.

Why this exists: ProteinMPNN costs 2.25 s/sequence, RF2 costs 26.5 s/design (measured,
RUNLOG 2026-11-21). ProteinMPNN has no sequon awareness and in the pilot produced a CDR
N-glycosylation sequon in 3 of 4 designs -- a HARD eligibility gate, so those designs are
dead before RF2 ever sees them. Screening sequences first and only folding the survivors
buys roughly 3x the eligible output for the same GPU cost.

RAW OUTPUTS ARE NEVER MODIFIED. Clean designs are COPIED into a separate directory;
the ProteinMPNN output directory is left exactly as written.

Run:  conda run -n boltz python scripts/07_prefilter.py --in <mpnn_dir> --out <clean_dir>
Test: conda run -n boltz python scripts/07_prefilter.py --self-test
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(HERE / path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


hv = _load("hv", "06_harvest.py")
qc = _load("qc", "qc_liabilities.py")


def evaluate(pdb):
    """Sequence-only verdict. Returns (keep: bool, reason: str, info: dict)."""
    why = []
    ex = hv.extract(pdb, reason=why)
    if ex is None:
        return False, f"extract_failed: {why[0] if why else 'unknown'}", {}

    # the two gates that are both HARD and decidable from sequence alone
    cdr_sequons = []
    for name, seq in sorted(ex["cdrs"].items()):
        for p in qc.find_all(r"N[^P][ST]", seq):
            cdr_sequons.append(f"{name}:{seq[p:p+3]}@{p}")
    if cdr_sequons:
        return False, "cdr_glycosylation:" + ",".join(cdr_sequons), {"cdrs": ex["cdrs"]}

    ch, cl = ex["vh"].count("C"), ex["vl"].count("C")
    if ch != qc.CYS_PER_DOMAIN or cl != qc.CYS_PER_DOMAIN:
        return False, f"cysteine_parity:VH{ch}/VL{cl}", {"cdrs": ex["cdrs"]}

    bad = sorted((set(ex["vh"]) | set(ex["vl"])) - qc.AA)
    if bad:
        return False, f"alphabet:{bad}", {}

    if not (qc.VH_LEN[0] <= len(ex["vh"]) <= qc.VH_LEN[1]):
        return False, f"vh_length:{len(ex['vh'])}", {}
    if not (qc.VL_LEN[0] <= len(ex["vl"]) <= qc.VL_LEN[1]):
        return False, f"vl_length:{len(ex['vl'])}", {}

    return True, "clean", {"cdrs": ex["cdrs"], "vh": ex["vh"], "vl": ex["vl"]}


def prefilter(in_dir, out_dir, report=None, verbose=True):
    in_dir, out_dir = Path(in_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdbs = sorted(in_dir.glob("*.pdb"))
    kept, rejected, reasons = [], [], {}
    for p in pdbs:
        ok, reason, _ = evaluate(p)
        if ok:
            shutil.copy2(p, out_dir / p.name)   # COPY -- raw dir untouched
            kept.append(p.name)
        else:
            rejected.append(p.name)
            reasons[p.name] = reason
    if verbose:
        n = len(pdbs)
        pct = (100.0 * len(kept) / n) if n else 0.0
        print(f"[prefilter] {in_dir}: {len(kept)}/{n} clean ({pct:.0f}%), "
              f"{len(rejected)} rejected pre-RF2")
        from collections import Counter
        c = Counter(r.split(":")[0] for r in reasons.values())
        for k, v in c.most_common():
            print(f"             {k}: {v}")
    rep = {"in_dir": str(in_dir), "out_dir": str(out_dir),
           "n_in": len(pdbs), "n_kept": len(kept), "n_rejected": len(rejected),
           "kept": kept, "rejected_reasons": reasons}
    if report:
        Path(report).write_text(json.dumps(rep, indent=2))
    return rep


def self_test():
    import tempfile
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    d = Path(tempfile.mkdtemp())

    def write(path, vh, vl, cdr_spans):
        """cdr_spans: {loop: (abs_start, abs_end)} 1-indexed inclusive."""
        lines, s = [], 1
        rev = {v: k for k, v in hv.tp.THREE2ONE.items()}
        for chain, seq, start in (("H", vh, 1), ("L", vl, len(vh) + 1)):
            for i, aa in enumerate(seq):
                three = rev[aa]
                for an in ("N", "CA", "C", "CB"):
                    nm4 = f" {an:<3s}"
                    lines.append(f"ATOM  {s:5d} {nm4}{'':1s}{three:>3s} "
                                 f"{chain}{start+i:4d}{'':4s}"
                                 f"{i*3.0:8.3f}{0.0:8.3f}{0.0:8.3f}"
                                 f"{1.00:6.2f}{0.00:6.2f}{'':10s}{an[0]:>2s}\n")
                    s += 1
        for loop, (a, b) in cdr_spans.items():
            for i in range(a, b + 1):
                lines.append(f"REMARK PDBinfo-LABEL: {i:4d} {loop}\n")
        path.write_text("".join(lines))

    # VH 110 aa with 2 Cys, VL 105 aa with 2 Cys
    vh_clean = ("ACDEFGHIKLMNPQRSTVWY" * 6)[:110]
    vh_clean = vh_clean.replace("C", "A")
    vh_clean = "AC" + vh_clean[2:]
    vh_clean = vh_clean[:50] + "C" + vh_clean[51:]
    vl_clean = ("ADEFGHIKLMNPQRSTVWY" * 6)[:105]
    vl_clean = "AC" + vl_clean[2:]
    vl_clean = vl_clean[:50] + "C" + vl_clean[51:]

    src = d / "in"
    src.mkdir()
    # a clean design: CDR H1 = positions 21-27 (no sequon)
    write(src / "clean.pdb", vh_clean[:20] + "AAAAAAA" + vh_clean[27:], vl_clean,
          {"H1": (21, 27)})
    # a sequon design: CDR H1 contains NIT
    write(src / "sequon.pdb", vh_clean[:20] + "GFNITDT" + vh_clean[27:], vl_clean,
          {"H1": (21, 27)})
    # odd cysteine count
    write(src / "cys.pdb", vh_clean[:20] + "AAAAAAC" + vh_clean[27:], vl_clean,
          {"H1": (21, 27)})

    k_clean, r_clean, _ = evaluate(src / "clean.pdb")
    k_seq, r_seq, _ = evaluate(src / "sequon.pdb")
    k_cys, r_cys, _ = evaluate(src / "cys.pdb")
    check("clean design is kept", k_clean)
    check("CDR sequon NIT is rejected", not k_seq and r_seq.startswith("cdr_glycosylation"))
    check("sequon reason names the loop and motif", "H1:NIT" in r_seq)
    check("odd Cys count is rejected", not k_cys and r_cys.startswith("cysteine_parity"))

    out = d / "clean_out"
    rep = prefilter(src, out, verbose=False)
    check("prefilter keeps exactly the clean design", rep["n_kept"] == 1)
    check("prefilter rejects the other two", rep["n_rejected"] == 2)
    check("clean design was COPIED to the output dir", (out / "clean.pdb").exists())
    check("RAW input directory is untouched (all 3 files still present)",
          len(list(src.glob("*.pdb"))) == 3)
    check("rejected designs are NOT copied forward",
          not (out / "sequon.pdb").exists())
    check("report records a reason for every rejection",
          set(rep["rejected_reasons"]) == {"sequon.pdb", "cys.pdb"})

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--in", dest="indir")
    ap.add_argument("--out", dest="outdir")
    ap.add_argument("--report")
    a = ap.parse_args()
    if a.self_test:
        print("07_prefilter.py self-test (synthetic PDBs)")
        sys.exit(0 if self_test() else 1)
    if not (a.indir and a.outdir):
        ap.error("need --in and --out")
    prefilter(a.indir, a.outdir, a.report)


if __name__ == "__main__":
    main()
