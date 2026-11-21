#!/usr/bin/env python
"""
02_epitopes.py -- freeze E1 and score/rank candidate patches for E2 and E3.

Spec: docs/TARGET_PREP.md section 6.

E1 is the IL-4 competitive site, computed in 01_target_prep.py. Here we pick its
hotspots. E2/E3 are the best-scoring alternate surface patches after masking.

Scoring axes (TARGET_PREP.md section 6):
  - burialable area (needs >= ~600 A^2 for an Fv paratope)
  - hydrophobic content (RFantibody README: ">~3 hydrophobic residues", charged-polar
    sites are hard)
  - local rigidity: crystallographic B-factor, and 1IAR-vs-3BPN backbone agreement
  - convexity (moderately convex/flat suits CDR loops; deep concavity does not)
  - separation from E1, so the arms are genuinely independent shots

Run:  conda run -n boltz python scripts/02_epitopes.py
Test: conda run -n boltz python scripts/02_epitopes.py --self-test
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "tp", str(Path(__file__).with_name("01_target_prep.py"))
)
tp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tp)

BDIL4R = tp.BDIL4R
TARGET = tp.TARGET
RAW = tp.RAW

HYDROPHOBIC = set("AVLIMFWYC")
FV_PATCH_RADIUS = 11.0      # Cbeta radius approximating an Fv paratope footprint
MIN_PATCH_AREA = 600.0      # A^2, TARGET_PREP.md section 6
MIN_HYDROPHOBIC = 3         # RFantibody README
MIN_E1_SEPARATION = 18.0    # A between patch centroids, so arms are independent
SURFACE_SASA_MIN = 20.0     # A^2 absolute, to count as a surface residue
HOTSPOT_MIN_SASA = 30.0     # A^2 absolute. A buried residue cannot be a hotspot.

_assert = tp._assert
PrepError = tp.PrepError


# ---------------------------------------------------------------- helpers

def load_bfactors(path, chain):
    """Mean backbone B-factor per residue."""
    acc = {}
    with open(path) as fh:
        for line in fh:
            if not line.startswith("ATOM") or line[21] != chain:
                continue
            if line[12:16].strip() not in ("N", "CA", "C", "O"):
                continue
            acc.setdefault(int(line[22:26]), []).append(float(line[60:66]))
    return {k: float(np.mean(v)) for k, v in acc.items()}


def kabsch_rmsd_per_residue(ref, mob):
    """Superpose mob onto ref on shared resnums (CA), return per-residue deviation.

    Both structures use the same PDB numbering (offset +25 to UniProt), verified in
    01_target_prep.py, so resnum is a safe join key. Asserted non-empty -- a silent
    empty join is the exact class of bug in CLAUDE.md section 6 trap 5.
    """
    shared = sorted(set(ref) & set(mob))
    _assert(len(shared) >= 50,
            f"only {len(shared)} shared residues between structures; join looks broken")
    P = np.array([ref[r] for r in shared])
    Q = np.array([mob[r] for r in shared])
    Pc, Qc = P - P.mean(0), Q - Q.mean(0)
    V, S, Wt = np.linalg.svd(Pc.T @ Qc)
    d = np.sign(np.linalg.det(V @ Wt))
    D = np.diag([1.0, 1.0, d])
    R = V @ D @ Wt
    Qr = Qc @ R.T
    dev = np.linalg.norm(Pc - Qr, axis=1)
    return dict(zip(shared, dev)), float(np.sqrt((dev ** 2).mean()))


def convexity(seed_cb, patch_cb, all_cb):
    """Protrusion score: fraction of a 12 A sphere around the patch centroid that is
    NOT filled by protein. Higher = more convex/exposed; low = buried in a cleft.
    """
    cen = patch_cb.mean(axis=0)
    n_near = int((np.linalg.norm(all_cb - cen, axis=1) <= 12.0).sum())
    return 1.0 - min(n_near / 60.0, 1.0)


def build_patch(seed, cands, cb, radius=FV_PATCH_RADIUS):
    return [p for p in cands if np.linalg.norm(cb[p] - cb[seed]) <= radius]


def score_patch(members, seq, sasa, bfac, dev, cb, all_cb, e1_centroid):
    area = float(sum(sasa.get(p, 0.0) for p in members))
    hyd = [p for p in members if seq[p - 1] in HYDROPHOBIC]
    chg = [p for p in members if seq[p - 1] in "DEKR"]
    pcb = np.array([cb[p] for p in members])
    cen = pcb.mean(axis=0)
    b = float(np.mean([bfac.get(p, np.nan) for p in members]))
    d = [dev.get(p) for p in members if p in dev]
    agree = float(np.mean(d)) if d else float("nan")
    conv = convexity(cb[members[0]], pcb, all_cb)
    sep = float(np.linalg.norm(cen - e1_centroid))
    return {
        "n": len(members),
        "area": round(area, 1),
        "n_hydrophobic": len(hyd),
        "frac_hydrophobic": round(len(hyd) / len(members), 3),
        "n_charged": len(chg),
        "mean_bfactor": round(b, 1),
        "mean_dev_1IAR_vs_3BPN": round(agree, 2) if agree == agree else None,
        "convexity": round(conv, 3),
        "sep_from_E1": round(sep, 1),
        "centroid": [round(float(x), 2) for x in cen],
        "members_pdb": members,
        "hydrophobic_pdb": hyd,
    }


def composite_score(s):
    """Weighted rank score. All weights are OUR choice -- label [ASSUMPTION] in methods."""
    if s["area"] < MIN_PATCH_AREA:
        return None, "area below 600 A^2"
    if s["n_hydrophobic"] < MIN_HYDROPHOBIC:
        return None, f"only {s['n_hydrophobic']} hydrophobic residues (need >= {MIN_HYDROPHOBIC})"
    if s["sep_from_E1"] < MIN_E1_SEPARATION:
        return None, f"centroid only {s['sep_from_E1']} A from E1 -- not an independent site"
    dev = s["mean_dev_1IAR_vs_3BPN"]
    score = (
        0.30 * min(s["area"] / 900.0, 1.0)
        + 0.30 * min(s["frac_hydrophobic"] / 0.45, 1.0)
        + 0.15 * (1.0 - min(s["mean_bfactor"] / 80.0, 1.0))
        + 0.15 * (1.0 - min((dev if dev is not None else 3.0) / 3.0, 1.0))
        + 0.10 * s["convexity"]
    )
    return round(score, 4), None


def pick_hotspots(members, seq, sasa, cb, n=4, min_sasa=HOTSPOT_MIN_SASA):
    """3-5 hotspots: high unbound side-chain SASA, central not rim, hydrophobic-leaning.

    RFantibody README: "more sensitive to exactly which hotspots are selected than
    vanilla RFdiffusion ... will generally just generate an undocked antibody if a bad
    set of hotspots is given."

    HARD GATE: a residue below `min_sasa` A^2 in the unbound receptor is buried and
    cannot be contacted by a CDR loop. Scoring it on centrality and hydrophobicity will
    happily rank a buried core residue first -- that happened on the first run (Y38,
    SASA 7.6 A^2, was selected). Buried residues are excluded before ranking, not
    down-weighted.
    """
    pcb = np.array([cb[p] for p in members])
    cen = pcb.mean(axis=0)
    eligible = [p for p in members if sasa.get(p, 0.0) >= min_sasa]
    _assert(len(eligible) >= n,
            f"only {len(eligible)} of {len(members)} patch residues are exposed enough "
            f"(>= {min_sasa} A^2) to be hotspots; need {n}")
    rows = []
    for p in eligible:
        centrality = 1.0 - min(float(np.linalg.norm(cb[p] - cen)) / 14.0, 1.0)
        exposure = min(sasa.get(p, 0.0) / 140.0, 1.0)
        hydro = 1.0 if seq[p - 1] in HYDROPHOBIC else 0.0
        rows.append((0.40 * exposure + 0.35 * centrality + 0.25 * hydro, p))
    rows.sort(reverse=True)
    chosen = [p for _, p in rows[:n]]
    for p in chosen:
        _assert(sasa.get(p, 0.0) >= min_sasa,
                f"hotspot pdb {p} has SASA {sasa.get(p,0.0):.1f} < {min_sasa}")
    return chosen, rows


# ---------------------------------------------------------------- main

def run(verbose=True):
    def log(*a):
        if verbose:
            print(*a)

    rep = json.loads((TARGET / "target_prep_report.json").read_text())
    nm = json.loads((TARGET / "numbering_map.json").read_text())
    seq = nm["sequence_seqres"]
    offset = rep["numbering_offset_uniprot_minus_pdb"]
    to_unp = lambda p: p + offset  # noqa: E731

    ch = tp.parse_pdb(RAW / "1IAR.pdb", chains={"A", "B"})
    rec = ch["B"]
    byn = {r.resnum: r for r in rec}
    cb = {p: byn[p].cbeta() for p in byn if byn[p].cbeta() is not None}
    all_cb = np.array(list(cb.values()))
    sasa = tp.sasa_per_residue(rec)
    bfac = load_bfactors(RAW / "1IAR.pdb", "B")

    # 1IAR vs 3BPN backbone agreement (rigidity / conformational certainty)
    ref_ca = {r.resnum: r.atoms["CA"] for r in rec if "CA" in r.atoms}
    dev, rms = {}, None
    bpn = RAW / "3BPN.pdb"
    if bpn.exists():
        mob = tp.parse_pdb(bpn, chains={"B"})["B"]
        mob_ca = {r.resnum: r.atoms["CA"] for r in mob if "CA" in r.atoms}
        dev, rms = kabsch_rmsd_per_residue(ref_ca, mob_ca)
        log(f"[xcheck] 1IAR vs 3BPN chain B: {len(dev)} shared residues, "
            f"global CA RMSD {rms:.2f} A")

    masked = set(rep["glycan_masked_pdb"])
    memb = set(rep["membrane_proximal_pdb"])
    e1 = rep["E1_pdb"]
    e1_cen = np.array([cb[p] for p in e1]).mean(axis=0)

    # ---------------- E1 hotspots ----------------
    log(f"\n[E1] {len(e1)} residues: " + " ".join(f"{seq[p-1]}{to_unp(p)}" for p in e1))
    # restrict hotspots to the best Fv-sized sub-site inside E1
    best_sub, best_key = None, None
    for s in e1:
        sub = build_patch(s, e1, cb)
        key = (len([p for p in sub if seq[p - 1] in HYDROPHOBIC]),
               sum(sasa.get(p, 0) for p in sub))
        if best_key is None or key > best_key:
            best_key, best_sub = key, sub
    log(f"[E1] best Fv-sized sub-site ({best_key[0]} hydrophobic, {best_key[1]:.0f} A^2): "
        + " ".join(f"{seq[p-1]}{to_unp(p)}" for p in best_sub))
    hs, ranked = pick_hotspots(best_sub, seq, sasa, cb, n=4)
    log("[E1] hotspot ranking (score, residue, SASA):")
    for sc, p in ranked:
        mark = "  <-- CHOSEN" if p in hs else ""
        log(f"       {sc:.3f}  {seq[p-1]}{to_unp(p)} (pdb {p})  SASA={sasa.get(p,0):6.1f}{mark}")
    log(f"[E1] HOTSPOTS (pdb): {sorted(hs)}")
    log(f"[E1] HOTSPOTS (uniprot): {[f'{seq[p-1]}{to_unp(p)}' for p in sorted(hs)]}")

    e1_json = {
        "_provenance": {
            "script": "scripts/02_epitopes.py",
            "definition": "1IAR chain B residues with any heavy atom within 5.0 A of any "
                          "IL-4 (chain A) heavy atom, minus glycan mask, minus membrane-proximal mask",
            "structure": "1IAR", "chain": "B",
            "numbering": "PDB (1IAR chain B). uniprot = pdb + 25",
            "glycan_mask_radius": rep["glycan_mask_radius_angstrom"],
            "hotspot_rule": "0.40*exposure + 0.35*centrality + 0.25*hydrophobic, "
                            "restricted to the best Fv-sized sub-site. [ASSUMPTION: our weights]",
            "literature_crosscheck": "A third-party patent reports an epitope at L39,F41,L42,"
                                     "L43,D72,Y74. All six residue identities match 1IAR chain B "
                                     "PDB numbering exactly and none match UniProt numbering, so "
                                     "that patent uses mature/PDB numbering. L42,L43 are in E1. "
                                     "Used as evidence of antibody accessibility ONLY -- no "
                                     "sequence from it is used anywhere.",
        },
        "description": "IL-4/IL-13 competitive site -- IL-4 contact surface on IL-4Ralpha",
        "residues_pdb": e1,
        "residues_uniprot": [to_unp(p) for p in e1],
        "residues_labelled": [f"{seq[p-1]}{to_unp(p)}" for p in e1],
        "fv_subsite_pdb": sorted(best_sub),
        "hotspots_pdb": sorted(hs),
        "hotspots_uniprot": [to_unp(p) for p in sorted(hs)],
        "hotspots_labelled": [f"{seq[p-1]}{to_unp(p)}" for p in sorted(hs)],
        "frozen": True,
    }

    # ---------------- E2 / E3 patch scoring ----------------
    cands = [p for p in cb
             if p not in masked and p not in memb and p not in set(e1)
             and sasa.get(p, 0.0) >= SURFACE_SASA_MIN]
    log(f"\n[patch] {len(cands)} candidate surface residues after masks and E1 removal")

    rows = []
    for s in cands:
        members = build_patch(s, cands, cb)
        if len(members) < 5:
            continue
        st = score_patch(members, seq, sasa, bfac, dev, cb, all_cb, e1_cen)
        sc, reject = composite_score(st)
        st.update(seed_pdb=s, seed_label=f"{seq[s-1]}{to_unp(s)}",
                  score=sc, rejected_because=reject)
        rows.append(st)

    passing = sorted([r for r in rows if r["score"] is not None],
                     key=lambda r: -r["score"])
    log(f"[patch] {len(rows)} patches scored, {len(passing)} passed the hard gates")

    # non-redundant selection: E2 best, E3 best that is well separated from E2
    chosen = []
    for r in passing:
        if all(np.linalg.norm(np.array(r["centroid"]) - np.array(c["centroid"])) >= 14.0
               for c in chosen):
            chosen.append(r)
        if len(chosen) == 2:
            break

    log("\n[patch] top 8 patches:")
    log(f"  {'seed':>8} {'score':>6} {'n':>3} {'area':>6} {'hyd':>4} {'B':>6} "
        f"{'dev':>5} {'conv':>5} {'sepE1':>6}")
    for r in passing[:8]:
        log(f"  {r['seed_label']:>8} {r['score']:6.3f} {r['n']:3d} {r['area']:6.0f} "
            f"{r['n_hydrophobic']:4d} {r['mean_bfactor']:6.1f} "
            f"{str(r['mean_dev_1IAR_vs_3BPN']):>5} {r['convexity']:5.2f} {r['sep_from_E1']:6.1f}")

    epi = {"E1": e1_json}
    for i, r in enumerate(chosen, start=2):
        name = f"E{i}"
        hs_i, _ = pick_hotspots(r["members_pdb"], seq, sasa, cb, n=4)
        log(f"\n[{name}] seed {r['seed_label']}  score={r['score']}  "
            f"{r['n']} residues, {r['area']:.0f} A^2, {r['n_hydrophobic']} hydrophobic")
        log(f"[{name}] residues: " + " ".join(f"{seq[p-1]}{to_unp(p)}" for p in r["members_pdb"]))
        log(f"[{name}] HOTSPOTS: {[f'{seq[p-1]}{to_unp(p)}' for p in sorted(hs_i)]}")
        epi[name] = {
            "_provenance": {
                "script": "scripts/02_epitopes.py",
                "definition": f"best-scoring alternate surface patch (rank {i-1}), "
                              f"{FV_PATCH_RADIUS} A Cbeta patch around seed {r['seed_label']}",
                "numbering": "PDB (1IAR chain B). uniprot = pdb + 25",
                "gates": f"area >= {MIN_PATCH_AREA}, hydrophobic >= {MIN_HYDROPHOBIC}, "
                         f"centroid >= {MIN_E1_SEPARATION} A from E1",
                "weights": "[ASSUMPTION] 0.30 area, 0.30 hydrophobic frac, 0.15 B-factor, "
                           "0.15 1IAR/3BPN agreement, 0.10 convexity",
            },
            "description": f"Alternate surface patch rank {i-1}, seed {r['seed_label']}",
            "score": r["score"],
            "metrics": {k: r[k] for k in
                        ("n", "area", "n_hydrophobic", "frac_hydrophobic", "n_charged",
                         "mean_bfactor", "mean_dev_1IAR_vs_3BPN", "convexity", "sep_from_E1")},
            "residues_pdb": r["members_pdb"],
            "residues_uniprot": [to_unp(p) for p in r["members_pdb"]],
            "residues_labelled": [f"{seq[p-1]}{to_unp(p)}" for p in r["members_pdb"]],
            "hotspots_pdb": sorted(hs_i),
            "hotspots_uniprot": [to_unp(p) for p in sorted(hs_i)],
            "hotspots_labelled": [f"{seq[p-1]}{to_unp(p)}" for p in sorted(hs_i)],
            "frozen": True,
        }

    # every epitope must assert zero intersection with the masks
    for name, e in epi.items():
        rs = set(e["residues_pdb"])
        _assert(not (rs & masked), f"{name} intersects the glycan mask")
        _assert(not (rs & memb), f"{name} intersects the membrane-proximal mask")
    log("\n[assert] all epitopes have zero intersection with glycan and membrane masks")

    return epi, rows, dict(seq=seq, to_unp=to_unp, rms=rms)


def write(epi, rows, ctx):
    d = TARGET / "epitopes"
    d.mkdir(parents=True, exist_ok=True)
    for name, e in epi.items():
        (d / f"{name}.json").write_text(json.dumps(e, indent=2))
        print(f"[write] {d/f'{name}.json'}")
    cols = ["seed_pdb", "seed_label", "score", "rejected_because", "n", "area",
            "n_hydrophobic", "frac_hydrophobic", "n_charged", "mean_bfactor",
            "mean_dev_1IAR_vs_3BPN", "convexity", "sep_from_E1", "members_pdb"]
    out = TARGET / "patch_scoring.tsv"
    with open(out, "w") as w:
        w.write("\t".join(cols) + "\n")
        for r in sorted(rows, key=lambda x: (x["score"] is None, -(x["score"] or 0))):
            w.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")
    print(f"[write] {out}  ({len(rows)} patches, including rejected)")


# ---------------------------------------------------------------- self-test

def self_test():
    ok = []

    def check(name, fn, should_raise=False):
        try:
            fn()
            passed = not should_raise
        except (PrepError, AssertionError) as e:
            passed = should_raise
            if not passed:
                print(f"   err: {e}")
        ok.append(passed)
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    # composite_score hard gates
    base = dict(area=800.0, n_hydrophobic=5, frac_hydrophobic=0.4, sep_from_E1=25.0,
                mean_bfactor=40.0, mean_dev_1IAR_vs_3BPN=1.0, convexity=0.5)
    check("gate: good patch scores", lambda: _assert(composite_score(dict(base))[0] is not None, "x"))
    check("gate: small area rejected",
          lambda: _assert(composite_score(dict(base, area=400.0))[0] is None, "x"))
    check("gate: too few hydrophobics rejected",
          lambda: _assert(composite_score(dict(base, n_hydrophobic=2))[0] is None, "x"))
    check("gate: patch too close to E1 rejected",
          lambda: _assert(composite_score(dict(base, sep_from_E1=5.0))[0] is None, "x"))
    check("gate: better patch outscores worse patch",
          lambda: _assert(
              composite_score(dict(base, frac_hydrophobic=0.45))[0]
              > composite_score(dict(base, frac_hydrophobic=0.10))[0], "x"))
    check("gate: rigid (low B) outscores floppy (high B)",
          lambda: _assert(composite_score(dict(base, mean_bfactor=20.0))[0]
                          > composite_score(dict(base, mean_bfactor=90.0))[0], "x"))

    # kabsch: identical coords -> ~0 rmsd; translated -> ~0; scrambled -> >0
    rng = np.random.default_rng(0)
    xyz = {i: rng.normal(size=3) * 10 for i in range(100)}
    check("kabsch: identical structures give ~0 RMSD",
          lambda: _assert(kabsch_rmsd_per_residue(xyz, xyz)[1] < 1e-6, "nonzero"))
    check("kabsch: pure translation gives ~0 RMSD",
          lambda: _assert(kabsch_rmsd_per_residue(
              xyz, {k: v + np.array([5.0, 0, 0]) for k, v in xyz.items()})[1] < 1e-6, "nonzero"))
    check("kabsch: perturbed structure gives >0 RMSD",
          lambda: _assert(kabsch_rmsd_per_residue(
              xyz, {k: v + rng.normal(size=3) for k, v in xyz.items()})[1] > 0.5, "zero"))
    check("kabsch: near-empty join must RAISE (trap 5, silent empty join)",
          lambda: kabsch_rmsd_per_residue(xyz, {i: xyz[i] for i in range(3)}),
          should_raise=True)

    # build_patch radius behaviour
    cb = {1: np.array([0.0, 0, 0]), 2: np.array([5.0, 0, 0]), 3: np.array([50.0, 0, 0])}
    check("patch: includes near, excludes far",
          lambda: _assert(build_patch(1, [1, 2, 3], cb) == [1, 2], "wrong members"))

    # hotspot picking prefers exposed+central+hydrophobic
    seq = "L" * 10 + "D" * 10
    cbx = {1: np.array([0.0, 0, 0]), 2: np.array([2.0, 0, 0]), 11: np.array([13.0, 0, 0])}
    sas = {1: 150.0, 2: 150.0, 11: 150.0}
    check("hotspots: central hydrophobic beats distal charged",
          lambda: _assert(pick_hotspots([1, 2, 11], seq, sas, cbx, n=1)[0] in ([1], [2]),
                          "picked the rim/charged residue"))
    # the buried-hotspot bug found on the first real run
    buried = {1: 7.6, 2: 150.0, 11: 150.0}
    check("hotspots: buried residue (SASA 7.6) is NEVER chosen",
          lambda: _assert(1 not in pick_hotspots([1, 2, 11], seq, buried, cbx, n=2)[0],
                          "buried residue was selected as a hotspot"))
    check("hotspots: all-buried patch must RAISE rather than return buried hotspots",
          lambda: pick_hotspots([1, 2, 11], seq, {1: 5.0, 2: 5.0, 11: 5.0}, cbx, n=2),
          should_raise=True)

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        print("02_epitopes.py self-test (synthetic input)")
        sys.exit(0 if self_test() else 1)
    epi, rows, ctx = run()
    write(epi, rows, ctx)
    print("\n[done] epitopes frozen")


if __name__ == "__main__":
    main()
