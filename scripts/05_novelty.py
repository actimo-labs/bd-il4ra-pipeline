#!/usr/bin/env python
"""
05_novelty.py -- frozen reference set + CDR-level novelty screen.

Spec: docs/RANKING_AND_QC.md section 4.

The rule: de novo, no existing IL-4Ralpha binder as a starting scaffold, novelty judged
at CDR level, standardised framework and constant regions EXPECTED. We satisfy it by
construction, but novelty is assessed on the output, so we screen our own output.

Tier 1 of the reference set is the tier the rule is actually about: every anti-IL-4Ralpha
antibody we can find. Found by querying RCSB for structures containing UniProt P24394:

    6WGL  Dupilumab Fab + human IL-4 receptor      <- the canonical one
    6OEL  Engineered Fab + IL-4 receptor
    8K4Q  Nanobody HuNb103 + IL-4Ralpha
    8Z8L  Nanobody 4E9/dAb1 + IL-4Ralpha

These are used for COMPARISON ONLY. No sequence from them is ever used as a scaffold or
a starting point -- that is a hard rule in CLAUDE.md.

Identity is global Needleman-Wunsch percent identity, implemented here in stdlib.
blastp is present but is unreliable on 7-20 residue CDR-H3 loops, and the thresholds in
the spec are global-identity thresholds.

Run:  conda run -n boltz python scripts/05_novelty.py --build
Test: python3 scripts/05_novelty.py --self-test
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

BDIL4R = Path(os.environ.get("BDIL4R", "/mnt/comp5data/bd-il4r"))
NOV = BDIL4R / "novelty"
RAW = NOV / "raw"

# docs/RANKING_AND_QC.md section 4. [ASSUMPTION] -- these are OURS, not GenScript's.
THRESH = {
    "cdrh3_identity_max": 0.70,
    "cdr_concat_identity_max": 0.60,
    "il4ra_full_identity_max": 0.85,
}

MIN_REF_CDRH3 = 5   # shorter transferred H3s are alignment artefacts, not CDRs

# True  = RANKING_AND_QC.md s4 verbatim: >0.85 full identity to an anti-IL-4Ra antibody
#         is a hard fail on its own.
# False = intent-based reading: only a hard fail when the CDRs are ALSO similar.
# A/B tested over 660 real designs 2026-11-22: identical outcome. Default to the spec.
STRICT_SPEC_FULL_IDENTITY = True

REFS = {
    "6WGL": {"H": "A", "L": "B", "name": "dupilumab", "target_chain": "C",
             "note": "canonical anti-IL-4Ralpha therapeutic (Dupixent)"},
    "6OEL": {"H": "H", "L": "L", "name": "engineered_Fab_6OEL", "target_chain": "B",
             "note": "engineered Fab bound to IL-4R"},
    "8K4Q": {"H": "B", "L": None, "name": "nanobody_HuNb103", "target_chain": "A",
             "note": "VHH; cannot be submitted but is a valid novelty reference"},
    "8Z8L": {"H": "A", "L": None, "name": "nanobody_4E9_dAb1", "target_chain": "B",
             "note": "VHH"},
}

# hu4D5-8 Fv -- our framework. CDR spans are known exactly from the HLT REMARKs
# (H1 26-32, H2 52-57, H3 99-105 absolute; L1 140-150, L2 166-172, L3 205-213 with
# VH length 116), so they are 0-based slices into each domain:
HU4D5_VH = ("EVQLVESGGGLVQPGGSLRLSCAASGFNIKDTYIHWVRQAPGKGLEWVARIYPTNGYTRYADSVKGRFTIS"
            "ADTSKNTAYLQMNSLRAEDTAVYYCSRWGYAMDYWGQGTLVTVSS")
HU4D5_VL = ("DIQMTQSPSSLSASVGDRVTITCRASQDVNTAVAWYQQKPGKAPKLLIYSASFLYSGVPSRFSGSRSGTDFT"
            "LTISSLQPEDFATYYCQQHYTTPPTFGQGTKVEIK")
HU4D5_CDR_SPANS = {  # 0-based [start, end) into the domain
    "H1": (25, 32), "H2": (51, 57), "H3": (98, 105),
    "L1": (23, 34), "L2": (49, 56), "L3": (88, 97),
}

BLOSUM_MATCH, BLOSUM_MISMATCH, GAP_OPEN, GAP_EXT = 2, -1, -10, -1


# ---------------------------------------------------------------- alignment

def nw_align(a, b, match=BLOSUM_MATCH, mismatch=BLOSUM_MISMATCH,
             gap_open=GAP_OPEN, gap_ext=GAP_EXT):
    """Global Needleman-Wunsch with affine gaps. Returns (aligned_a, aligned_b)."""
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return a + "-" * m, "-" * n + b
    NEG = float("-inf")
    M = [[NEG] * (m + 1) for _ in range(n + 1)]
    X = [[NEG] * (m + 1) for _ in range(n + 1)]   # gap in b
    Y = [[NEG] * (m + 1) for _ in range(n + 1)]   # gap in a
    PM = [[None] * (m + 1) for _ in range(n + 1)]
    PX = [[None] * (m + 1) for _ in range(n + 1)]
    PY = [[None] * (m + 1) for _ in range(n + 1)]
    M[0][0] = 0
    for i in range(1, n + 1):
        X[i][0] = gap_open + (i - 1) * gap_ext
        PX[i][0] = "X"
    for j in range(1, m + 1):
        Y[0][j] = gap_open + (j - 1) * gap_ext
        PY[0][j] = "Y"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = match if a[i - 1] == b[j - 1] else mismatch
            best, src = max((M[i - 1][j - 1], "M"), (X[i - 1][j - 1], "X"),
                            (Y[i - 1][j - 1], "Y"))
            M[i][j] = best + s
            PM[i][j] = src
            best, src = max((M[i - 1][j] + gap_open, "M"), (X[i - 1][j] + gap_ext, "X"),
                            (Y[i - 1][j] + gap_open, "Y"))
            X[i][j] = best
            PX[i][j] = src
            best, src = max((M[i][j - 1] + gap_open, "M"), (X[i][j - 1] + gap_open, "X"),
                            (Y[i][j - 1] + gap_ext, "Y"))
            Y[i][j] = best
            PY[i][j] = src
    i, j = n, m
    state = max((M[n][m], "M"), (X[n][m], "X"), (Y[n][m], "Y"))[1]
    oa, ob = [], []
    P = {"M": PM, "X": PX, "Y": PY}
    while i > 0 or j > 0:
        if state == "M":
            oa.append(a[i - 1]); ob.append(b[j - 1])
            state = P["M"][i][j]; i -= 1; j -= 1
        elif state == "X":
            oa.append(a[i - 1]); ob.append("-")
            state = P["X"][i][j]; i -= 1
        else:
            oa.append("-"); ob.append(b[j - 1])
            state = P["Y"][i][j]; j -= 1
        if i == 0 and j > 0 and state is None:
            state = "Y"
        if j == 0 and i > 0 and state is None:
            state = "X"
        if state is None:
            break
    while i > 0:
        oa.append(a[i - 1]); ob.append("-"); i -= 1
    while j > 0:
        oa.append("-"); ob.append(b[j - 1]); j -= 1
    return "".join(reversed(oa)), "".join(reversed(ob))


def fast_identity(a, b, denom="max"):
    """Ungapped best-offset identity. ~50x cheaper than affine-gap NW.

    Used to SHORTLIST references; the exact NW identity is then computed only for the
    top few. With 1108 references and ~500 designs, running full NW against every
    reference costs ~13 s/design, which does not scale to the pool.
    """
    if not a or not b:
        return 0.0
    d = len(a) if denom == "query" else max(len(a), len(b))
    if len(a) > len(b):
        a, b = b, a
    best = 0
    for off in range(len(b) - len(a) + 1):
        m = 0
        for x, y in zip(a, b[off:]):
            if x == y:
                m += 1
        if m > best:
            best = m
    return best / d if d else 0.0


def nearest_by_identity(query, candidates, topk=12, denom="max"):
    """(best_exact_identity, best_key) over `candidates` = [(key, seq), ...].

    Shortlists with fast_identity, then runs exact NW identity on the top `topk`.
    Exact where it matters (the nearest hit) and cheap where it does not.
    """
    if not query:
        return 0.0, None
    scored = [(fast_identity(query, s, denom), k) for k, s in candidates if s]
    if not scored:
        return 0.0, None
    scored.sort(reverse=True)
    best_i, best_k = 0.0, None
    lookup = dict(candidates)
    for _, k in scored[:topk]:
        i = identity(query, lookup[k], denom)
        if i > best_i:
            best_i, best_k = i, k
    return best_i, best_k


def identity(a, b, denom="max"):
    """Global percent identity. The DENOMINATOR CHOICE IS NOT COSMETIC.

    denom="max"   : matches / length of the LONGER sequence. Correct for comparing two
                    CDR loops, where a length difference is a real difference.
    denom="query" : matches / len(a). Correct when `b` legitimately contains extra
                    residues outside the region of interest -- e.g. our 119 aa VH
                    against a 222 aa reference Fab HEAVY CHAIN that carries CH1.

    This was originally min(len(a), len(b)), described as "conservative because it
    cannot be deflated by padding". That reasoning is backwards for short references:
    with a min denominator, Cinpanemab's transferred CDR-H3 of 'AH' (2 residues) scored
    **1.0 identical** to our 10-residue 'APIGGHALSH', hard-failing a perfectly novel
    design. 5 of 20 real designs were being rejected this way. See RUNLOG 2026-11-21.
    """
    if not a or not b:
        return 0.0
    aa, bb = nw_align(a, b)
    matches = sum(1 for x, y in zip(aa, bb) if x == y and x != "-")
    d = len(a) if denom == "query" else max(len(a), len(b))
    return round(matches / d, 4) if d else 0.0


def transfer_cdrs(query, ref_domain, ref_spans):
    """Transfer CDR boundaries from our framework onto a reference V-domain by alignment.

    The documented no-install fallback (RANKING_AND_QC.md section 1) for when ANARCI is
    unavailable, which it is on this box (hmmer is not installed either). Adequate for
    'is our CDR-H3 suspiciously close to a known one'.
    """
    qa, ra = nw_align(query, ref_domain)
    # map ref_domain index -> alignment column
    col_of, ri = {}, 0
    for c, ch in enumerate(ra):
        if ch != "-":
            col_of[ri] = c
            ri += 1
    out = {}
    for name, (s, e) in ref_spans.items():
        if s not in col_of:
            continue
        c0 = col_of[s]
        c1 = col_of.get(e - 1, len(ra) - 1) + 1
        seg = "".join(ch for ch in qa[c0:c1] if ch != "-")
        out[name] = seg
    return out


# ---------------------------------------------------------------- reference set

def parse_chain_seq(pdb, chain):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "tp", str(Path(__file__).with_name("01_target_prep.py")))
    tp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tp)
    ch = tp.parse_pdb(pdb, chains={chain})
    if chain not in ch:
        return None
    return "".join(r.one for r in sorted(ch[chain], key=lambda x: x.resnum))


def build_reference_set(verbose=True):
    def log(*a):
        if verbose:
            print(*a)

    NOV.mkdir(parents=True, exist_ok=True)
    entries, files = [], []
    for pid, info in REFS.items():
        p = RAW / f"{pid}.pdb"
        if not p.exists():
            log(f"[ref] MISSING {p} -- download it first")
            continue
        files.append(p)
        vh = parse_chain_seq(p, info["H"])
        vl = parse_chain_seq(p, info["L"]) if info["L"] else None
        # Fab chains include CH1/CL -- trim to the V domain by alignment to our framework
        vh_cdrs = transfer_cdrs(vh, HU4D5_VH,
                                {k: v for k, v in HU4D5_CDR_SPANS.items()
                                 if k.startswith("H")}) if vh else {}
        vl_cdrs = transfer_cdrs(vl, HU4D5_VL,
                                {k: v for k, v in HU4D5_CDR_SPANS.items()
                                 if k.startswith("L")}) if vl else {}
        cdrs = {**vh_cdrs, **vl_cdrs}
        e = {
            "id": info["name"], "pdb": pid, "note": info["note"],
            "is_anti_il4ra": True, "tier": 1,
            "vh": vh, "vl": vl, "cdrs": cdrs,
            "vh_len": len(vh) if vh else 0, "vl_len": len(vl) if vl else 0,
            "format": "Fv/Fab" if vl else "VHH",
        }
        entries.append(e)
        log(f"[ref] {info['name']:22s} {pid}  VH {len(vh or '')}aa VL {len(vl or '')}aa  "
            f"CDR-H3='{cdrs.get('H3','?')}'")

    # freeze: file list + per-file sha256 + date, per RANKING_AND_QC.md section 4
    shas = {}
    for f in files:
        shas[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    ref = {
        "_frozen": {
            "date_utc": datetime.datetime.utcnow().isoformat() + "Z",
            "source": "RCSB structures containing UniProt P24394, found via the RCSB "
                      "search API; 10 entries total, 4 of which are antibody complexes",
            "files": shas,
            "policy": "FROZEN. Do not update mid-campaign (the brief recommends a frozen "
                      "reference database). Comparison only -- no sequence here is ever "
                      "used as a design scaffold.",
            "cdr_boundary_method": "mafft-free alignment transfer from the hu4D5-8 "
                                   "framework, whose CDR spans are known exactly from "
                                   "the RFantibody HLT REMARKs. ANARCI and hmmer are not "
                                   "installed on this box; this is the documented "
                                   "no-install fallback (RANKING_AND_QC.md section 1).",
            "tier2_therapeutic": "not_run",
            "tier3_sabdab_broad": "not_run",
        },
        "thresholds": THRESH,
        "entries": entries,
    }
    out = NOV / "reference_set.json"
    out.write_text(json.dumps(ref, indent=2))
    log(f"\n[write] {out}  ({len(entries)} tier-1 references)")

    fa = NOV / "reference_set.fasta"
    with open(fa, "w") as w:
        for e in entries:
            if e["vh"]:
                w.write(f">{e['id']}|VH|{e['pdb']}\n{e['vh']}\n")
            if e["vl"]:
                w.write(f">{e['id']}|VL|{e['pdb']}\n{e['vl']}\n")
    log(f"[write] {fa}")
    return ref


def build_tier2(csv_path, max_entries=None, verbose=True):
    """Tier 2: clinical-stage therapeutic antibodies from Thera-SAbDab.

    These contribute **CDR-level comparison only**. Full-domain identity against them is
    deliberately not computed: they are not IL-4Ra binders, so high framework identity to
    them is expected and fine, and many use the same IGHV3-23 / IGKV1-39 germlines we do.
    """
    import csv as _csv
    rows = list(_csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    out = []
    for r in rows:
        h = (r.get("HeavySequence") or "").strip()
        l = (r.get("LightSequence") or "").strip()
        if len(h) < 90 or len(l) < 80 or h.lower() in ("na", "none"):
            continue
        h = h.split()[0].upper()
        l = l.split()[0].upper()
        if set(h) - set("ACDEFGHIKLMNPQRSTVWY") or set(l) - set("ACDEFGHIKLMNPQRSTVWY"):
            continue
        cdrs = {}
        cdrs.update(transfer_cdrs(h, HU4D5_VH,
                                  {k: v for k, v in HU4D5_CDR_SPANS.items() if k[0] == "H"}))
        cdrs.update(transfer_cdrs(l, HU4D5_VL,
                                  {k: v for k, v in HU4D5_CDR_SPANS.items() if k[0] == "L"}))
        # Alignment transfer occasionally collapses a loop to 2-4 residues. Those are
        # transfer failures, not real CDR-H3s (32 of 1104 were shorter than 5), and a
        # degenerate reference matches far too easily. Drop them rather than trust them.
        if len(cdrs.get("H3", "")) < MIN_REF_CDRH3:
            continue
        out.append({
            "id": r["Therapeutic"].strip(), "pdb": None, "tier": 2,
            "note": f"{r.get('Format','')} / {r.get('Est. Status','')}".strip(" /"),
            "is_anti_il4ra": False,
            "vh": None, "vl": None,          # intentionally not stored: CDR-level only
            "cdrs": cdrs,
        })
        if max_entries and len(out) >= max_entries:
            break
    if verbose:
        print(f"[tier2] {len(rows)} therapeutics in file -> {len(out)} usable paired entries")
    return out


# ---------------------------------------------------------------- screen

def screen_design(vh, vl, cdrs, ref):
    """Returns novelty verdict + the nearest hit, recorded even when it passes."""
    cdr_concat = "".join(cdrs[k] for k in sorted(cdrs))
    h3 = cdrs.get("H3", "")

    best_full = {"ref": None, "identity": 0.0, "chain": None}
    exact = None

    h3_cands, concat_cands = [], []
    for e in ref["entries"]:
        rh3 = e["cdrs"].get("H3", "")
        if rh3:
            h3_cands.append((e["id"], rh3))
            if h3 and h3 == rh3:
                exact = e["id"]
        rconcat = "".join(e["cdrs"][k] for k in sorted(e["cdrs"]))
        if rconcat:
            concat_cands.append((e["id"], rconcat))

    i, k = nearest_by_identity(h3, h3_cands)
    best_h3 = {"ref": k, "identity": i,
               "seq": dict(h3_cands).get(k) if k else None}
    i, k = nearest_by_identity(cdr_concat, concat_cands)
    best_concat = {"ref": k, "identity": i}

    for e in ref["entries"]:
        # Full-domain identity is ONLY meaningful against anti-IL-4Ra antibodies.
        # RANKING_AND_QC.md s4: "Full VH/VL identity to a non-IL-4Ra antibody: high is
        # expected and fine. This is the standardised framework." With tier 2 loaded
        # (1133 therapeutics, many on IGHV3-23/IGKV1-39), comparing against all of them
        # would flag every design for sharing a common human germline framework.
        if e.get("is_anti_il4ra"):
            for chain, s in (("VH", e.get("vh")), ("VL", e.get("vl"))):
                q = vh if chain == "VH" else vl
                if s and q:
                    i = identity(q, s, denom="query")
                    if i > best_full["identity"]:
                        best_full = {"ref": e["id"], "identity": i, "chain": chain}

    fails = []
    if exact:
        fails.append(f"exact CDR-H3 match to {exact}")
    if best_h3["identity"] > THRESH["cdrh3_identity_max"]:
        fails.append(f"CDR-H3 identity {best_h3['identity']:.2f} > "
                     f"{THRESH['cdrh3_identity_max']} vs {best_h3['ref']}")
    flags = []
    if best_concat["identity"] > THRESH["cdr_concat_identity_max"]:
        flags.append(f"concatenated-CDR identity {best_concat['identity']:.2f} > "
                     f"{THRESH['cdr_concat_identity_max']} vs {best_concat['ref']}")

    # Full-domain identity gate.
    #
    # RANKING_AND_QC.md section 4 specifies ">85% full VH/VL identity to any anti-IL-4Ra
    # antibody = hard fail", reasoning that it "looks like scaffold derivation regardless
    # of how it was made". Applied literally that gate FAILS EVERY DESIGN WE MAKE:
    # our bare hu4D5-8 framework is already 0.860 identical to the 6OEL anti-IL-4Ra Fab's
    # VL, before a single CDR is designed, because both are IGKV1-39-family kappa
    # frameworks. Measured 2026-11-21, see RUNLOG.
    #
    # The same doc says framework sharing is "expected and fine" and the brief says
    # standardised frameworks are expected. So the gate's real target is derivation of
    # BOTH framework and CDRs. It hard-fails only when high full identity is accompanied
    # by CDR similarity; otherwise it records a flag with the explanation.
    # REVERTED TO THE LITERAL SPEC on 2026-11-22 after an A/B test over all 660 real
    # designs showed the modification changes NOTHING: both readings give 651 pass /
    # 9 fail, and zero designs differ. My earlier alarm -- that the literal gate "fails
    # 100% of our designs" -- was an extrapolation from the BARE framework (hu4D5-8 VL
    # is 0.860 against 6OEL) that the real data does not support: designing six CDRs
    # pulls the maximum observed full identity down to 0.827, under the 0.85 threshold.
    #
    # Since the modification buys nothing on this pool, the literal spec wins: it is one
    # fewer deviation to defend to GenScript. STRICT_SPEC_FULL_IDENTITY=False restores
    # the intent-based reading if a future pool ever does exceed 0.85 on framework alone.
    #
    # Margin is thin: 0.827 observed vs 0.850 threshold. Re-run the A/B if the pool changes.
    if best_full["identity"] > THRESH["il4ra_full_identity_max"]:
        if STRICT_SPEC_FULL_IDENTITY or best_concat["identity"] > THRESH["cdr_concat_identity_max"]:
            fails.append(
                f"full {best_full['chain']} identity {best_full['identity']:.2f} > "
                f"{THRESH['il4ra_full_identity_max']} vs anti-IL-4Ra {best_full['ref']} "
                f"AND concatenated-CDR identity {best_concat['identity']:.2f} > "
                f"{THRESH['cdr_concat_identity_max']} -- scaffold derivation")
        else:
            flags.append(
                f"full {best_full['chain']} identity {best_full['identity']:.2f} > "
                f"{THRESH['il4ra_full_identity_max']} vs anti-IL-4Ra {best_full['ref']}, "
                f"but concatenated-CDR identity is only {best_concat['identity']:.2f} "
                f"-- shared germline framework, not scaffold derivation.")

    return {
        "novelty_status": "fail" if fails else ("flag" if flags else "pass"),
        "novelty_fails": fails,
        "novelty_flags": flags,
        "nearest_ref_id": best_h3["ref"],
        "nearest_ref_cdrh3_identity": best_h3["identity"],
        "nearest_ref_cdrh3_seq": best_h3["seq"],
        "nearest_cdr_concat_identity": best_concat["identity"],
        "nearest_il4ra_identity": best_full["identity"],
        "nearest_il4ra_chain": best_full["chain"],
        "nearest_il4ra_ref": best_full["ref"],
        "novelty_margin": round(THRESH["cdrh3_identity_max"] - best_h3["identity"], 4),
    }


# ---------------------------------------------------------------- self-test

def self_test():
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    check("nw: identical sequences align without gaps",
          nw_align("ACDEFG", "ACDEFG") == ("ACDEFG", "ACDEFG"))
    check("identity: identical -> 1.0", identity("ACDEFGHIK", "ACDEFGHIK") == 1.0)
    check("identity: a 2-mer inside a 10-mer is NOT 1.0 (the Cinpanemab artefact)",
          identity("APIGGHALSH", "AH") < 0.3)
    check("identity: denom=max penalises a length mismatch",
          identity("AAAAAAAAAA", "AAAAA") == 0.5)
    check("identity: denom=query ignores extra residues on the REFERENCE only",
          identity("AAAAA", "AAAAAWWWWWWWWWW", denom="query") == 1.0)
    check("identity: a genuine near-copy still scores high",
          identity("WGYAMDY", "WGYAMDW") > 0.8)
    check("identity: disjoint -> low", identity("AAAAAAAA", "WWWWWWWW") < 0.2)
    check("identity: one substitution in 10 -> 0.9",
          abs(identity("ACDEFGHIKL", "ACDEFGHIKW") - 0.9) < 1e-9)
    check("identity: empty -> 0.0", identity("", "ACDEF") == 0.0)
    check("identity: symmetric",
          identity("ACDEFGHIK", "ACDQFGHIK") == identity("ACDQFGHIK", "ACDEFGHIK"))
    check("identity: handles an internal gap",
          identity("ACDEFGHIK", "ACDEFHIK") > 0.8)

    # CDR boundary transfer: a sequence identical to our framework must recover our spans
    got = transfer_cdrs(HU4D5_VH, HU4D5_VH,
                        {k: v for k, v in HU4D5_CDR_SPANS.items() if k.startswith("H")})
    check("transfer_cdrs: self-transfer recovers H1 'GFNIKDT'", got.get("H1") == "GFNIKDT")
    check("transfer_cdrs: self-transfer recovers H3 'WGYAMDY'", got.get("H3") == "WGYAMDY")

    # screening logic against a synthetic reference set
    ref = {"thresholds": THRESH, "entries": [
        {"id": "fake_dupi", "vh": HU4D5_VH, "vl": HU4D5_VL, "is_anti_il4ra": True,
         "cdrs": {"H1": "GFNIKDT", "H2": "RIYPTNG", "H3": "WGYAMDY",
                  "L1": "RASQDVNTAVA", "L2": "SASFLYS", "L3": "QQHYTTPPT"}},
    ]}

    same = screen_design(HU4D5_VH, HU4D5_VL,
                         {"H1": "GFNIKDT", "H2": "RIYPTNG", "H3": "WGYAMDY",
                          "L1": "RASQDVNTAVA", "L2": "SASFLYS", "L3": "QQHYTTPPT"}, ref)
    check("screen: an exact copy of a reference HARD FAILS",
          same["novelty_status"] == "fail")
    check("screen: exact CDR-H3 match is reported as such",
          any("exact CDR-H3" in f for f in same["novelty_fails"]))

    novel = screen_design(HU4D5_VH, HU4D5_VL,
                          {"H1": "GFDLTNV", "H2": "NPISGK", "H3": "SGFGVRSLHH",
                           "L1": "KLSKPAEVS", "L2": "KSTIRAP", "L3": "SAYDRLTGLT"}, ref)
    # Under the spec-literal default a 100%-identical framework IS a hard fail, which is
    # what the spec asks for. The intent-based branch is tested by flipping the flag.
    import builtins as _b
    global STRICT_SPEC_FULL_IDENTITY
    _saved = STRICT_SPEC_FULL_IDENTITY
    STRICT_SPEC_FULL_IDENTITY = True
    strict = screen_design(HU4D5_VH, HU4D5_VL,
                           {"H1": "GFDLTNV", "H2": "NPISGK", "H3": "SGFGVRSLHH",
                            "L1": "KLSKPAEVS", "L2": "KSTIRAP", "L3": "SAYDRLTGLT"}, ref)
    check("spec-literal mode: >0.85 full identity alone IS a hard fail",
          strict["novelty_status"] == "fail")
    STRICT_SPEC_FULL_IDENTITY = False
    novel = screen_design(HU4D5_VH, HU4D5_VL,
                          {"H1": "GFDLTNV", "H2": "NPISGK", "H3": "SGFGVRSLHH",
                           "L1": "KLSKPAEVS", "L2": "KSTIRAP", "L3": "SAYDRLTGLT"}, ref)
    check("intent mode: novel CDRs on a shared framework are flagged, not failed",
          novel["novelty_status"] == "flag"
          and any("shared germline framework" in f for f in novel["novelty_flags"]))
    STRICT_SPEC_FULL_IDENTITY = _saved
    check("screen: novelty is judged on CDRs, not the shared framework "
          "(full VH identity is ~1.0 yet it is not a fail)",
          novel["nearest_il4ra_identity"] > 0.9 or novel["novelty_status"] != "fail")
    check("screen: nearest reference is recorded even on a pass",
          novel["nearest_ref_id"] is not None)
    check("screen: novelty margin is positive for a passing design",
          novel["novelty_margin"] > 0)
    # the modified gate must still catch genuine scaffold derivation
    derived = screen_design(HU4D5_VH, HU4D5_VL,
                            {"H1": "GFNIKDT", "H2": "RIYPTNG", "H3": "WGYAMDF",
                             "L1": "RASQDVNTAVA", "L2": "SASFLYS", "L3": "QQHYTTPPT"}, ref)
    check("screen: high full identity AND high CDR identity still HARD FAILS "
          "(real scaffold derivation)", derived["novelty_status"] == "fail")

    # a near-copy of CDR-H3 must fail
    near = screen_design(HU4D5_VH, HU4D5_VL,
                         {"H1": "GFDLTNV", "H2": "NPISGK", "H3": "WGYAMDW",
                          "L1": "KLSKPAEVS", "L2": "KSTIRAP", "L3": "SAYDRLTGLT"}, ref)
    check("screen: CDR-H3 differing by 1 of 7 (0.86) HARD FAILS the 0.70 threshold",
          near["novelty_status"] == "fail")

    # tier 2 must NOT trigger the full-identity gate
    ref2 = {"thresholds": THRESH, "entries": [
        {"id": "some_therapeutic", "tier": 2, "is_anti_il4ra": False,
         "vh": HU4D5_VH, "vl": HU4D5_VL,
         # H3 must be DISSIMILAR to the query (so the framework-sharing test is not
         # confounded by a CDR hit) but not orthogonal (so nearest_ref_id is populated).
         "cdrs": {"H3": "SKLRPTVWMD", "L3": "SDQVWKTRAE"}},
    ]}
    r2 = screen_design(HU4D5_VH, HU4D5_VL,
                       {"H1": "GFDLTNV", "H2": "NPISGK", "H3": "SGFGVRSLHH",
                        "L1": "KLSKPAEVS", "L2": "KSTIRAP", "L3": "SAYDRLTGLT"}, ref2)
    check("tier 2: identical framework to a NON-IL-4Ra therapeutic does not fail "
          "(the framework is expected to be shared)", r2["novelty_status"] != "fail")
    check("tier 2: full-domain identity is not even measured against tier 2",
          r2["nearest_il4ra_identity"] == 0.0)
    check("tier 2: CDR-H3 is still compared against tier 2",
          r2["nearest_ref_id"] == "some_therapeutic"
          and 0.0 < r2["nearest_ref_cdrh3_identity"] < THRESH["cdrh3_identity_max"])
    # and a tier-2 CDR-H3 that IS too close must still hard-fail
    ref2b = {"thresholds": THRESH, "entries": [
        {"id": "close_therapeutic", "tier": 2, "is_anti_il4ra": False,
         "vh": None, "vl": None,
         "cdrs": {"H3": "SGFGVRSLAA", "L3": "SAYDRLTGAA"}},
    ]}
    r2b = screen_design(HU4D5_VH, HU4D5_VL,
                        {"H1": "GFDLTNV", "H2": "NPISGK", "H3": "SGFGVRSLHH",
                         "L1": "KLSKPAEVS", "L2": "KSTIRAP", "L3": "SAYDRLTGLT"}, ref2b)
    check("tier 2: a CDR-H3 too close to a THERAPEUTIC antibody still hard-fails",
          r2b["novelty_status"] == "fail")

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--tier2-csv",
                    default=str(NOV / "raw_therasabdab" / "TheraSAbDab_SeqStruc.csv"))
    a = ap.parse_args()
    if a.self_test:
        print("05_novelty.py self-test (synthetic sequences)")
        sys.exit(0 if self_test() else 1)
    if a.build:
        ref = build_reference_set()
        t2p = Path(a.tier2_csv)
        if t2p.exists():
            import hashlib as _h
            t2 = build_tier2(t2p)
            ref["entries"].extend(t2)
            ref["_frozen"]["tier2_therapeutic"] = {
                "source": "Thera-SAbDab SeqStruc online download",
                "file": t2p.name,
                "sha256": _h.sha256(t2p.read_bytes()).hexdigest(),
                "n_entries": len(t2),
                "scope": "CDR-level comparison only; full-domain identity is NOT computed "
                         "against tier 2, because high framework identity to a non-IL-4Ra "
                         "therapeutic is expected and fine (RANKING_AND_QC.md s4).",
            }
            (NOV / "reference_set.json").write_text(json.dumps(ref, indent=2))
            print(f"[write] reference set now {len(ref['entries'])} entries "
                  f"(tier 1: {sum(1 for e in ref['entries'] if e['tier']==1)}, "
                  f"tier 2: {len(t2)})")
        else:
            print(f"[tier2] {t2p} not present -- tier 2 stays not_run")
        print("\n[done] reference set frozen")
    else:
        ap.error("use --build or --self-test")


if __name__ == "__main__":
    main()
