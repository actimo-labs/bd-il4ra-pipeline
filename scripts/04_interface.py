#!/usr/bin/env python
"""
04_interface.py -- (H+L) vs T interface scoring for Fv-antigen complexes.

Spec: docs/PIPELINE.md section 4, docs/RANKING_AND_QC.md section 5.

THE TRAP THIS MODULE EXISTS TO PREVENT
--------------------------------------
An Fv-antigen complex has THREE chains: H, L, T. The H<->L interface scores ~0.9
regardless of whether the antibody binds the antigen, so any GLOBAL interface metric
on this system is dominated by H<->L and is meaningless as a binding signal.

Every metric here is computed on the **(H+L) versus T** chain pair. The chain selection
is ASSERTED, not assumed, on every call. The H<->L interface is also reported --
explicitly labelled as a NEGATIVE CONTROL -- so that a reader can see the thing we are
not scoring and confirm it is large regardless.

Run:  conda run -n boltz python scripts/04_interface.py <pdb> [<pdb> ...]
Test: conda run -n boltz python scripts/04_interface.py --self-test
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

_assert = tp._assert
PrepError = tp.PrepError

CONTACT_CUTOFF = 5.0      # A, heavy atom
CB_CONTACT_CUTOFF = 8.0   # A, Cbeta, the RFantibody hotspot definition


# ---------------------------------------------------------------- SASA

def total_sasa(residues):
    """Total SASA over an arbitrary multi-chain residue list.

    Uses the in-house Shrake-Rupley in 01_target_prep.py. NOT biopython: its wrapper
    mis-handled residue numbers duplicated across chains, which an Fv+target complex
    always has (H1.., L1.., T1..), and produced a negative BSA. See RUNLOG 2026-11-21.
    """
    return float(sum(tp.sasa_per_residue(residues).values()))


# ---------------------------------------------------------------- contacts

def contact_pairs(group_a, group_b, cutoff=CONTACT_CUTOFF):
    """Residue pairs with any heavy-atom pair within cutoff, plus the atom-pair count."""
    pairs, natoms = [], 0
    bcoords = [(r, np.array(r.heavy())) for r in group_b]
    bcoords = [(r, c) for r, c in bcoords if c.size]
    for ra in group_a:
        ca = np.array(ra.heavy())
        if ca.size == 0:
            continue
        for rb, cb in bcoords:
            d = np.linalg.norm(ca[:, None, :] - cb[None, :, :], axis=-1)
            n = int((d <= cutoff).sum())
            if n:
                pairs.append((ra, rb, float(d.min()), n))
                natoms += n
    return pairs, natoms


def score_pair(group_a, group_b, label_a, label_b):
    """BSA and contact metrics for one chain-group pair."""
    pairs, natoms = contact_pairs(group_a, group_b)
    sa = total_sasa(group_a)
    sb = total_sasa(group_b)
    sab = total_sasa(list(group_a) + list(group_b))
    bsa = sa + sb - sab
    return {
        "pair": f"({label_a}) vs {label_b}",
        "bsa_a2": round(bsa, 1),
        "bsa_per_side_a2": round(bsa / 2.0, 1),
        "n_residue_contacts": len(pairs),
        "n_atom_contacts": natoms,
        "contact_residues_a": sorted({f"{r.chain}{r.resnum}" for r, _, _, _ in pairs}),
        "contact_residues_b": sorted({r.resnum for _, r, _, _ in pairs}),
        "min_distance": round(min((d for _, _, d, _ in pairs), default=float("nan")), 2),
    }


# ---------------------------------------------------------------- main API

def build_target_map(target_chain, crop_residues, crop_seq_by_resnum):
    """Map RF2/RFdiffusion output chain-T numbering back to input crop numbering.

    CLAUDE.md trap 4, in the direction that is easy to miss. RFdiffusion renumbers the
    WHOLE complex sequentially across chains -- for our system H=1..119, L=120..225,
    T=226..312 -- so output T numbers have nothing to do with the crop's 1IAR numbering
    (9..188). Comparing them directly silently reports every design as binding
    off-epitope, because the two integer sets simply do not intersect.

    The i-th residue of output chain T is the i-th residue of the sorted crop. We assert
    that correspondence on AMINO ACID IDENTITY for every residue before trusting it, so
    a changed convention fails loudly instead of producing a plausible wrong answer.
    """
    out_res = sorted(target_chain, key=lambda r: r.resnum)
    crop = sorted(crop_residues)
    _assert(len(out_res) == len(crop),
            f"output chain T has {len(out_res)} residues but the crop has {len(crop)}; "
            f"cannot establish a positional mapping")
    mapping, mismatches = {}, []
    for r, p in zip(out_res, crop):
        exp = crop_seq_by_resnum.get(p)
        if exp is not None and r.one != exp:
            mismatches.append((r.resnum, r.one, p, exp))
        mapping[r.resnum] = p
    _assert(not mismatches,
            f"positional target mapping failed identity check at {len(mismatches)} "
            f"position(s), first: output T{mismatches[0][0]}={mismatches[0][1]} vs "
            f"crop T{mismatches[0][2]}={mismatches[0][3]}. The renumbering convention "
            f"changed -- do not trust any epitope accounting until this is fixed."
            if mismatches else "")
    return mapping


def score_hlt(path, epitope_residues=None, hotspots=None, strict=True,
              target_map=None, masked_residues=None):
    """Score one HLT complex. Returns a dict. Asserts the H/L/T chain selection.

    epitope_residues / hotspots: target (chain T) residue numbers, post-crop numbering.
    """
    ch = tp.parse_pdb(path)
    present = set(ch)

    # ---- THE ASSERTION. Everything downstream is meaningless without it. ----
    _assert("T" in present, f"{Path(path).name}: no chain T -- cannot score an interface "
                            f"against the target. Chains present: {sorted(present)}")
    _assert(present <= {"H", "L", "T"},
            f"{Path(path).name}: unexpected chains {sorted(present - {'H','L','T'})}; "
            f"HLT files must contain only H, L and T")
    if strict:
        _assert(present == {"H", "L", "T"},
                f"{Path(path).name}: chains are {sorted(present)}, expected exactly "
                f"H, L and T. A missing light chain silently turns an Fv score into a "
                f"VHH score.")

    binder = [r for c in ("H", "L") if c in ch for r in ch[c]]
    target = ch["T"]
    _assert(len(binder) > 0, f"{Path(path).name}: binder (H+L) is empty")
    _assert(len(target) > 0, f"{Path(path).name}: target (T) is empty")

    res = {
        "pdb": str(path),
        "chains_present": sorted(present),
        "n_H": len(ch.get("H", [])),
        "n_L": len(ch.get("L", [])),
        "n_T": len(target),
        "scored_chain_pair": "(H+L) vs T",
    }

    # ---- the metric that matters ----
    hl_t = score_pair(binder, target, "H+L", "T")
    res["HL_vs_T"] = hl_t

    # ---- per-chain split, to show which chain is doing the binding ----
    if "H" in ch:
        res["H_vs_T"] = score_pair(ch["H"], target, "H", "T")
    if "L" in ch:
        res["L_vs_T"] = score_pair(ch["L"], target, "L", "T")

    # ---- NEGATIVE CONTROL: the interface we must never score on ----
    if "H" in ch and "L" in ch:
        hl = score_pair(ch["H"], ch["L"], "H", "L")
        hl["WARNING"] = ("H<->L is an INTERNAL antibody interface. It is large for every "
                         "Fv, bound or not. Reported as a negative control ONLY. Never "
                         "rank on this, and never on any global metric that includes it.")
        res["H_vs_L_NEGATIVE_CONTROL"] = hl

    # ---- did we hit the epitope we aimed at? ----
    # Remap output T numbering -> input crop numbering FIRST. See build_target_map().
    raw_contacted = set(hl_t["contact_residues_b"])
    if target_map:
        unknown = raw_contacted - set(target_map)
        _assert(not unknown,
                f"{Path(path).name}: contacted target residues {sorted(unknown)} are not "
                f"in the output->crop map")
        contacted = {target_map[p] for p in raw_contacted}
        res["target_numbering"] = {
            "note": "output chain T is renumbered sequentially by RFdiffusion; "
                    "remapped to input crop (1IAR chain B) numbering for all epitope "
                    "and hotspot accounting",
            "output_T_range": [min(target_map), max(target_map)],
            "crop_range": [min(target_map.values()), max(target_map.values())],
        }
        hl_t["contact_residues_b_cropnum"] = sorted(contacted)
    else:
        contacted = raw_contacted
    if epitope_residues:
        inter = sorted(contacted & set(epitope_residues))
        res["epitope"] = {
            "epitope_residues": sorted(epitope_residues),
            "contacted": inter,
            "epitope_contact_frac": round(len(inter) / len(set(epitope_residues)), 3),
            "off_epitope_contacts": sorted(contacted - set(epitope_residues)),
            "on_epitope_frac_of_all_contacts":
                round(len(inter) / len(contacted), 3) if contacted else 0.0,
        }
    # ---- how much of the interface sits on presumed-glycosylated surface? ----
    # The glycan mask filters EPITOPE SELECTION, but masked residues remain physically
    # present in the crop, so nothing stops a design from docking onto them. Measured
    # on real output: 33-43% of each crop is masked surface and designs drift onto it
    # (E2 median 35% of contacts). A design burying a third of its paratope under an
    # assumed glycan will model beautifully and give zero assay signal.
    if masked_residues:
        mset = set(masked_residues)
        on_masked = sorted(contacted & mset)
        res["masked_surface"] = {
            "n_contacts_on_masked": len(on_masked),
            "contacts_on_masked": on_masked,
            "masked_contact_frac": round(len(on_masked) / len(contacted), 3)
                                   if contacted else 0.0,
            "note": "fraction of (H+L) vs T residue contacts falling on glycan-masked "
                    "or membrane-proximal target surface. [ASSUMPTION] the mask itself "
                    "is a 10 A shell around sequon Asn, not a certainty of occlusion.",
        }

    if hotspots:
        # RFantibody's own hotspot definition: mean Cbeta distance to the closest 5
        # binder CDR residues < 8 A. We use the simpler "is it contacted" plus Cbeta.
        bcb = np.array([r.cbeta() for r in binder if r.cbeta() is not None])
        hit = {}
        # key the target residues by CROP numbering so hotspot lookups line up
        if target_map:
            byn = {target_map[r.resnum]: r for r in target if r.resnum in target_map}
        else:
            byn = {r.resnum: r for r in target}
        for p in hotspots:
            if p not in byn or byn[p].cbeta() is None:
                hit[p] = None
                continue
            d = np.sort(np.linalg.norm(bcb - byn[p].cbeta()[None, :], axis=1))[:5]
            hit[p] = round(float(d.mean()), 2)
        res["hotspots"] = {
            "mean_cb_dist_to_nearest5_binder_residues": hit,
            "n_engaged_under_8A": sum(1 for v in hit.values() if v is not None and v < CB_CONTACT_CUTOFF),
            "n_hotspots": len(hotspots),
            "contacted": sorted(set(hotspots) & contacted),
        }

    # ---- a blunt docked / not-docked verdict ----
    res["verdict"] = classify(hl_t, res.get("hotspots"))
    return res


def classify(hl_t, hotspots):
    """Undocked output is the documented symptom of bad hotspots (RFantibody README)."""
    if hl_t["n_residue_contacts"] == 0:
        return "UNDOCKED -- zero (H+L) vs T residue contacts"
    if hl_t["bsa_a2"] < 400:
        return f"WEAK -- only {hl_t['bsa_a2']:.0f} A^2 buried"
    if hotspots and hotspots["n_engaged_under_8A"] == 0:
        return "DOCKED OFF-TARGET -- contacts the target but engages no hotspot"
    return "DOCKED"


# ---------------------------------------------------------------- self-test

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

    import tempfile

    def write_pdb(path, spec):
        """spec: list of (chain, resnum, x, y, z). Strict PDB column layout:
        cols 1-6 ATOM, 7-11 serial, 13-16 atom name, 18-20 resname, 22 chain, 23-26 resseq,
        31-38/39-46/47-54 xyz. Same layout 03_crop_hlt.py writes and round-trips.
        """
        with open(path, "w") as w:
            s = 1
            for chn, num, x, y, z in spec:
                for an, dx in (("N", 0.0), ("CA", 0.6), ("C", 1.2), ("CB", 0.3)):
                    name = f" {an:<3s}"
                    w.write(f"ATOM  {s:5d} {name}{'':1s}{'ALA':>3s} "
                            f"{chn}{num:4d}{'':4s}"
                            f"{x+dx:8.3f}{y:8.3f}{z:8.3f}"
                            f"{1.00:6.2f}{0.00:6.2f}{'':10s}{an[0]:>2s}\n")
                    s += 1
            w.write("END\n")

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)

        # bound: H and L sit right against T
        bound = d / "bound.pdb"
        write_pdb(bound,
                  [("H", i, 0.0, i * 3.0, 0.0) for i in range(1, 6)]
                  + [("L", i, 0.0, i * 3.0, 4.0) for i in range(1, 6)]
                  + [("T", i, 4.0, i * 3.0, 2.0) for i in range(1, 6)])
        # unbound: T translated 60 A away
        unbound = d / "unbound.pdb"
        write_pdb(unbound,
                  [("H", i, 0.0, i * 3.0, 0.0) for i in range(1, 6)]
                  + [("L", i, 0.0, i * 3.0, 4.0) for i in range(1, 6)]
                  + [("T", i, 60.0, i * 3.0, 2.0) for i in range(1, 6)])
        # no light chain
        nol = d / "nol.pdb"
        write_pdb(nol,
                  [("H", i, 0.0, i * 3.0, 0.0) for i in range(1, 6)]
                  + [("T", i, 4.0, i * 3.0, 2.0) for i in range(1, 6)])
        # stray chain
        stray = d / "stray.pdb"
        write_pdb(stray,
                  [("H", i, 0.0, i * 3.0, 0.0) for i in range(1, 6)]
                  + [("L", i, 0.0, i * 3.0, 4.0) for i in range(1, 6)]
                  + [("T", i, 4.0, i * 3.0, 2.0) for i in range(1, 6)]
                  + [("X", i, 9.0, i * 3.0, 2.0) for i in range(1, 3)])

        check("bound complex: non-zero (H+L) vs T contacts",
              lambda: _assert(score_hlt(bound)["HL_vs_T"]["n_residue_contacts"] > 0, "none"))
        check("bound complex: verdict is not UNDOCKED",
              lambda: _assert(not score_hlt(bound)["verdict"].startswith("UNDOCKED"),
                              score_hlt(bound)["verdict"]))
        # classify() thresholds tested directly -- the toy fixture is far too small
        # to bury a realistic 400 A^2, so testing them through it would be meaningless
        check("classify: zero contacts -> UNDOCKED",
              lambda: _assert(classify({"n_residue_contacts": 0, "bsa_a2": 0.0}, None)
                              .startswith("UNDOCKED"), "x"))
        check("classify: contacts but tiny BSA -> WEAK",
              lambda: _assert(classify({"n_residue_contacts": 5, "bsa_a2": 260.0}, None)
                              .startswith("WEAK"), "x"))
        check("classify: good BSA but no hotspot engaged -> DOCKED OFF-TARGET",
              lambda: _assert(classify({"n_residue_contacts": 20, "bsa_a2": 900.0},
                                       {"n_engaged_under_8A": 0}) == "DOCKED OFF-TARGET"
                              or classify({"n_residue_contacts": 20, "bsa_a2": 900.0},
                                          {"n_engaged_under_8A": 0}).startswith("DOCKED OFF"), "x"))
        check("classify: good BSA and hotspots engaged -> DOCKED",
              lambda: _assert(classify({"n_residue_contacts": 20, "bsa_a2": 900.0},
                                       {"n_engaged_under_8A": 3}) == "DOCKED", "x"))
        check("separated target: ZERO (H+L) vs T contacts",
              lambda: _assert(score_hlt(unbound)["HL_vs_T"]["n_residue_contacts"] == 0, "nonzero"))
        check("separated target: verdict UNDOCKED",
              lambda: _assert(score_hlt(unbound)["verdict"].startswith("UNDOCKED"),
                              score_hlt(unbound)["verdict"]))

        # THE CORE POINT: H<->L is large in BOTH, so a global metric cannot tell them apart
        def discriminates():
            b, u = score_hlt(bound), score_hlt(unbound)
            hl_b = b["H_vs_L_NEGATIVE_CONTROL"]["n_residue_contacts"]
            hl_u = u["H_vs_L_NEGATIVE_CONTROL"]["n_residue_contacts"]
            _assert(hl_b > 0 and hl_u > 0,
                    "H<->L should be contacted in both; fixture is wrong")
            _assert(hl_b == hl_u,
                    f"H<->L differs ({hl_b} vs {hl_u}); fixture should hold it constant")
            _assert(b["HL_vs_T"]["n_residue_contacts"]
                    != u["HL_vs_T"]["n_residue_contacts"],
                    "(H+L) vs T failed to discriminate bound from unbound")
        check("H<->L is IDENTICAL bound vs unbound, while (H+L) vs T differs "
              "-- the whole reason for this module", discriminates)

        check("missing light chain must RAISE in strict mode",
              lambda: score_hlt(nol), should_raise=True)
        check("missing light chain is allowed when strict=False",
              lambda: _assert(score_hlt(nol, strict=False)["n_L"] == 0, "x"))
        check("unexpected extra chain must RAISE",
              lambda: score_hlt(stray), should_raise=True)

        # epitope accounting
        def epi():
            r = score_hlt(bound, epitope_residues=[1, 2, 3], hotspots=[1, 2])
            _assert(0.0 <= r["epitope"]["epitope_contact_frac"] <= 1.0, "frac out of range")
            _assert(r["hotspots"]["n_hotspots"] == 2, "hotspot count wrong")
        check("epitope and hotspot accounting runs and is in range", epi)

        def maskfrac():
            r = score_hlt(bound, epitope_residues=[1, 2, 3], hotspots=[1, 2],
                          masked_residues=[1, 2, 3, 4, 5])
            _assert(r["masked_surface"]["masked_contact_frac"] == 1.0,
                    "all-masked target should give frac 1.0")
            r2 = score_hlt(bound, epitope_residues=[1, 2, 3], hotspots=[1, 2],
                           masked_residues=[])
            _assert("masked_surface" not in r2, "empty mask should not add the key")
        check("masked-surface accounting: all-masked target gives frac 1.0", maskfrac)

        # BSA sanity: burying surface must be positive when in contact, ~0 when apart
        check("BSA > 0 for the bound complex",
              lambda: _assert(score_hlt(bound)["HL_vs_T"]["bsa_a2"] > 0, "zero"))
        check("BSA ~0 for the separated complex",
              lambda: _assert(abs(score_hlt(unbound)["HL_vs_T"]["bsa_a2"]) < 1.0,
                              f"BSA={score_hlt(unbound)['HL_vs_T']['bsa_a2']}"))
        # the invariant the previous biopython-based implementation violated
        check("BSA is NEVER negative (regression guard for the SASA bug)",
              lambda: _assert(all(score_hlt(f)["HL_vs_T"]["bsa_a2"] >= -1e-6
                                  for f in (bound, unbound)), "negative BSA"))
        check("BSA is unaffected by residue numbers duplicated across chains",
              lambda: _assert(abs(score_hlt(unbound)["HL_vs_T"]["bsa_a2"]) < 1.0,
                              "duplicate resnums across H/L/T corrupted the SASA"))

        # ---- build_target_map: the output-renumbering trap (CLAUDE.md trap 4) ----
        class R:
            def __init__(self, n, o):
                self.resnum, self.one = n, o

        # output T is 226..229, crop is 9,42,43,70 -- disjoint integer sets
        out_T = [R(226, "D"), R(227, "V"), R(228, "Y"), R(229, "L")]
        crop = [9, 42, 43, 70]
        cseq = {9: "D", 42: "V", 43: "Y", 70: "L"}
        check("target map: positional mapping output->crop is built",
              lambda: _assert(build_target_map(out_T, crop, cseq)
                              == {226: 9, 227: 42, 228: 43, 229: 70}, "wrong map"))
        check("target map: order-independent (input list unsorted)",
              lambda: _assert(build_target_map(list(reversed(out_T)), crop, cseq)
                              == {226: 9, 227: 42, 228: 43, 229: 70}, "wrong map"))
        check("target map: residue-identity mismatch must RAISE",
              lambda: build_target_map(out_T, crop, {9: "W", 42: "V", 43: "Y", 70: "L"}),
              should_raise=True)
        check("target map: length mismatch must RAISE",
              lambda: build_target_map(out_T, [9, 42, 43], cseq), should_raise=True)
        check("target map: missing crop sequence is tolerated (identity check skipped)",
              lambda: _assert(build_target_map(out_T, crop, {})[226] == 9, "x"))

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdbs", nargs="*")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--epitope", help="epitope JSON (uses residues_pdb + hotspots_pdb)")
    ap.add_argument("--crop-manifest", help="target/crops/manifest.json")
    ap.add_argument("--epitope-name", default="E1")
    ap.add_argument("--numbering-map", help="target/numbering_map.json, for identity checks")
    ap.add_argument("--glycan-mask", help="target/glycan_mask.json")
    ap.add_argument("--json-out")
    a = ap.parse_args()

    if a.self_test:
        print("04_interface.py self-test (synthetic input)")
        sys.exit(0 if self_test() else 1)

    epi = hs = None
    if a.epitope:
        e = json.loads(Path(a.epitope).read_text())
        epi, hs = e["residues_pdb"], e["hotspots_pdb"]

    crop_res = crop_seq = None
    if a.crop_manifest:
        man = json.loads(Path(a.crop_manifest).read_text())
        crop_res = man[a.epitope_name]["residues_pdb"]
        crop_seq = {}
        if a.numbering_map:
            nm = json.loads(Path(a.numbering_map).read_text())
            full = nm["sequence_seqres"]
            crop_seq = {p: full[p - 1] for p in crop_res}

    masked = None
    if a.glycan_mask:
        g = json.loads(Path(a.glycan_mask).read_text())
        masked = set(g["masked_pdb"]) | set(g.get("membrane_proximal_pdb", []))

    out = []
    for p in a.pdbs:
        try:
            tmap = None
            if crop_res:
                ch = tp.parse_pdb(p)
                tmap = build_target_map(ch["T"], crop_res, crop_seq or {})
            r = score_hlt(p, epitope_residues=epi, hotspots=hs, target_map=tmap,
                          masked_residues=masked)
        except PrepError as e:
            r = {"pdb": p, "error": str(e), "verdict": "ERROR"}
        out.append(r)
        hlt = r.get("HL_vs_T", {})
        print(f"{Path(p).name:<45s} {r['verdict']:<45s} "
              f"BSA={hlt.get('bsa_a2','-'):>8} contacts={hlt.get('n_residue_contacts','-'):>4}"
              + (f" hotspots_engaged={r['hotspots']['n_engaged_under_8A']}/{r['hotspots']['n_hotspots']}"
                 if "hotspots" in r else ""))
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(out, indent=2))
        print(f"\n[write] {a.json_out}")


if __name__ == "__main__":
    main()
