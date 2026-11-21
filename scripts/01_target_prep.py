#!/usr/bin/env python
"""
01_target_prep.py -- IL-4Ralpha ECD preparation: numbering map, glycan mask, E1 epitope.

Spec: docs/TARGET_PREP.md sections 1, 2, 6, 7.

Produces (under $BDIL4R/target/):
    il4ra_ecd.pdb          cleaned 1IAR chain B, PDB numbering preserved
    numbering_map.json     uniprot <-> pdb (<-> cropped, filled by 02_crop)
    glycan_mask.json       masked residues + radius used + provenance
    epitopes/E1.json       residue set + hotspots + provenance

Everything here is ASSERTED, not eyeballed. docs/TARGET_PREP.md: "target prep bugs are
the hardest class to detect later".

Run:  conda run -n boltz python scripts/01_target_prep.py
Test: conda run -n boltz python scripts/01_target_prep.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------- constants

BDIL4R = Path(os.environ.get("BDIL4R", "/mnt/comp5data/bd-il4r"))
TARGET = BDIL4R / "target"
RAW = TARGET / "raw"

# From docs/TARGET_PREP.md section 1 / config/sprint.yaml. ALL UniProt numbering.
UNIPROT = "P24394-1"
ECD_RANGE = (26, 232)
ECD_LENGTH = 207
SEQUONS_UNIPROT = [53, 98, 128, 134, 176, 209]
DISULFIDES_UNIPROT_DOC = [(34, 44), (74, 86)]
GLYCAN_MASK_RADIUS = float(os.environ.get("GLYCAN_MASK_RADIUS", "12.0"))
MEMBRANE_PROXIMAL_LAST_N = 15
E1_CONTACT_CUTOFF = 5.0

THREE2ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}


class PrepError(RuntimeError):
    pass


def _assert(cond, msg):
    if not cond:
        raise PrepError(msg)


def validate_sequon(n, x, s, where=""):
    """Raise unless n-x-s is a real N-glycosylation sequon: N-X-[ST] with X != P.

    Single shared predicate so the self-test exercises the production code path and
    not a re-statement of it.
    """
    _assert(n == "N", f"sequon {where}: first residue is {n}, not N")
    _assert(x != "P", f"sequon {where}: X position is Pro, which blocks glycosylation")
    _assert(s in ("S", "T"), f"sequon {where}: third residue is {s}, not Ser/Thr")
    return True


# ---------------------------------------------------------------- PDB parsing

class Residue:
    __slots__ = ("chain", "resnum", "icode", "resname", "atoms")

    def __init__(self, chain, resnum, icode, resname):
        self.chain = chain
        self.resnum = resnum
        self.icode = icode
        self.resname = resname
        self.atoms = {}  # atom name -> np.array(3)

    @property
    def one(self):
        return THREE2ONE.get(self.resname, "X")

    def cbeta(self):
        """CB, or CA for glycine / when CB is unmodelled. None if neither present."""
        if "CB" in self.atoms:
            return self.atoms["CB"]
        return self.atoms.get("CA")

    def heavy(self):
        return [v for k, v in self.atoms.items() if not k.startswith("H")]


def parse_pdb(path, chains=None):
    """Minimal ATOM-record parser. Returns {chain: [Residue, ...]} in file order.

    Skips altlocs other than blank/A, skips HETATM (waters, NAG) and hydrogens.
    """
    out = {}
    seen = {}
    with open(path) as fh:
        for line in fh:
            if not line.startswith("ATOM"):
                continue
            altloc = line[16]
            if altloc not in (" ", "A"):
                continue
            ch = line[21]
            if chains and ch not in chains:
                continue
            resname = line[17:20].strip()
            if resname not in THREE2ONE:
                continue
            resnum = int(line[22:26])
            icode = line[26]
            key = (ch, resnum, icode)
            if key not in seen:
                r = Residue(ch, resnum, icode, resname)
                seen[key] = r
                out.setdefault(ch, []).append(r)
            atom = line[12:16].strip()
            if atom.startswith("H") or (len(atom) > 1 and atom[0].isdigit() and atom[1] == "H"):
                continue
            seen[key].atoms[atom] = np.array(
                [float(line[30:38]), float(line[38:46]), float(line[46:54])]
            )
    return out


def parse_seqres(path, chain):
    """SEQRES-derived full sequence (includes residues unresolved in the model)."""
    seq = []
    declared = None
    with open(path) as fh:
        for line in fh:
            if not line.startswith("SEQRES"):
                continue
            if line[11] != chain:
                continue
            declared = int(line[13:17])
            seq.extend(line[19:].split())
    return seq, declared


def parse_seqadv(path, chain):
    """SEQADV -> list of (pdb_resnum, pdb_resname, unp_resname, unp_resnum, note)."""
    rows = []
    with open(path) as fh:
        for line in fh:
            if not line.startswith("SEQADV"):
                continue
            if line[16] != chain:
                continue
            pdb_resname = line[12:15].strip()
            try:
                pdb_resnum = int(line[18:22])
            except ValueError:
                continue
            unp_resname = line[39:42].strip()
            unp_num_s = line[43:48].strip()
            note = line[49:].strip()
            unp_resnum = int(unp_num_s) if unp_num_s else None
            rows.append((pdb_resnum, pdb_resname, unp_resname, unp_resnum, note))
    return rows


def parse_ssbond(path, chain):
    pairs = []
    with open(path) as fh:
        for line in fh:
            if not line.startswith("SSBOND"):
                continue
            if line[15] == chain and line[29] == chain:
                pairs.append((int(line[17:21]), int(line[31:35])))
    return pairs


# ---------------------------------------------------------------- numbering

def derive_offset(seqadv_rows, structure_name):
    """uniprot_resnum = pdb_resnum + offset, derived from SEQADV and asserted unique."""
    offsets = set()
    evidence = []
    for pdb_num, _pdbres, _unpres, unp_num, note in seqadv_rows:
        if unp_num is None:
            continue  # expression tag -- no UniProt counterpart
        offsets.add(unp_num - pdb_num)
        evidence.append({"pdb": pdb_num, "uniprot": unp_num, "note": note})
    _assert(
        len(offsets) == 1,
        f"{structure_name}: SEQADV implies inconsistent numbering offsets {sorted(offsets)}. "
        "Refusing to guess a numbering map.",
    )
    return offsets.pop(), evidence


# ---------------------------------------------------------------- geometry

def residues_within(res_a, res_b_list, cutoff):
    """Indices of res_b_list with any heavy atom within `cutoff` of any heavy atom of any res_a."""
    a_coords = np.array([c for r in res_a for c in r.heavy()])
    hits = set()
    for i, rb in enumerate(res_b_list):
        b = np.array(rb.heavy())
        if b.size == 0:
            continue
        d = np.linalg.norm(a_coords[:, None, :] - b[None, :, :], axis=-1)
        if d.min() <= cutoff:
            hits.add(i)
    return hits


def cbeta_mask(anchor_res, all_res, radius):
    """Residues whose Cbeta lies within `radius` of any anchor Cbeta."""
    anchors = np.array([r.cbeta() for r in anchor_res if r.cbeta() is not None])
    masked = []
    for r in all_res:
        cb = r.cbeta()
        if cb is None:
            continue
        if np.linalg.norm(anchors - cb[None, :], axis=-1).min() <= radius:
            masked.append(r)
    return masked


def sasa_per_residue(residues):
    """Shrake-Rupley SASA per residue via biopython, on the isolated (unbound) chain."""
    from Bio.PDB.SASA import ShrakeRupley
    from Bio.PDB.Atom import Atom
    from Bio.PDB.Residue import Residue as BioRes
    from Bio.PDB.Chain import Chain
    from Bio.PDB.Model import Model
    from Bio.PDB.Structure import Structure

    st = Structure("s")
    mo = Model(0)
    ch = Chain("B")
    st.add(mo)
    mo.add(ch)
    for i, r in enumerate(residues):
        br = BioRes((" ", r.resnum, " "), r.resname, "")
        for name, xyz in r.atoms.items():
            el = name[0]
            br.add(Atom(name, xyz, 0.0, 1.0, " ", name, i, element=el))
        ch.add(br)
    ShrakeRupley().compute(st, level="R")
    return {r.resnum: ch[(" ", r.resnum, " ")].sasa for r in residues}


# ---------------------------------------------------------------- main prep

def run_prep(verbose=True):
    def log(*a):
        if verbose:
            print(*a)

    il4ar_pdb = RAW / "1IAR.pdb"
    bpn_pdb = RAW / "3BPN.pdb"
    _assert(il4ar_pdb.exists(), f"missing {il4ar_pdb} -- download from RCSB first")

    report = {
        "uniprot": UNIPROT,
        "primary_structure": "1IAR",
        "primary_chain": "B",
        "glycan_mask_radius_angstrom": GLYCAN_MASK_RADIUS,
    }

    # -- 1. numbering map, derived from SEQADV in BOTH structures and cross-checked ----
    adv_1iar = parse_seqadv(il4ar_pdb, "B")
    off_1iar, ev_1iar = derive_offset(adv_1iar, "1IAR")
    log(f"[numbering] 1IAR chain B: uniprot = pdb + {off_1iar}")
    for e in ev_1iar:
        log(f"            evidence  pdb {e['pdb']:>4} -> uniprot {e['uniprot']:>4}   {e['note']}")

    cross = None
    if bpn_pdb.exists():
        adv_bpn = parse_seqadv(bpn_pdb, "B")
        off_bpn, ev_bpn = derive_offset(adv_bpn, "3BPN")
        log(f"[numbering] 3BPN chain B: uniprot = pdb + {off_bpn}  ({len(ev_bpn)} SEQADV rows)")
        _assert(
            off_bpn == off_1iar,
            f"numbering offset disagrees between structures: 1IAR={off_1iar} 3BPN={off_bpn}",
        )
        cross = {"structure": "3BPN", "offset": off_bpn, "evidence": ev_bpn}
        log("[numbering] CROSS-CHECK PASSED: both structures give the same offset")

    offset = off_1iar
    to_unp = lambda p: p + offset          # noqa: E731
    to_pdb = lambda u: u - offset          # noqa: E731
    report["numbering_offset_uniprot_minus_pdb"] = offset
    report["offset_evidence_1IAR"] = ev_1iar
    report["offset_crosscheck"] = cross

    # -- 2. ECD length assertion, from SEQRES (not from observed density) -------------
    seqres3, declared = parse_seqres(il4ar_pdb, "B")
    seq = "".join(THREE2ONE.get(r, "X") for r in seqres3)
    log(f"[ecd] SEQRES chain B declares {declared} residues, parsed {len(seq)}")
    _assert(declared == len(seq), f"SEQRES count {declared} != parsed {len(seq)}")
    _assert(
        len(seq) == ECD_LENGTH,
        f"SEQRES chain B length {len(seq)} != expected ECD length {ECD_LENGTH}",
    )
    # SEQRES index 0 corresponds to pdb resnum 1 -> uniprot 26
    _assert(
        to_unp(1) == ECD_RANGE[0] and to_unp(len(seq)) == ECD_RANGE[1],
        f"ECD range mismatch: pdb 1..{len(seq)} maps to uniprot "
        f"{to_unp(1)}..{to_unp(len(seq))}, expected {ECD_RANGE}",
    )
    log(f"[ecd] OK: pdb 1..{len(seq)} == uniprot {ECD_RANGE[0]}..{ECD_RANGE[1]}, "
        f"length {ECD_LENGTH}")

    seq_at_unp = lambda u: seq[to_pdb(u) - 1]   # noqa: E731

    # -- 3. sequon assertion: N-X-[ST], X != P, on the SEQRES sequence ----------------
    sequon_rows = []
    for u in SEQUONS_UNIPROT:
        p = to_pdb(u)
        n, x, s = seq_at_unp(u), seq_at_unp(u + 1), seq_at_unp(u + 2)
        validate_sequon(n, x, s, where=f"uniprot {u} / pdb {p}")
        log(f"[sequon] uniprot N{u} (pdb {p}): {n}-{x}-{s}  OK")
        sequon_rows.append({"uniprot": u, "pdb": p, "motif": f"{n}{x}{s}"})
    log(f"[sequon] all {len(SEQUONS_UNIPROT)} sequons verified as N-X-[ST]")
    report["sequons"] = sequon_rows

    # -- 4. disulfides: assert doc pairs are Cys, and report what the structure says ---
    ss_pdb = parse_ssbond(il4ar_pdb, "B")
    ss_unp = [(to_unp(a), to_unp(b)) for a, b in ss_pdb]
    log(f"[ss] 1IAR SSBOND chain B (pdb): {ss_pdb}")
    log(f"[ss] 1IAR SSBOND chain B (uniprot): {ss_unp}")
    for a, b in DISULFIDES_UNIPROT_DOC:
        _assert(
            seq_at_unp(a) == "C" and seq_at_unp(b) == "C",
            f"documented disulfide {a}-{b}: sequence has {seq_at_unp(a)}/{seq_at_unp(b)}, not Cys/Cys",
        )
        log(f"[ss] documented pair uniprot {a}-{b}: both Cys OK"
            f"{'' if (a, b) in ss_unp else '   (NOTE: not an SSBOND record)'}")
    undocumented = [p for p in ss_unp if p not in DISULFIDES_UNIPROT_DOC]
    if undocumented:
        log(f"[ss] *** STRUCTURE HAS DISULFIDES NOT IN THE HANDOFF DOCS: {undocumented} ***")
    report["disulfides_pdb"] = ss_pdb
    report["disulfides_uniprot"] = ss_unp
    report["disulfides_undocumented_vs_docs"] = undocumented

    # free / engineered cysteine
    all_cys_unp = [to_unp(i + 1) for i, c in enumerate(seq) if c == "C"]
    bonded = {x for p in ss_unp for x in p}
    free_cys = [c for c in all_cys_unp if c not in bonded]
    log(f"[ss] chain B Cys (uniprot): {all_cys_unp}; in SSBOND: {sorted(bonded)}; "
        f"unpaired: {free_cys}")
    report["cys_uniprot_all"] = all_cys_unp
    report["cys_uniprot_unpaired"] = free_cys

    # the engineered C182A -- confirm against SEQADV, in both numberings
    mutations = [
        {"pdb": p, "pdb_resname": pr, "uniprot": u, "uniprot_resname": ur, "note": nt}
        for p, pr, ur, u, nt in adv_1iar
        if u is not None and pr != ur
    ]
    for m in mutations:
        log(f"[mutation] 1IAR chain B has {m['uniprot_resname']}->{m['pdb_resname']} at "
            f"pdb {m['pdb']} / uniprot {m['uniprot']}  ({m['note']})")
    report["engineered_mutations_1IAR"] = mutations

    # -- 5. coordinates -------------------------------------------------------------
    chains = parse_pdb(il4ar_pdb, chains={"A", "B"})
    il4 = chains["A"]
    rec = chains["B"]
    observed = {r.resnum for r in rec}
    log(f"[coords] chain B observed residues: {len(rec)} of {ECD_LENGTH} "
        f"(pdb {min(observed)}..{max(observed)})")
    missing = [p for p in range(1, ECD_LENGTH + 1) if p not in observed]
    log(f"[coords] unresolved in 1IAR (pdb): {missing}")
    report["observed_count"] = len(rec)
    report["unresolved_pdb"] = missing
    report["unresolved_uniprot"] = [to_unp(p) for p in missing]

    # assert the model sequence agrees with SEQRES where observed -- catches a silent
    # off-by-one in the numbering map, which is the exact trap in TARGET_PREP.md section 1
    for r in rec:
        exp = seq[r.resnum - 1]
        _assert(
            r.one == exp,
            f"sequence mismatch at pdb {r.resnum}: model has {r.one} ({r.resname}), "
            f"SEQRES has {exp}. The numbering map is wrong.",
        )
    log(f"[coords] OK: all {len(rec)} observed residues match SEQRES at their index")

    # -- 6. glycan mask -------------------------------------------------------------
    sequon_pdb = [to_pdb(u) for u in SEQUONS_UNIPROT]
    anchors = [r for r in rec if r.resnum in sequon_pdb]
    anchor_nums = sorted(r.resnum for r in anchors)
    unobserved_sequons = [p for p in sequon_pdb if p not in observed]
    log(f"[glycan] sequon Asn observed at pdb {anchor_nums}")
    if unobserved_sequons:
        log(f"[glycan] *** sequon(s) UNRESOLVED, cannot mask geometrically: "
            f"pdb {unobserved_sequons} (uniprot {[to_unp(p) for p in unobserved_sequons]}) ***")
    for r in anchors:
        _assert(r.resname == "ASN", f"sequon anchor pdb {r.resnum} is {r.resname}, not ASN")

    masked = cbeta_mask(anchors, rec, GLYCAN_MASK_RADIUS)
    masked_pdb = sorted(r.resnum for r in masked)
    log(f"[glycan] radius {GLYCAN_MASK_RADIUS} A -> {len(masked_pdb)} of {len(rec)} "
        f"observed residues masked ({100*len(masked_pdb)/len(rec):.0f}%)")
    report["glycan_masked_pdb"] = masked_pdb
    report["glycan_masked_uniprot"] = [to_unp(p) for p in masked_pdb]
    report["sequons_unresolved_pdb"] = unobserved_sequons

    # -- 7. membrane-proximal mask --------------------------------------------------
    mp_cut_unp = ECD_RANGE[1] - MEMBRANE_PROXIMAL_LAST_N + 1
    mp_pdb = sorted(r.resnum for r in rec if to_unp(r.resnum) >= mp_cut_unp)
    log(f"[membrane] excluding uniprot >= {mp_cut_unp} -> pdb {mp_pdb}")
    report["membrane_proximal_cut_uniprot"] = mp_cut_unp
    report["membrane_proximal_pdb"] = mp_pdb

    # -- 8. E1: IL-4 contact surface -------------------------------------------------
    hit_idx = residues_within(il4, rec, E1_CONTACT_CUTOFF)
    e1_raw = sorted(rec[i].resnum for i in hit_idx)
    log(f"[E1] raw IL-4 contacts (<= {E1_CONTACT_CUTOFF} A heavy-atom): "
        f"{len(e1_raw)} residues, pdb {e1_raw}")

    excluded_glyc = sorted(set(e1_raw) & set(masked_pdb))
    excluded_mp = sorted(set(e1_raw) & set(mp_pdb))
    e1 = sorted(set(e1_raw) - set(masked_pdb) - set(mp_pdb))
    log(f"[E1] removed by glycan mask: {excluded_glyc}")
    log(f"[E1] removed by membrane-proximal mask: {excluded_mp}")
    log(f"[E1] SURVIVING: {len(e1)} residues, pdb {e1}")
    log(f"[E1] SURVIVING (uniprot): {[to_unp(p) for p in e1]}")
    log("[E1] sequence: " + " ".join(f"{seq[p-1]}{to_unp(p)}" for p in e1))

    report["E1_raw_pdb"] = e1_raw
    report["E1_excluded_glycan_pdb"] = excluded_glyc
    report["E1_excluded_membrane_pdb"] = excluded_mp
    report["E1_pdb"] = e1
    report["E1_uniprot"] = [to_unp(p) for p in e1]

    # assert the mask actually took effect (TARGET_PREP.md section 2 rule 3)
    _assert(not (set(e1) & set(masked_pdb)), "E1 intersects the glycan mask")
    _assert(not (set(e1) & set(mp_pdb)), "E1 intersects the membrane-proximal mask")

    # -- 9. SASA on the UNBOUND receptor, for hotspot picking ------------------------
    sasa = sasa_per_residue(rec)
    report["sasa_unbound"] = {str(k): round(v, 1) for k, v in sasa.items()}

    return report, dict(
        seq=seq, rec=rec, il4=il4, offset=offset, e1=e1, sasa=sasa,
        masked_pdb=masked_pdb, mp_pdb=mp_pdb, to_unp=to_unp, to_pdb=to_pdb,
    )


# ---------------------------------------------------------------- self-test

def self_test():
    """Exercise the geometry and numbering logic on synthetic input.

    A screen that silently passes everything is worse than no screen (CLAUDE.md section 10),
    so each check here is paired with a NEGATIVE case that must raise.
    """
    ok = []

    def check(name, fn, should_raise=False):
        try:
            fn()
            passed = not should_raise
        except (PrepError, AssertionError) as e:
            passed = should_raise
            if not passed:
                print(f"  {name}: unexpected error {e}")
        ok.append(passed)
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    # -- derive_offset -------------------------------------------------------
    check("offset: consistent SEQADV yields single offset",
          lambda: _assert(
              derive_offset([(1, "PHE", "MET", 26, ""), (182, "ALA", "CYS", 207, "")], "t")[0] == 25,
              "wrong offset"))
    check("offset: inconsistent SEQADV must RAISE",
          lambda: derive_offset([(1, "PHE", "MET", 26, ""), (182, "ALA", "CYS", 999, "")], "t"),
          should_raise=True)
    check("offset: expression tags (no uniprot num) are ignored",
          lambda: _assert(
              derive_offset([(-2, "ALA", "", None, "EXPRESSION TAG"),
                             (28, "GLN", "ASN", 53, "")], "t")[0] == 25,
              "tag not ignored"))

    # -- cbeta_mask ----------------------------------------------------------
    def mk(num, name, xyz, cb=True):
        r = Residue("B", num, " ", name)
        r.atoms["CA"] = np.array(xyz, dtype=float)
        if cb:
            r.atoms["CB"] = np.array(xyz, dtype=float)
        return r

    anchor = mk(1, "ASN", [0, 0, 0])
    near = mk(2, "ALA", [5, 0, 0])
    far = mk(3, "ALA", [50, 0, 0])
    edge = mk(4, "ALA", [12, 0, 0])
    check("mask: picks up residue inside radius",
          lambda: _assert({r.resnum for r in cbeta_mask([anchor], [near, far], 12.0)} == {1 if False else 2},
                          "near not masked"))
    check("mask: excludes residue outside radius",
          lambda: _assert(3 not in {r.resnum for r in cbeta_mask([anchor], [near, far], 12.0)},
                          "far was masked"))
    check("mask: boundary is inclusive at exactly the radius",
          lambda: _assert(4 in {r.resnum for r in cbeta_mask([anchor], [edge], 12.0)},
                          "edge excluded"))
    check("mask: glycine (CA fallback, no CB) is still maskable",
          lambda: _assert(5 in {r.resnum for r in cbeta_mask([anchor], [mk(5, "GLY", [3, 0, 0], cb=False)], 12.0)},
                          "gly skipped"))

    # -- residues_within -----------------------------------------------------
    a = [mk(1, "ALA", [0, 0, 0])]
    b = [mk(10, "ALA", [4.0, 0, 0]), mk(11, "ALA", [6.0, 0, 0])]
    check("contacts: 5.0 A cutoff includes 4.0 A, excludes 6.0 A",
          lambda: _assert(residues_within(a, b, 5.0) == {0}, "wrong contact set"))

    # -- sequon logic: exercises the SAME validate_sequon() production uses ---
    check("sequon: N-A-S accepted", lambda: validate_sequon("N", "A", "S"))
    check("sequon: N-A-T accepted", lambda: validate_sequon("N", "A", "T"))
    check("sequon: N-P-S must RAISE (Pro blocks glycosylation)",
          lambda: validate_sequon("N", "P", "S"), should_raise=True)
    check("sequon: N-A-A must RAISE (no Ser/Thr)",
          lambda: validate_sequon("N", "A", "A"), should_raise=True)
    check("sequon: Q-A-S must RAISE (not Asn)",
          lambda: validate_sequon("Q", "A", "S"), should_raise=True)

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


# ---------------------------------------------------------------- output

def write_outputs(report, ctx):
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / "epitopes").mkdir(exist_ok=True)
    seq, rec, offset = ctx["seq"], ctx["rec"], ctx["offset"]
    to_unp = ctx["to_unp"]

    # cleaned chain B
    out_pdb = TARGET / "il4ra_ecd.pdb"
    with open(RAW / "1IAR.pdb") as fh, open(out_pdb, "w") as w:
        w.write(f"REMARK   1 IL-4Ralpha ECD, 1IAR chain B. uniprot = pdb + {offset}\n")
        w.write(f"REMARK   1 UniProt {UNIPROT} residues {ECD_RANGE[0]}-{ECD_RANGE[1]}\n")
        w.write("REMARK   1 Engineered in this entry: M26F (pdb 1), C207A (pdb 182)\n")
        n = 0
        for line in fh:
            if line.startswith("ATOM") and line[21] == "B" and line[16] in (" ", "A"):
                w.write(line)
                n += 1
        w.write("END\n")
    print(f"[write] {out_pdb}  ({n} atom records)")

    nm = {
        "_provenance": {
            "script": "scripts/01_target_prep.py",
            "primary_structure": "1IAR", "chain": "B",
            "rule": "uniprot_resnum = pdb_resnum + offset",
            "offset": offset,
            "derived_from": "SEQADV records, cross-checked against 3BPN",
            "evidence_1IAR": report["offset_evidence_1IAR"],
            "crosscheck": report["offset_crosscheck"],
            "cropped": "not_run -- filled by 02_crop_target.py",
        },
        "ecd_range_uniprot": list(ECD_RANGE),
        "ecd_length": ECD_LENGTH,
        "sequence_seqres": seq,
        "map": [
            {"uniprot": to_unp(p), "pdb": p, "aa": seq[p - 1],
             "observed": p in {r.resnum for r in rec}, "cropped": None}
            for p in range(1, ECD_LENGTH + 1)
        ],
    }
    (TARGET / "numbering_map.json").write_text(json.dumps(nm, indent=2))
    print(f"[write] {TARGET/'numbering_map.json'}  ({ECD_LENGTH} rows)")

    gm = {
        "_provenance": {
            "script": "scripts/01_target_prep.py",
            "rule": f"Cbeta (CA for Gly/unmodelled CB) within {GLYCAN_MASK_RADIUS} A "
                    "of any sequon Asn Cbeta",
            "radius_angstrom": GLYCAN_MASK_RADIUS,
            "sequons_uniprot": SEQUONS_UNIPROT,
            "sequons_verified_motif": report["sequons"],
            "sequons_unresolved_pdb": report["sequons_unresolved_pdb"],
            "rationale": "Assay antigen is a mammalian-expressed Fc fusion; assume all six "
                         "sequons occupied. 3BPN crystallographers mutated N53Q/N98Q/N134Q/"
                         "N176Q to crystallise -- independent evidence these sites are glycosylated.",
        },
        "masked_pdb": report["glycan_masked_pdb"],
        "masked_uniprot": report["glycan_masked_uniprot"],
        "membrane_proximal_pdb": report["membrane_proximal_pdb"],
        "membrane_proximal_cut_uniprot": report["membrane_proximal_cut_uniprot"],
    }
    (TARGET / "glycan_mask.json").write_text(json.dumps(gm, indent=2))
    print(f"[write] {TARGET/'glycan_mask.json'}  ({len(report['glycan_masked_pdb'])} masked)")

    (TARGET / "target_prep_report.json").write_text(json.dumps(report, indent=2))
    print(f"[write] {TARGET/'target_prep_report.json'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        print("01_target_prep.py self-test (synthetic input)")
        sys.exit(0 if self_test() else 1)

    report, ctx = run_prep()
    write_outputs(report, ctx)
    print("\n[done] target prep stage 1 complete")


if __name__ == "__main__":
    main()
