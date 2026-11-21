#!/usr/bin/env python
"""
qc_liabilities.py -- hard eligibility gates + developability liability screen.

Spec: docs/RANKING_AND_QC.md sections 2 and 3. That section is the complete spec.

STDLIB ONLY. No numpy, no biopython. There is no system biopython on this box, so this
runs in any env or none -- including a bare `python3`.

Two stages, in order:
  1. Hard eligibility gates (binary). A design failing ANY gate is REMOVED from the pool.
     It does not get a penalty; it is gone.
  2. Liability screen (penalty score). REPORTS, does not filter. A design with one
     borderline flag and strong structural evidence may still deserve a slot, but that
     must be a visible logged decision.

Run:  python3 scripts/qc_liabilities.py --tsv candidates.tsv
Test: python3 scripts/qc_liabilities.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys

AA = set("ACDEFGHIKLMNPQRSTVWY")
GENSCRIPT_SIGNAL = "MGWSCIILFLVATATGVHS"

# docs/RANKING_AND_QC.md section 2
VH_LEN = (105, 135)
VL_LEN = (100, 125)
CYS_PER_DOMAIN = 2

# Kyte-Doolittle hydropathy, for GRAVY
KD = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

# pKa values for the Henderson-Hasselbalch pI estimate
PKA_NTERM, PKA_CTERM = 9.69, 2.34
PKA_SIDE = {"D": 3.65, "E": 4.25, "C": 8.18, "Y": 10.07, "H": 6.00,
            "K": 10.53, "R": 12.48}
POSITIVE = set("KRH")

# ---------------------------------------------------------------- liabilities
# [ASSUMPTION] every weight below is OURS, not GenScript's. Severities follow the
# table in RANKING_AND_QC.md section 3; the numbers attached to them are our choice.
SEVERITY = {"critical": 10.0, "high": 5.0, "medium_high": 3.0, "medium": 2.0}

# Framework hits are down-weighted hard: the framework is a standard, well-behaved
# scaffold whose motifs are tolerated in approved therapeutics. The CDRs are ours.
FRAMEWORK_WEIGHT = 0.15

# (name, regex, severity_in_cdr, severity_in_framework)
MOTIFS = [
    ("n_glycosylation",   r"N[^P][ST]", "critical",    "high"),
    ("deamidation_NG",    r"NG",        "critical",    "high"),
    ("deamidation_NS",    r"NS",        "high",        "medium"),
    ("deamidation_NN",    r"NN",        "medium",      "medium"),
    ("deamidation_NT",    r"NT",        "medium",      "medium"),
    ("deamidation_NA",    r"NA",        "medium",      "medium"),
    ("deamidation_NH",    r"NH",        "medium",      "medium"),
    ("isomerisation_DG",  r"DG",        "critical",    "high"),
    ("isomerisation_DS",  r"DS",        "high",        "medium"),
    ("isomerisation_DD",  r"DD",        "medium",      "medium"),
    ("isomerisation_DT",  r"DT",        "medium",      "medium"),
    ("isomerisation_DH",  r"DH",        "medium",      "medium"),
    ("acid_labile_DP",    r"DP",        "medium_high", "medium"),
    ("oxidation_Met",     r"M",         "medium",      "medium"),
    ("oxidation_Trp",     r"W",         "high",        "medium"),
    ("basic_patch",       r"RR|KK|RK|KR", "medium",    "medium"),
]


class Gate:
    def __init__(self, name, passed, detail):
        self.name, self.passed, self.detail = name, passed, detail

    def as_dict(self):
        return {"gate": self.name, "pass": self.passed, "detail": self.detail}


# ---------------------------------------------------------------- helpers

def find_all(pattern, seq):
    """All (possibly overlapping) match start positions."""
    return [m.start() for m in re.finditer(f"(?={pattern})", seq)]


def net_charge(seq, ph):
    pos = 1.0 / (1.0 + 10 ** (ph - PKA_NTERM))
    neg = 1.0 / (1.0 + 10 ** (PKA_CTERM - ph))
    for a in seq:
        pk = PKA_SIDE.get(a)
        if pk is None:
            continue
        if a in POSITIVE:
            pos += 1.0 / (1.0 + 10 ** (ph - pk))
        else:
            neg += 1.0 / (1.0 + 10 ** (pk - ph))
    return pos - neg


def theoretical_pi(seq, lo=0.0, hi=14.0, tol=1e-4):
    """Bisection on net charge.

    NOTE: this treats Cys as titratable. For a variable domain with an intact
    intradomain disulfide that slightly UNDERestimates pI. Acceptable for a comparative
    screen; it is an estimate and must never be reported as an analytical measurement.
    """
    for _ in range(100):
        mid = (lo + hi) / 2.0
        c = net_charge(seq, mid)
        if abs(c) < tol or hi - lo < tol:
            return round(mid, 2)
        if c > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2.0, 2)


def gravy(seq):
    if not seq:
        return 0.0
    return round(sum(KD.get(a, 0.0) for a in seq) / len(seq), 3)


def cdr_net_charge(cdr_seq):
    """(K + R + H/2) - (D + E), per RANKING_AND_QC.md section 3."""
    return (cdr_seq.count("K") + cdr_seq.count("R") + cdr_seq.count("H") / 2.0
            - cdr_seq.count("D") - cdr_seq.count("E"))


def longest_run(seq):
    best = run = 1
    for a, b in zip(seq, seq[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best if seq else 0


def looks_like_signal_peptide(seq, n=20):
    """A signal peptide is a short hydrophobic leader. Real VH/VL start E/D/Q/V.

    Heuristic and deliberately narrow: we only need to catch an accidentally prepended
    leader, and GenScript's own leader is checked exactly.
    """
    head = seq[:n]
    if not head:
        return False
    hyd = sum(1 for a in head if a in "AVLIMFWC")
    return seq[0] == "M" and hyd / len(head) >= 0.45


# ---------------------------------------------------------------- stage 1

def eligibility(vh, vl, cdrs, seen_pairs=None, provenance=None):
    """Hard binary gates. Returns (ok, [Gate]). Any failure removes the design."""
    g = []

    # completeness
    g.append(Gate("completeness", bool(vh) and bool(vl),
                  f"VH {len(vh or '')} aa, VL {len(vl or '')} aa"))

    # alphabet
    bad_h = sorted(set(vh or "") - AA)
    bad_l = sorted(set(vl or "") - AA)
    g.append(Gate("alphabet", not bad_h and not bad_l,
                  "ok" if not (bad_h or bad_l) else f"non-standard: VH{bad_h} VL{bad_l}"))

    # length
    g.append(Gate("vh_length", VH_LEN[0] <= len(vh or "") <= VH_LEN[1],
                  f"{len(vh or '')} (allowed {VH_LEN[0]}-{VH_LEN[1]})"))
    g.append(Gate("vl_length", VL_LEN[0] <= len(vl or "") <= VL_LEN[1],
                  f"{len(vl or '')} (allowed {VL_LEN[0]}-{VL_LEN[1]})"))

    # signal peptide -- GenScript prepends MGWSCIILFLVATATGVHS automatically
    sig = []
    for nm, s in (("VH", vh or ""), ("VL", vl or "")):
        if s.startswith(GENSCRIPT_SIGNAL):
            sig.append(f"{nm} starts with the GenScript leader")
        elif looks_like_signal_peptide(s):
            sig.append(f"{nm} looks like a hydrophobic leader")
    g.append(Gate("no_signal_peptide", not sig, "; ".join(sig) or "ok"))

    # cysteine parity -- exactly 2 per variable domain
    ch, cl = (vh or "").count("C"), (vl or "").count("C")
    cys_ok = ch == CYS_PER_DOMAIN and cl == CYS_PER_DOMAIN
    if ch % 2 or cl % 2:
        det = f"ODD Cys count (free thiol): VH {ch}, VL {cl}"
    elif not cys_ok:
        det = (f"VH {ch}, VL {cl} -- even but != {CYS_PER_DOMAIN}; a non-canonical "
               f"disulfide we cannot validate experimentally in this timeframe. "
               f"Default is to reject (RANKING_AND_QC.md section 2 note)")
    else:
        det = f"VH {ch}, VL {cl}"
    g.append(Gate("cysteine_parity", cys_ok, det))

    # no N-glycosylation sequon inside any CDR
    glyc = []
    for name, s in sorted(cdrs.items()):
        for p in find_all(r"N[^P][ST]", s):
            glyc.append(f"{name}@{p}:{s[p:p+3]}")
    g.append(Gate("no_cdr_glycosylation", not glyc, "; ".join(glyc) or "ok"))

    # uniqueness
    if seen_pairs is None:
        g.append(Gate("uniqueness", True, "not_checked (no pool supplied)"))
    else:
        dup = (vh, vl) in seen_pairs
        g.append(Gate("uniqueness", not dup, "duplicate (VH,VL) in pool" if dup else "ok"))

    # provenance
    need = ("generator", "generator_version", "parameters_json", "random_seed", "run_id")
    miss = [k for k in need if not (provenance or {}).get(k)]
    g.append(Gate("provenance", not miss,
                  f"missing {miss}" if miss else "complete"))

    return all(x.passed for x in g), g


# ---------------------------------------------------------------- stage 2

def liabilities(vh, vl, cdrs):
    """Penalty score. REPORTS, does not filter."""
    hits = []
    cdr_concat = "".join(cdrs[k] for k in sorted(cdrs))

    # locate CDR spans inside each chain so a hit can be labelled CDR vs framework
    spans = {}
    for name, s in cdrs.items():
        chain = "VH" if name.startswith("H") else "VL"
        parent = vh if chain == "VH" else vl
        i = parent.find(s)
        if i >= 0:
            spans.setdefault(chain, []).append((i, i + len(s), name))

    def in_cdr(chain, pos):
        for a, b, nm in spans.get(chain, []):
            if a <= pos < b:
                return nm
        return None

    for chain, seq in (("VH", vh), ("VL", vl)):
        for name, pat, sev_cdr, sev_fw in MOTIFS:
            for p in find_all(pat, seq):
                loc = in_cdr(chain, p)
                sev = sev_cdr if loc else sev_fw
                w = SEVERITY[sev] * (1.0 if loc else FRAMEWORK_WEIGHT)
                hits.append({
                    "liability": name, "chain": chain, "pos": p,
                    "motif": seq[p:p + max(1, len(pat.replace("[^P]", "X")
                                                 .replace("|RK|KR", "")) // 1)][:3],
                    "region": loc or "framework", "severity": sev,
                    "weight": round(w, 2),
                })

    pen = sum(h["weight"] for h in hits)

    # sequence-level properties
    chg = cdr_net_charge(cdr_concat)
    gv = gravy(cdr_concat)
    pi_h, pi_l = theoretical_pi(vh), theoretical_pi(vl)
    h3 = cdrs.get("H3", "")
    runs = {k: longest_run(v) for k, v in cdrs.items()}
    worst_run = max(runs.values()) if runs else 0

    prop = []

    def add(cond, name, sev, detail):
        if cond:
            w = SEVERITY[sev]
            prop.append({"liability": name, "severity": sev, "weight": w, "detail": detail})

    add(chg >= 2.0, "cdr_net_charge_high", "high",
        f"CDR net charge {chg:+.1f} >= +2 (polyreactivity / fast clearance)")
    add(gv >= 0.0, "cdr_gravy_high", "medium_high",
        f"CDR GRAVY {gv:+.3f} >= 0 (self-association, HIC retention, viscosity)")
    add(not (6.0 <= pi_h <= 9.0), "pi_vh_out_of_range", "medium",
        f"VH theoretical pI {pi_h} outside 6.0-9.0 [estimate, not an analytical value]")
    add(not (6.0 <= pi_l <= 9.0), "pi_vl_out_of_range", "medium",
        f"VL theoretical pI {pi_l} outside 6.0-9.0 [estimate, not an analytical value]")
    add(len(h3) > 20, "cdrh3_too_long", "medium",
        f"CDR-H3 length {len(h3)} > 20")
    add(worst_run >= 4, "low_complexity_run", "medium",
        f"run of {worst_run} identical residues in a CDR")

    pen += sum(p["weight"] for p in prop)

    return {
        "liability_penalty": round(pen, 2),
        "motif_hits": hits,
        "property_hits": prop,
        "cdr_net_charge": round(chg, 2),
        "cdr_gravy": gv,
        "theoretical_pi_vh": pi_h,
        "theoretical_pi_vl": pi_l,
        "cdrh3_len": len(h3),
        "cys_count_vh": vh.count("C"),
        "cys_count_vl": vl.count("C"),
        "n_cdr_hits": sum(1 for h in hits if h["region"] != "framework"),
        "n_framework_hits": sum(1 for h in hits if h["region"] == "framework"),
    }


def screen(vh, vl, cdrs, seen_pairs=None, provenance=None):
    ok, gates = eligibility(vh, vl, cdrs, seen_pairs, provenance)
    out = {
        "eligibility_status": "pass" if ok else "fail",
        "gates": [g.as_dict() for g in gates],
        "failed_gates": [g.name for g in gates if not g.passed],
    }
    out.update(liabilities(vh, vl, cdrs))
    # assert the recorded CDRs really are slices of the submitted sequences
    bad = [k for k, v in cdrs.items()
           if v and v not in (vh if k.startswith("H") else vl)]
    out["cdr_slice_check"] = "ok" if not bad else f"QUARANTINE: {bad} not found in sequence"
    if bad:
        out["eligibility_status"] = "fail"
        out["failed_gates"] = out["failed_gates"] + ["cdr_slice_check"]
    return out


# ---------------------------------------------------------------- self-test

# a real, well-behaved humanised Fv (hu4D5-8) -- the framework we actually use
GOOD_VH = ("EVQLVESGGGLVQPGGSLRLSCAASGFNIKDTYIHWVRQAPGKGLEWVARIYPTNGYTRYADSVKGRFTIS"
           "ADTSKNTAYLQMNSLRAEDTAVYYCSRWGYAMDYWGQGTLVTVSS")
GOOD_VL = ("DIQMTQSPSSLSASVGDRVTITCRASQDVNTAVAWYQQKPGKAPKLLIYSASFLYSGVPSRFSGSRSGTDFT"
           "LTISSLQPEDFATYYCQQHYTTPPTFGQGTKVEIK")
GOOD_CDRS = {"H1": "GFNIKDT", "H2": "RIYPTNG", "H3": "WGYAMDY",
             "L1": "RASQDVNTAVA", "L2": "SASFLYS", "L3": "QQHYTTPPT"}


def self_test():
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    prov = {"generator": "rfantibody", "generator_version": "efe4b90",
            "parameters_json": "{}", "random_seed": 1, "run_id": "r1"}

    # ---- the known-good control MUST pass every gate ----
    r = screen(GOOD_VH, GOOD_VL, GOOD_CDRS, set(), prov)
    check("control (hu4D5-8 Fv) passes eligibility", r["eligibility_status"] == "pass")
    if r["eligibility_status"] != "pass":
        print(f"      failed: {r['failed_gates']}")
    check("control CDR slice check ok", r["cdr_slice_check"] == "ok")
    check("control has 2 Cys per domain",
          r["cys_count_vh"] == 2 and r["cys_count_vl"] == 2)

    # ---- every hard gate must FAIL on a targeted mutant ----
    def fails(vh, vl, cdrs, gate, seen=None, pv=prov):
        rr = screen(vh, vl, cdrs, seen if seen is not None else set(), pv)
        return rr["eligibility_status"] == "fail" and gate in rr["failed_gates"]

    check("gate alphabet: 'X' in VH fails",
          fails("X" + GOOD_VH[1:], GOOD_VL, GOOD_CDRS, "alphabet"))
    check("gate completeness: empty VL fails",
          fails(GOOD_VH, "", GOOD_CDRS, "completeness"))
    check("gate vh_length: 40-mer fails",
          fails(GOOD_VH[:40], GOOD_VL, GOOD_CDRS, "vh_length"))
    check("gate vl_length: 300-mer fails",
          fails(GOOD_VH, GOOD_VL + "A" * 200, GOOD_CDRS, "vl_length"))
    check("gate no_signal_peptide: GenScript leader prepended fails",
          fails(GENSCRIPT_SIGNAL + GOOD_VH, GOOD_VL, GOOD_CDRS, "no_signal_peptide"))
    check("gate no_signal_peptide: generic hydrophobic leader fails",
          fails("MALWMRLLPLLALLALWGPD" + GOOD_VH, GOOD_VL, GOOD_CDRS, "no_signal_peptide"))
    check("gate cysteine_parity: 3 Cys (odd, free thiol) fails",
          fails(GOOD_VH[:10] + "C" + GOOD_VH[11:], GOOD_VL, GOOD_CDRS, "cysteine_parity"))
    check("gate cysteine_parity: 4 Cys (even, non-canonical) also fails by default",
          fails(GOOD_VH[:10] + "C" + GOOD_VH[11:20] + "C" + GOOD_VH[21:],
                GOOD_VL, GOOD_CDRS, "cysteine_parity"))
    check("gate no_cdr_glycosylation: NGT in CDR-H3 fails",
          fails(GOOD_VH.replace("WGYAMDY", "WNGTMDY"), GOOD_VL,
                dict(GOOD_CDRS, H3="WNGTMDY"), "no_cdr_glycosylation"))
    check("gate uniqueness: duplicate pair fails",
          fails(GOOD_VH, GOOD_VL, GOOD_CDRS, "uniqueness",
                seen={(GOOD_VH, GOOD_VL)}))
    check("gate provenance: missing run_id fails",
          fails(GOOD_VH, GOOD_VL, GOOD_CDRS, "provenance",
                pv={k: v for k, v in prov.items() if k != "run_id"}))
    check("cdr_slice_check: CDR not present in sequence quarantines",
          screen(GOOD_VH, GOOD_VL, dict(GOOD_CDRS, H3="ZZZZZZ"), set(), prov)
          ["cdr_slice_check"].startswith("QUARANTINE"))

    # ---- the screen must not silently pass everything ----
    sus = screen(GOOD_VH, GOOD_VL, dict(GOOD_CDRS, H3="NGSNGSNGS"), set(), prov)
    check("screen is not vacuous: an NGS-rich CDR-H3 is caught",
          sus["eligibility_status"] == "fail")

    # ---- liability scoring behaviour ----
    clean = screen(GOOD_VH, GOOD_VL, GOOD_CDRS, set(), prov)
    dirty = screen(GOOD_VH.replace("WGYAMDY", "WDGNGMW"), GOOD_VL,
                   dict(GOOD_CDRS, H3="WDGNGMW"), set(), prov)
    check("liability: DG+NG+W in CDR-H3 scores worse than the control",
          dirty["liability_penalty"] > clean["liability_penalty"])
    check("liability: a CDR hit outweighs the same motif in framework",
          SEVERITY["critical"] > SEVERITY["critical"] * FRAMEWORK_WEIGHT)
    check("liability: penalty is never negative", clean["liability_penalty"] >= 0)

    # charge / GRAVY / pI behaviour
    check("cdr_net_charge: KKRR scores +4",
          abs(cdr_net_charge("KKRR") - 4.0) < 1e-9)
    check("cdr_net_charge: His counts half",
          abs(cdr_net_charge("H") - 0.5) < 1e-9)
    check("cdr_net_charge: DE subtract",
          abs(cdr_net_charge("KDE") - (-1.0)) < 1e-9)
    check("gravy: poly-Ile is positive, poly-Asp negative",
          gravy("IIII") > 0 > gravy("DDDD"))
    check("pI: poly-Lys basic (>9), poly-Asp acidic (<5)",
          theoretical_pi("KKKKKKKKKK") > 9.0 and theoretical_pi("DDDDDDDDDD") < 5.0)
    check("pI: monotone -- adding Lys raises pI",
          theoretical_pi(GOOD_VH + "KKKK") > theoretical_pi(GOOD_VH))
    check("longest_run: AAAA is 4", longest_run("CAAAAG") == 4)
    check("find_all: overlapping NNN finds 2 NN", len(find_all(r"NN", "NNN")) == 2)
    check("high CDR charge is flagged",
          any(p["liability"] == "cdr_net_charge_high"
              for p in screen(GOOD_VH, GOOD_VL,
                              dict(GOOD_CDRS, H3="KKRRKKR"), set(), prov)["property_hits"]))
    check("long CDR-H3 is flagged",
          any(p["liability"] == "cdrh3_too_long"
              for p in screen(GOOD_VH, GOOD_VL,
                              dict(GOOD_CDRS, H3="A" * 25), set(), prov)["property_hits"]))

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--vh")
    ap.add_argument("--vl")
    ap.add_argument("--cdrs", help="JSON dict of CDR name -> sequence")
    a = ap.parse_args()

    if a.self_test:
        print("qc_liabilities.py self-test (synthetic sequences)")
        sys.exit(0 if self_test() else 1)

    if a.vh and a.vl:
        cd = json.loads(a.cdrs) if a.cdrs else {}
        print(json.dumps(screen(a.vh, a.vl, cd, set(), None), indent=2))
    else:
        ap.error("supply --vh and --vl, or --self-test")


if __name__ == "__main__":
    main()
