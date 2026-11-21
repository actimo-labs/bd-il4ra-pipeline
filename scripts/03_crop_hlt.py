#!/usr/bin/env python
"""
03_crop_hlt.py -- crop IL-4Ralpha around each epitope and emit RFantibody target files.

Spec: docs/TARGET_PREP.md section 4.

Format verified against the shipped example `scripts/examples/example_inputs/rsv_site3.pdb`:
a target file is a plain PDB with **chain id T**, **no REMARK lines**, and the **original
residue numbering preserved** (that example runs 253..960 with gaps, it is not
renumbered 1..N). So we keep 1IAR chain B PDB numbering and only relabel the chain.

That makes post-crop numbering identical to pre-crop numbering -- but CLAUDE.md trap 4
says hotspots must name the numbering *after* cropping, so this script **asserts** the
identity rather than assuming it, and emits the exact hotspot string to pass to
RFdiffusion so nobody retypes it.

Run:  conda run -n boltz python scripts/03_crop_hlt.py
Test: conda run -n boltz python scripts/03_crop_hlt.py --self-test
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "tp", str(Path(__file__).with_name("01_target_prep.py"))
)
tp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tp)

TARGET = tp.TARGET
RAW = tp.RAW
CROPS = TARGET / "crops"

SHELL_RADIUS = 12.0     # A beyond the epitope, README: "~10A of target on each side"
GAP_FILL = 3            # bridge gaps of <= this many residues to limit chain breaks
MIN_CROP = 40           # sanity floor
MAX_CROP = 160          # RFdiffusion/RF2 are O(N^2); keep the target small

_assert = tp._assert
PrepError = tp.PrepError


def select_crop(epitope_pdb, residues, radius=SHELL_RADIUS, gap_fill=GAP_FILL):
    """Residues within `radius` of any epitope residue, then short gaps bridged."""
    byn = {r.resnum: r for r in residues}
    epi = [byn[p] for p in epitope_pdb if p in byn]
    _assert(len(epi) == len(epitope_pdb),
            f"epitope residues missing from the structure: "
            f"{sorted(set(epitope_pdb) - set(byn))}")
    epi_coords = np.array([c for r in epi for c in r.heavy()])
    keep = set()
    for r in residues:
        h = np.array(r.heavy())
        if h.size == 0:
            continue
        d = np.linalg.norm(epi_coords[:, None, :] - h[None, :, :], axis=-1)
        if d.min() <= radius:
            keep.add(r.resnum)

    # bridge short gaps so we do not fragment secondary structure
    present = sorted(byn)
    ordered = sorted(keep)
    bridged = set(keep)
    for a, b in zip(ordered, ordered[1:]):
        between = [p for p in present if a < p < b]
        if 0 < len(between) <= gap_fill:
            bridged.update(between)
    return sorted(bridged)


def write_target(path, residues, keep, note):
    """Emit chain T, original numbering, no REMARKs -- matching rsv_site3.pdb."""
    byn = {r.resnum: r for r in residues}
    serial = 1
    lines = []
    for p in keep:
        r = byn[p]
        for atom, xyz in r.atoms.items():
            el = atom[0]
            name = f" {atom:<3s}" if len(atom) < 4 else atom
            lines.append(
                f"ATOM  {serial:5d} {name}{'':1s}{r.resname:>3s} T{p:4d}{'':4s}"
                f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}"
                f"{1.00:6.2f}{0.00:6.2f}{'':10s}{el:>2s}\n"
            )
            serial += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as w:
        w.writelines(lines)
        w.write("TER\nEND\n")
    return serial - 1


def verify_target(path, expected_keep, expected_hotspots, seq,
                  min_crop=MIN_CROP, max_crop=MAX_CROP):
    """Re-parse what we wrote and assert it. Never trust the writer."""
    ch = tp.parse_pdb(path)
    _assert(set(ch) == {"T"}, f"{path.name}: chains are {sorted(ch)}, expected exactly ['T']")
    got = sorted(r.resnum for r in ch["T"])
    _assert(got == sorted(expected_keep),
            f"{path.name}: residue set written != residue set intended")
    byn = {r.resnum: r for r in ch["T"]}
    for p in expected_hotspots:
        _assert(p in byn, f"{path.name}: hotspot T{p} is NOT in the crop")
        exp = seq[p - 1]
        _assert(byn[p].one == exp,
                f"{path.name}: hotspot T{p} is {byn[p].one} in the crop but {exp} in SEQRES "
                f"-- numbering is wrong")
    _assert(min_crop <= len(got) <= max_crop,
            f"{path.name}: crop is {len(got)} residues, outside [{min_crop},{max_crop}]")
    return got


def run(verbose=True):
    def log(*a):
        if verbose:
            print(*a)

    nm = json.loads((TARGET / "numbering_map.json").read_text())
    seq = nm["sequence_seqres"]
    offset = nm["_provenance"]["offset"]
    rec = tp.parse_pdb(RAW / "1IAR.pdb", chains={"B"})["B"]

    manifest = {}
    for name in ("E1", "E2", "E3"):
        f = TARGET / "epitopes" / f"{name}.json"
        if not f.exists():
            log(f"[{name}] no epitope file, skipping")
            continue
        e = json.loads(f.read_text())
        epi = e["residues_pdb"]
        hs = e["hotspots_pdb"]

        keep = select_crop(epi, rec)
        out = CROPS / f"{name}_target_HLT.pdb"
        natoms = write_target(out, rec, keep, name)
        got = verify_target(out, keep, hs, seq)

        segs, start = [], got[0]
        for a, b in zip(got, got[1:]):
            if b != a + 1:
                segs.append((start, a))
                start = b
        segs.append((start, got[-1]))

        hotspot_str = ",".join(f"T{p}" for p in sorted(hs))
        log(f"\n[{name}] crop: {len(got)} residues, {natoms} atoms, "
            f"{len(segs)} chain segment(s)")
        log(f"[{name}] segments (pdb): {segs}")
        log(f"[{name}] hotspots verified in crop: "
            + ", ".join(f"T{p}={seq[p-1]}{p} (uniprot {seq[p-1]}{p+offset})" for p in sorted(hs)))
        log(f"[{name}] RFDIFFUSION HOTSPOT STRING: {hotspot_str}")
        log(f"[{name}] -> {out}")

        manifest[name] = {
            "target_pdb": str(out),
            "n_residues": len(got),
            "n_atoms": natoms,
            "segments_pdb": segs,
            "residues_pdb": got,
            "hotspots_pdb": sorted(hs),
            "hotspot_string": hotspot_str,
            "hotspots_labelled_uniprot": e["hotspots_labelled"],
            "numbering": "1IAR chain B PDB numbering, PRESERVED through the crop "
                         "(verified against rsv_site3.pdb convention). uniprot = pdb + 25",
            "shell_radius": SHELL_RADIUS,
            "gap_fill": GAP_FILL,
        }

    # framework: shipped pre-converted, just verify and record
    fw_src = tp.BDIL4R / "rfantibody/scripts/examples/example_inputs/hu-4D5-8_Fv.pdb"
    fw_dst = TARGET / "frameworks" / "hu4D5-8_Fv_HLT.pdb"
    fw_dst.parent.mkdir(parents=True, exist_ok=True)
    fw_dst.write_bytes(fw_src.read_bytes())
    fch = tp.parse_pdb(fw_dst)
    _assert(set(fch) == {"H", "L"},
            f"framework chains are {sorted(fch)}, expected ['H','L']")
    labels = {}
    for line in fw_dst.read_text().splitlines():
        if line.startswith("REMARK PDBinfo-LABEL:"):
            parts = line.split()
            labels.setdefault(parts[-1], []).append(int(parts[-2]))
    _assert(set(labels) == {"H1", "H2", "H3", "L1", "L2", "L3"},
            f"framework CDR REMARKs are {sorted(labels)}, expected all six loops")
    nH, nL = len(fch["H"]), len(fch["L"])
    log(f"\n[framework] hu4D5-8 Fv: H={nH} L={nL} residues, CDR REMARKs present for "
        f"all six loops")
    for k in ("H1", "H2", "H3", "L1", "L2", "L3"):
        v = labels[k]
        log(f"[framework]   {k}: absolute idx {min(v)}-{max(v)} ({len(v)} residues)")
    _assert(max(max(v) for v in labels.values()) <= nH + nL,
            "a CDR REMARK index exceeds the total residue count")
    log(f"[framework] -> {fw_dst}")

    manifest["framework_hu4D5-8"] = {
        "pdb": str(fw_dst),
        "source": "RFantibody scripts/examples/example_inputs/hu-4D5-8_Fv.pdb (ships HLT-formatted)",
        "n_H": nH, "n_L": nL,
        "cdr_labels": {k: [min(v), max(v)] for k, v in labels.items()},
    }
    return manifest


def self_test():
    ok = []

    def check(name, fn, should_raise=False):
        try:
            fn()
            p = not should_raise
        except (PrepError, AssertionError) as e:
            p = should_raise
            if not p:
                print(f"   err: {e}")
        ok.append(p)
        print(f"  [{'PASS' if p else 'FAIL'}] {name}")

    def mk(num, name, x):
        r = tp.Residue("B", num, " ", name)
        r.atoms["CA"] = np.array([float(x), 0.0, 0.0])
        r.atoms["CB"] = np.array([float(x), 1.0, 0.0])
        return r

    # a 1-A-spaced chain; epitope at residue 10
    chain = [mk(i, "ALA", i) for i in range(1, 41)]
    check("crop: picks up the shell around the epitope",
          lambda: _assert(set(select_crop([10], chain, radius=5.0, gap_fill=0))
                          == set(range(5, 16)), "wrong shell"))
    check("crop: excludes residues beyond the shell",
          lambda: _assert(40 not in select_crop([10], chain, radius=5.0, gap_fill=0), "far kept"))
    check("crop: epitope residue absent from structure must RAISE",
          lambda: select_crop([999], chain, radius=5.0), should_raise=True)

    # gap bridging
    split = [mk(i, "ALA", i) for i in range(1, 6)] + [mk(i, "ALA", i + 2) for i in range(6, 11)]
    check("crop: bridges a short gap to limit chain breaks",
          lambda: _assert(len(select_crop([3, 9], split, radius=2.5, gap_fill=3))
                          >= len(select_crop([3, 9], split, radius=2.5, gap_fill=0)),
                          "gap_fill did not add residues"))

    # round-trip write + verify, including the hotspot identity assertion
    import tempfile
    seq = "A" * 40
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.pdb"
        keep = list(range(5, 16))
        write_target(p, chain, keep, "t")
        V = lambda *a, **k: verify_target(*a, min_crop=1, max_crop=1000, **k)  # noqa: E731
        check("io: written file re-parses as exactly one chain T with the right residues",
              lambda: _assert(V(p, keep, [10], seq) == keep, "roundtrip mismatch"))
        check("io: hotspot outside the crop must RAISE",
              lambda: V(p, keep, [30], seq), should_raise=True)
        wrong = "A" * 9 + "W" + "A" * 30   # SEQRES says W at 10, written file has A
        check("io: hotspot identity mismatch must RAISE (numbering guard)",
              lambda: V(p, keep, [10], wrong), should_raise=True)
        check("io: crop outside the size bounds must RAISE",
              lambda: verify_target(p, keep, [10], seq, min_crop=40, max_crop=160),
              should_raise=True)

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        print("03_crop_hlt.py self-test (synthetic input)")
        sys.exit(0 if self_test() else 1)
    man = run()
    out = TARGET / "crops" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(man, indent=2))
    print(f"\n[write] {out}")
    print("[done] crops and framework ready")


if __name__ == "__main__":
    main()
