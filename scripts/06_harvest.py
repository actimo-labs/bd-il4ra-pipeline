#!/usr/bin/env python
"""
06_harvest.py -- walk production output and build candidates.tsv.

Spec: docs/RANKING_AND_QC.md section 7 (manifest schema).

One row per candidate, EVERY candidate ever generated -- not just the 20. Append-only
in spirit: the file is rebuilt from the raw outputs, which are never modified, so it is
reproducible rather than accumulated.

Rules enforced here:
  - a metric that was not computed is literally `not_run` -- never 0, never a guess
  - joins are on FULL candidate ids, asserted non-empty (CLAUDE.md s6 trap 5)
  - CDR definitions come from the HLT REMARK lines (known by construction), and slicing
    the submitted sequence at those indices must reproduce the CDR string or the design
    is quarantined

Run:  conda run -n boltz python scripts/06_harvest.py
Test: conda run -n boltz python scripts/06_harvest.py --self-test
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(HERE / path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tp = _load("tp", "01_target_prep.py")
iface = _load("iface", "04_interface.py")
qc = _load("qc", "qc_liabilities.py")
nov = _load("nov", "05_novelty.py")

BDIL4R = tp.BDIL4R
PROD = BDIL4R / "out" / "production"
TARGET = BDIL4R / "target"

NOT_RUN = "not_run"

COLUMNS = [
    "candidate_id", "epitope_arm", "framework", "generator", "generator_version",
    "parameters_json", "random_seed", "run_id", "vh_seq", "vl_seq", "ch_type", "cl_type",
    "vh_len", "vl_len", "cdr_definitions_json", "rf2_iface_hl_vs_t", "rf2_rank",
    "boltz2_iface_mean5", "boltz2_iface_sd5", "boltz2_rank", "novaatom_iptm",
    "novaatom_refold_rmsd", "cross_family_agree", "bsa_a2", "contact_count",
    "epitope_contact_frac", "liability_penalty", "liability_hits_json", "cys_count_vh",
    "cys_count_vl", "cdr_net_charge", "cdr_gravy", "theoretical_pi", "cdrh3_len",
    "nearest_ref_id", "nearest_ref_cdrh3_identity", "nearest_il4ra_identity",
    "novelty_status", "eligibility_status", "cluster_id", "rank_final", "selected",
    "rejection_reason", "artifact_paths", "notes",
    # extra provenance columns beyond the spec's minimum, all measured
    "rf2_plddt", "rf2_target_aligned_antibody_rmsd", "rf2_framework_aligned_cdr_rmsd",
    "rf2_framework_aligned_H3_rmsd", "hotspots_engaged", "n_hotspots", "verdict",
    "hl_vs_l_bsa_negative_control", "masked_contact_frac", "n_contacts_on_masked",
]


def read_scores(pdb):
    """RF2 embeds its metrics as SCORE lines in the PDB. There is no scorefile."""
    out = {}
    for line in Path(pdb).read_text().splitlines():
        if line.startswith("SCORE"):
            try:
                k, v = line[6:].split(":")
                out[k.strip()] = float(v)
            except ValueError:
                pass
    return out


def read_cdr_labels(pdb):
    """REMARK PDBinfo-LABEL: <1-indexed ABSOLUTE residue index> <loop>."""
    lab = {}
    for line in Path(pdb).read_text().splitlines():
        if line.startswith("REMARK PDBinfo-LABEL:"):
            q = line.split()
            lab.setdefault(q[-1], []).append(int(q[-2]))
    return {k: sorted(v) for k, v in lab.items()}


# hu4D5-8 Fv, the fixed framework every design is built on. Positions outside the CDRs
# must match this exactly; that is what makes the CDR boundaries checkable.
FRAMEWORK_VH = ("EVQLVESGGGLVQPGGSLRLSCAASGFNIKDTYIHWVRQAPGKGLEWVARIYPTNGYTRYADSVKGRFTIS"
                "ADTSKNTAYLQMNSLRAEDTAVYYCSRWGYAMDYWGQGTLVTVSS")
FRAMEWORK_VL = ("DIQMTQSPSSLSASVGDRVTITCRASQDVNTAVAWYQQKPGKAPKLLIYSASFLYSGVPSRFSGSRSGTDFT"
                "LTISSLQPEDFATYYCQQHYTTPPTFGQGTKVEIK")


def check_framework_outside_cdrs(ex, max_mismatch=0):
    """Return a list of problems if non-CDR positions diverge from the framework.

    Independent of how the CDR indices were derived, so it genuinely tests them.
    Compares the N-terminal and C-terminal framework runs flanking the CDR span, which
    are unaffected by CDR length changes.
    """
    problems = []
    for chain, dom, fw in (("VH", ex["vh"], FRAMEWORK_VH), ("VL", ex["vl"], FRAMEWORK_VL)):
        spans = sorted((d["start_idx"], d["end_idx"]) for d in ex["cdr_definitions"].values()
                       if d["chain"] == chain)
        if not spans:
            problems.append(f"{chain}: no CDRs recorded")
            continue
        # leading framework: before the first CDR, indices are shared with the framework
        lead_n = spans[0][0]
        if dom[:lead_n] != fw[:lead_n]:
            problems.append(f"{chain}: {lead_n} residues before the first CDR do not match "
                            f"the hu4D5-8 framework")
        # trailing framework: after the last CDR, align from the C-terminus
        tail_n = len(dom) - spans[-1][1]
        if tail_n > 0 and dom[-tail_n:] != fw[-tail_n:]:
            problems.append(f"{chain}: {tail_n} residues after the last CDR do not match "
                            f"the hu4D5-8 framework")
    return problems


def extract(pdb, reason=None):
    """VH/VL sequences + CDR definitions as 0-based slices into each domain.

    Returns None on failure and, if `reason` is a list, appends a diagnosable message.
    A bare None here would make every quarantine look identical.
    """
    def bail(msg):
        if reason is not None:
            reason.append(msg)
        return None

    ch = tp.parse_pdb(pdb)
    if "H" not in ch or "L" not in ch:
        return bail(f"chains present {sorted(ch)}, need both H and L")
    H = sorted(ch["H"], key=lambda r: r.resnum)
    L = sorted(ch["L"], key=lambda r: r.resnum)
    vh = "".join(r.one for r in H)
    vl = "".join(r.one for r in L)
    nH = len(H)
    lab = read_cdr_labels(pdb)
    if not lab:
        return bail("no REMARK PDBinfo-LABEL lines -- cannot locate CDRs")
    cdrs, defs = {}, {}
    for name, idxs in lab.items():
        chain = "VH" if name.startswith("H") else "VL"
        dom = vh if chain == "VH" else vl
        off = 0 if chain == "VH" else nH
        s0, s1 = idxs[0] - 1 - off, idxs[-1] - off      # 0-based [start, end)
        if s0 < 0 or s1 > len(dom):
            return bail(f"{name} absolute idx {idxs[0]}-{idxs[-1]} maps outside "
                        f"{chain} (len {len(dom)}, offset {off})")
        seg = dom[s0:s1]
        cdrs[name] = seg
        defs[name] = {"chain": chain, "start_idx": s0, "end_idx": s1, "sequence": seg}
    return {"vh": vh, "vl": vl, "cdrs": cdrs, "cdr_definitions": defs, "n_H": nH}


def arm_of(path):
    """Epitope arm from the path. Searched, not positional -- the pilot and production
    layouts differ in depth and a positional index silently picks the wrong token."""
    for part in Path(path).parts:
        for e in ("E1", "E2", "E3"):
            if part == e or part.startswith(e + "_"):
                return e
    return None


def harvest(limit=None, verbose=True, root=None, pattern="*/*/3_rf2/*.pdb"):
    def log(*a):
        if verbose:
            print(*a)

    ref_path = BDIL4R / "novelty" / "reference_set.json"
    ref = json.loads(ref_path.read_text()) if ref_path.exists() else None
    if ref is None:
        log("[warn] no frozen reference set; novelty columns will be not_run")

    crops = json.loads((TARGET / "crops" / "manifest.json").read_text())
    gmp = TARGET / "glycan_mask.json"
    masked = None
    if gmp.exists():
        g = json.loads(gmp.read_text())
        masked = set(g["masked_pdb"]) | set(g.get("membrane_proximal_pdb", []))
    nm = json.loads((TARGET / "numbering_map.json").read_text())
    full_seq = nm["sequence_seqres"]
    epitopes = {}
    for e in ("E1", "E2", "E3"):
        p = TARGET / "epitopes" / f"{e}.json"
        if p.exists():
            epitopes[e] = json.loads(p.read_text())

    base = Path(root) if root else PROD
    pdbs = sorted(base.glob(pattern))
    if limit:
        pdbs = pdbs[:limit]
    log(f"[harvest] {len(pdbs)} RF2 output PDBs under {base}")

    rows, seen_pairs, quarantined = [], set(), 0
    for i, p in enumerate(pdbs, 1):
        arm = arm_of(p)
        if arm is None:
            quarantined += 1
            log(f"  [quarantine] {p}: cannot determine epitope arm from path")
            continue
        batch = p.parts[-3]
        cid = f"{arm}_{batch}_{p.stem.replace('_best', '')}"

        why = []
        ex = extract(p, reason=why)
        if ex is None:
            quarantined += 1
            log(f"  [quarantine] {cid}: {why[0] if why else 'unknown'}")
            continue

        # CDR boundary validation.
        #
        # The previous check compared dom[s0:s1] against a value DEFINED as dom[s0:s1] --
        # a tautology that could never fire. Shifting every CDR boundary by +3 passed it.
        #
        # Real check: we diffuse ONLY the CDRs, so every non-CDR position must still be
        # the hu4D5-8 framework verbatim. If a boundary is wrong, designed residues leak
        # into the framework mask and the comparison breaks. That is an independent test
        # of the boundaries, not a restatement of them.
        bad = check_framework_outside_cdrs(ex)
        if bad:
            quarantined += 1
            log(f"  [quarantine] {cid}: CDR boundaries inconsistent with the fixed "
                f"framework -- {bad}")
            continue

        sc = read_scores(p)
        epi = epitopes.get(arm)

        # interface metrics, with the output->crop renumbering applied
        try:
            chn = tp.parse_pdb(p)
            crop_res = crops[arm]["residues_pdb"]
            tmap = iface.build_target_map(
                chn["T"], crop_res, {q: full_seq[q - 1] for q in crop_res})
            im = iface.score_hlt(p, epitope_residues=epi["residues_pdb"] if epi else None,
                                 hotspots=epi["hotspots_pdb"] if epi else None,
                                 target_map=tmap, masked_residues=masked)
        except Exception as e:
            log(f"  [warn] {cid}: interface scoring failed: {e}")
            im = None

        prov = {"generator": "rfantibody",
                "generator_version": "efe4b9040f051edc229e9318ead586ff76236c9b",
                "parameters_json": json.dumps(
                    {"loops": "H1:7,H2:6,H3:5-13,L1:8-13,L2:7,L3:9-11",
                     "hotspots": crops[arm]["hotspot_string"],
                     "mpnn_temp": 0.2, "rf2_recycles": 10,
                     "diffuser_T": 50}, separators=(",", ":")),
                "random_seed": NOT_RUN,   # not fixed per design in round 1
                "run_id": f"prod_round1_{arm}_{batch}"}

        q = qc.screen(ex["vh"], ex["vl"], ex["cdrs"], seen_pairs, prov)
        seen_pairs.add((ex["vh"], ex["vl"]))

        n = (nov.screen_design(ex["vh"], ex["vl"], ex["cdrs"], ref) if ref
             else {"novelty_status": NOT_RUN, "nearest_ref_id": NOT_RUN,
                   "nearest_ref_cdrh3_identity": NOT_RUN,
                   "nearest_il4ra_identity": NOT_RUN})

        row = {c: NOT_RUN for c in COLUMNS}
        row.update({
            "candidate_id": cid,
            "epitope_arm": arm,
            "framework": "hu4D5-8",
            "generator": prov["generator"],
            "generator_version": prov["generator_version"],
            "parameters_json": prov["parameters_json"],
            "random_seed": prov["random_seed"],
            "run_id": prov["run_id"],
            "vh_seq": ex["vh"], "vl_seq": ex["vl"],
            # exact dropdown values from the official template, NOT "Human Kappa"
            "ch_type": "Human IgG1", "cl_type": "Human Ig Kappa",
            "vh_len": len(ex["vh"]), "vl_len": len(ex["vl"]),
            "cdr_definitions_json": json.dumps(ex["cdr_definitions"], separators=(",", ":")),
            "rf2_iface_hl_vs_t": sc.get("interaction_pae", NOT_RUN),
            "rf2_plddt": sc.get("pred_lddt", NOT_RUN),
            "rf2_target_aligned_antibody_rmsd": sc.get("target_aligned_antibody_rmsd", NOT_RUN),
            "rf2_framework_aligned_cdr_rmsd": sc.get("framework_aligned_cdr_rmsd", NOT_RUN),
            "rf2_framework_aligned_H3_rmsd": sc.get("framework_aligned_H3_rmsd", NOT_RUN),
            "liability_penalty": q["liability_penalty"],
            "liability_hits_json": json.dumps(
                {"motifs": q["motif_hits"], "properties": q["property_hits"]},
                separators=(",", ":")),
            "cys_count_vh": q["cys_count_vh"], "cys_count_vl": q["cys_count_vl"],
            "cdr_net_charge": q["cdr_net_charge"], "cdr_gravy": q["cdr_gravy"],
            "theoretical_pi": f"VH:{q['theoretical_pi_vh']}|VL:{q['theoretical_pi_vl']}",
            "cdrh3_len": q["cdrh3_len"],
            "eligibility_status": q["eligibility_status"],
            "novelty_status": n["novelty_status"],
            "nearest_ref_id": n.get("nearest_ref_id", NOT_RUN),
            "nearest_ref_cdrh3_identity": n.get("nearest_ref_cdrh3_identity", NOT_RUN),
            "nearest_il4ra_identity": n.get("nearest_il4ra_identity", NOT_RUN),
            "artifact_paths": str(p),
            "selected": "no",
            "rejection_reason": ";".join(q["failed_gates"] + n.get("novelty_fails", []))
                                or NOT_RUN,
            "notes": ";".join(n.get("novelty_flags", [])) or NOT_RUN,
        })
        if im:
            row.update({
                "bsa_a2": im["HL_vs_T"]["bsa_a2"],
                "contact_count": im["HL_vs_T"]["n_residue_contacts"],
                "epitope_contact_frac": im.get("epitope", {}).get("epitope_contact_frac", NOT_RUN),
                "hotspots_engaged": im.get("hotspots", {}).get("n_engaged_under_8A", NOT_RUN),
                "n_hotspots": im.get("hotspots", {}).get("n_hotspots", NOT_RUN),
                "verdict": im["verdict"],
                "hl_vs_l_bsa_negative_control":
                    im.get("H_vs_L_NEGATIVE_CONTROL", {}).get("bsa_a2", NOT_RUN),
                "masked_contact_frac":
                    im.get("masked_surface", {}).get("masked_contact_frac", NOT_RUN),
                "n_contacts_on_masked":
                    im.get("masked_surface", {}).get("n_contacts_on_masked", NOT_RUN),
            })
        rows.append(row)
        if verbose and i % 25 == 0:
            log(f"  ... {i}/{len(pdbs)}")

    log(f"[harvest] {len(rows)} rows, {quarantined} quarantined")
    return rows


def write_tsv(rows, path):
    path = Path(path)
    with open(path, "w") as w:
        w.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            w.write("\t".join(str(r.get(c, NOT_RUN)).replace("\t", " ").replace("\n", " ")
                              for c in COLUMNS) + "\n")
    print(f"[write] {path}  ({len(rows)} candidates x {len(COLUMNS)} columns)")


def summarise(rows):
    if not rows:
        print("no rows")
        return
    import collections
    print(f"\n{'='*64}\nPOOL SUMMARY  n={len(rows)}\n{'='*64}")
    for key in ("epitope_arm", "eligibility_status", "novelty_status", "verdict"):
        c = collections.Counter(str(r[key]) for r in rows)
        print(f"{key:20s} " + "  ".join(f"{k}={v}" for k, v in sorted(c.items())))
    num = [r for r in rows if r["rf2_iface_hl_vs_t"] != NOT_RUN]
    if num:
        v = sorted(float(r["rf2_iface_hl_vs_t"]) for r in num)
        print(f"\nrf2 interaction_pae (H+L vs T), n={len(v)}:")
        print(f"  min {v[0]:.2f}  p25 {v[len(v)//4]:.2f}  median {v[len(v)//2]:.2f}  "
              f"p75 {v[3*len(v)//4]:.2f}  max {v[-1]:.2f}")
        print(f"  PASSING the authors' <10 filter: "
              f"{sum(1 for x in v if x < 10)}/{len(v)} ({100*sum(1 for x in v if x<10)/len(v):.0f}%)")
    rm = [float(r["rf2_target_aligned_antibody_rmsd"]) for r in rows
          if r["rf2_target_aligned_antibody_rmsd"] != NOT_RUN]
    if rm:
        rm.sort()
        print(f"\ntarget-aligned antibody RMSD (design vs RF2 prediction), n={len(rm)}:")
        print(f"  min {rm[0]:.2f}  median {rm[len(rm)//2]:.2f}  max {rm[-1]:.2f}")
        print(f"  PASSING <2A: {sum(1 for x in rm if x < 2)}/{len(rm)}")
    both = [r for r in rows
            if r["rf2_iface_hl_vs_t"] != NOT_RUN
            and r["rf2_target_aligned_antibody_rmsd"] != NOT_RUN]
    if both:
        n = sum(1 for r in both
                if float(r["rf2_iface_hl_vs_t"]) < 10
                and float(r["rf2_target_aligned_antibody_rmsd"]) < 2
                and r["eligibility_status"] == "pass"
                and r["novelty_status"] != "fail")
        print(f"\nFULLY PASSING (pae<10 AND rmsd<2A AND eligible AND novel): {n}/{len(both)}")


def self_test():
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    import tempfile
    d = Path(tempfile.mkdtemp())
    p = d / "t.pdb"
    # H: 5 residues ACDEF, L: 4 residues GHIK; CDR H1 = abs 2-3, L1 = abs 7-8
    lines = []
    s = 1
    for chain, seq, start in (("H", "ACDEF", 1), ("L", "GHIK", 6)):
        for i, aa in enumerate(seq):
            three = {v: k for k, v in tp.THREE2ONE.items()}[aa]
            for an in ("N", "CA", "C", "CB"):
                nm4 = f" {an:<3s}"
                lines.append(f"ATOM  {s:5d} {nm4}{'':1s}{three:>3s} "
                             f"{chain}{start+i:4d}{'':4s}"
                             f"{i*3.0:8.3f}{0.0:8.3f}{0.0:8.3f}"
                             f"{1.00:6.2f}{0.00:6.2f}{'':10s}{an[0]:>2s}\n")
                s += 1
    lines.append("REMARK PDBinfo-LABEL:    2 H1\n")
    lines.append("REMARK PDBinfo-LABEL:    3 H1\n")
    lines.append("REMARK PDBinfo-LABEL:    7 L1\n")
    lines.append("REMARK PDBinfo-LABEL:    8 L1\n")
    lines.append("SCORE interaction_pae: 5.50\n")
    lines.append("SCORE pred_lddt: 0.88\n")
    p.write_text("".join(lines))

    sc = read_scores(p)
    check("read_scores parses SCORE lines", sc["interaction_pae"] == 5.5)
    lab = read_cdr_labels(p)
    check("read_cdr_labels groups by loop", lab == {"H1": [2, 3], "L1": [7, 8]})

    ex = extract(p)
    check("extract: VH sequence", ex["vh"] == "ACDEF")
    check("extract: VL sequence", ex["vl"] == "GHIK")
    check("extract: H1 absolute idx 2-3 -> VH[1:3] = 'CD'", ex["cdrs"]["H1"] == "CD")
    check("extract: L1 absolute idx 7-8 -> VL[1:3] = 'HI' (offset by len(VH))",
          ex["cdrs"]["L1"] == "HI")
    check("extract: CDR slice reproduces the recorded sequence",
          all((ex["vh"] if v["chain"] == "VH" else ex["vl"])
              [v["start_idx"]:v["end_idx"]] == v["sequence"]
              for v in ex["cdr_definitions"].values()))
    why = []
    bad = d / "nol.pdb"
    bad.write_text("".join(l for l in lines if " L" not in l[20:23]))
    check("extract: missing light chain returns None WITH a reason",
          extract(bad, reason=why) is None and why and "need both H and L" in why[0])
    check("arm_of: finds E1 in a production path",
          arm_of("/x/out/production/E1/b003/3_rf2/y.pdb") == "E1")
    check("arm_of: finds E1 in the differently-shaped pilot path",
          arm_of("/x/out/pilot/E1_n2/3_rf2/y.pdb") == "E1")
    check("arm_of: returns None when no arm is present",
          arm_of("/x/out/other/b000/3_rf2/y.pdb") is None)
    # The boundary check must CATCH a shift. The fixture needs DESIGNED CDRs that differ
    # from the framework -- using the bare framework as the "design" means a shifted
    # boundary still compares framework against framework and nothing is detected.
    def with_designed_cdrs(fw, spans):
        out = list(fw)
        for a, b in spans:
            for i in range(a, b):
                out[i] = "W" if fw[i] != "W" else "G"   # guaranteed different
        return "".join(out)

    vh_d = with_designed_cdrs(FRAMEWORK_VH, [(25, 32), (98, 105)])
    vl_d = with_designed_cdrs(FRAMEWORK_VL, [(23, 34), (88, 97)])
    real = {"vh": vh_d, "vl": vl_d,
            "cdr_definitions": {"H1": {"chain": "VH", "start_idx": 25, "end_idx": 32,
                                       "sequence": FRAMEWORK_VH[25:32]},
                                "H3": {"chain": "VH", "start_idx": 98, "end_idx": 105,
                                       "sequence": FRAMEWORK_VH[98:105]},
                                "L1": {"chain": "VL", "start_idx": 23, "end_idx": 34,
                                       "sequence": FRAMEWORK_VL[23:34]},
                                "L3": {"chain": "VL", "start_idx": 88, "end_idx": 97,
                                       "sequence": FRAMEWORK_VL[88:97]}}}
    check("framework check: correct boundaries on the real framework pass",
          check_framework_outside_cdrs(real) == [])
    shifted = {k: (v if k != "cdr_definitions" else
                   {kk: dict(vv, start_idx=vv["start_idx"] + 3, end_idx=vv["end_idx"] + 3)
                    for kk, vv in v.items()}) for k, v in real.items()}
    check("framework check: a +3 boundary shift is CAUGHT (the old check was a tautology)",
          check_framework_outside_cdrs(shifted) != [])
    truncated = dict(real, vh="KKKK" + vh_d[4:])
    check("framework check: a corrupted framework N-terminus is caught",
          check_framework_outside_cdrs(truncated) != [])
    check("schema: candidates.tsv has every spec column",
          all(c in COLUMNS for c in
              ["candidate_id", "epitope_arm", "framework", "generator", "vh_seq",
               "vl_seq", "rf2_iface_hl_vs_t", "boltz2_iface_mean5", "novaatom_iptm",
               "liability_penalty", "novelty_status", "eligibility_status",
               "rank_final", "selected", "rejection_reason"]))

    rows = [{c: NOT_RUN for c in COLUMNS}]
    out = d / "c.tsv"
    write_tsv(rows, out)
    txt = out.read_text().splitlines()
    check("write_tsv: header + one row", len(txt) == 2)
    check("write_tsv: uncomputed metrics are literally 'not_run', never 0",
          txt[1].split("\t")[COLUMNS.index("boltz2_iface_mean5")] == "not_run")
    check("write_tsv: no stray tabs break the column count",
          len(txt[1].split("\t")) == len(COLUMNS))

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default=str(HERE.parent / "candidates.tsv"))
    ap.add_argument("--root")
    ap.add_argument("--pattern", default="*/*/3_rf2/*.pdb")
    a = ap.parse_args()
    if a.self_test:
        print("06_harvest.py self-test (synthetic PDB)")
        sys.exit(0 if self_test() else 1)
    rows = harvest(limit=a.limit, root=a.root, pattern=a.pattern)
    if rows:
        write_tsv(rows, a.out)
        summarise(rows)
    else:
        print("[harvest] no candidates yet -- production may still be running")


if __name__ == "__main__":
    main()
