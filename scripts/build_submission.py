#!/usr/bin/env python
"""
build_submission.py -- fill the OFFICIAL GenScript batch template and validate it.

Spec: docs/SUBMISSION.md sections 1-2, CORRECTED against the real template
      (TurboCHO_IgG_AA_Seperate_Region.xlsx, sha256 b6f59ebc0072...).

CHALLENGE_SPEC.md trap 6: "Verify the submission column spec from the live template,
never from memory or a paraphrase of this doc. A prior campaign nearly shipped an
invalid enum value." That trap was live here. The real template disagrees with
docs/SUBMISSION.md in four ways, any one of which is a silent rejection:

  1. CL Type is 'Human Ig Kappa', NOT 'Human Kappa'. The dropdown at G2:G961 is bound
     to 'Constant Region Seq'!$D$3:$D$6 = Human Ig Kappa / Human Ig Lambda /
     Rabbit Ig Kappa / Rabbit Ig Lambda. 'Human Kappa' is not a member.
  2. There are EIGHT columns, not five, in a fixed order, including two auto-fill
     columns interleaved between the ones we populate.
  3. The header is 'Antibody Name' (capital N), not 'Antibody name'.
  4. Columns A, E and H are FORMULAS, not values:
        A: =IF(B2="","",COUNTA($B$2:B2))
        E: =IF(D2="","",VLOOKUP(D2,'Constant Region Seq'!$A$3:$C$6,2,0))
        H: =IF(G2="","",VLOOKUP(G2,'Constant Region Seq'!$D$3:$F$6,2,0))

So we FILL THE SUPPLIED TEMPLATE rather than building a workbook from scratch.
Generating our own would silently drop the dropdowns, the auto-fill formulas and the
'Constant Region Seq' sheet they depend on. The template file itself is opened
read-only and never modified; output always goes to a new path.

THIS SCRIPT REFUSES TO WRITE ON ANY VALIDATION ERROR and exits non-zero.
It does NOT submit anything. Dr. G is human-in-the-loop; the user drives it.

Run:  conda run -n boltz python scripts/build_submission.py --manifest candidates.tsv \
          --template <official.xlsx> --out submission/round1.xlsx
Test: python3 scripts/build_submission.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

AA = set("ACDEFGHIKLMNPQRSTVWY")
GENSCRIPT_SIGNAL = "MGWSCIILFLVATATGVHS"
NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,30}$")
NOT_RUN = "not_run"

DEFAULT_TEMPLATE = ("/mnt/comp5data/bd-il4r/submission_template/"
                    "TurboCHO_IgG_AA_Seperate_Region.xlsx")
TEMPLATE_SHA256 = "b6f59ebc00728dbb20173fd7737da800b0e05465ed65fdaab22eb1e1b209f751"

SHEET = "IgG Seperate Region"
HEADERS = ["Antibody #", "Antibody Name", "VH Seq", "CH Type",
           "CH Seq (Auto-fill)", "VL Seq", "CL Type", "CL Seq (Auto-fill)"]
COL = {h: i + 1 for i, h in enumerate(HEADERS)}
AUTOFILL_COLS = ("Antibody #", "CH Seq (Auto-fill)", "CL Seq (Auto-fill)")
FIRST_DATA_ROW = 2

# Read from the template's own dropdown ranges at runtime; these are the fallbacks.
CH_TYPES = ["Human IgG1", "Human IgG4", "Rabbit IgG"]
CL_TYPES = ["Human Ig Kappa", "Human Ig Lambda", "Rabbit Ig Kappa", "Rabbit Ig Lambda"]

CH1_MOTIFS = ["ASTKGPSVFPLAP", "SSASTKGPSV"]
CL_MOTIFS = ["RTVAAPSVFIFPPS", "TVAAPSVFIFPP"]
MAX_V_LEN = 140


class ValidationError(Exception):
    pass


# ---------------------------------------------------------------- template

def read_template_spec(path):
    """Read headers and the REAL dropdown enums out of the supplied template.

    Enums come from the cells the data-validation ranges point at, not from a constant
    in this file, so the template stays the authority even if it is revised.
    """
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=False)
    if SHEET not in wb.sheetnames:
        raise ValidationError(f"template has no sheet {SHEET!r}; sheets are {wb.sheetnames}")
    ws = wb[SHEET]
    headers = [ws.cell(row=1, column=c).value for c in range(1, len(HEADERS) + 1)]
    cr = wb["Constant Region Seq"] if "Constant Region Seq" in wb.sheetnames else None
    ch, cl = [], []
    if cr is not None:
        ch = [cr.cell(row=r, column=1).value for r in range(3, 6)]
        cl = [cr.cell(row=r, column=4).value for r in range(3, 7)]
    return {
        "headers": headers,
        "ch_types": [x for x in ch if x],
        "cl_types": [x for x in cl if x],
        "formulas": {
            "Antibody #": ws.cell(row=2, column=COL["Antibody #"]).value,
            "CH Seq (Auto-fill)": ws.cell(row=2, column=COL["CH Seq (Auto-fill)"]).value,
            "CL Seq (Auto-fill)": ws.cell(row=2, column=COL["CL Seq (Auto-fill)"]).value,
        },
    }


def retarget_formula(f, row):
    """Move a row-2 template formula to `row`, keeping $absolute refs fixed."""
    if not isinstance(f, str) or not f.startswith("="):
        return f
    # replace relative row 2 refs (B2, D2, G2) but never $B$2
    return re.sub(r"(?<![$A-Za-z0-9])([A-Z]{1,2})2(?![0-9])",
                  lambda m: f"{m.group(1)}{row}", f)


# ---------------------------------------------------------------- validation

def validate_rows(rows, ch_type, cl_type, expect=20,
                  ch_allowed=None, cl_allowed=None):
    errs, checks = [], []
    ch_allowed = ch_allowed or CH_TYPES
    cl_allowed = cl_allowed or CL_TYPES

    def ck(ok, msg):
        checks.append(("PASS" if ok else "FAIL", msg))
        if not ok:
            errs.append(msg)

    ck(len(rows) == expect, f"row count is {len(rows)}, expected exactly {expect}")

    ck(ch_type in ch_allowed,
       f"CH Type {ch_type!r} is not in the template dropdown {ch_allowed}")
    ck(cl_type in cl_allowed,
       f"CL Type {cl_type!r} is not in the template dropdown {cl_allowed}")

    names = [r["Antibody Name"] for r in rows]
    ck(len(set(names)) == len(names),
       f"antibody names must be unique ({len(names) - len(set(names))} duplicates)")
    bad_names = [n for n in names if not NAME_RE.match(str(n))]
    ck(not bad_names, f"names must be alphanumeric+hyphen, <=30 chars: {bad_names[:3]}")

    pairs = [(r["VH Seq"], r["VL Seq"]) for r in rows]
    ck(len(set(pairs)) == len(pairs),
       f"(VH,VL) pairs must be unique ({len(pairs) - len(set(pairs))} duplicates)")

    for r in rows:
        n = r["Antibody Name"]
        ck(r["CH Type"] == ch_type, f"{n}: CH Type is {r['CH Type']!r}, expected {ch_type!r}")
        ck(r["CL Type"] == cl_type, f"{n}: CL Type is {r['CL Type']!r}, expected {cl_type!r}")
        for field in ("VH Seq", "VL Seq"):
            s = r[field]
            ck(bool(s), f"{n}: {field} is empty")
            if not s:
                continue
            ck(s == s.strip(), f"{n}: {field} has leading/trailing whitespace")
            ck(" " not in s, f"{n}: {field} contains an internal space")
            ck(s == s.upper(), f"{n}: {field} contains lowercase")
            bad = sorted(set(s) - AA)
            ck(not bad, f"{n}: {field} has non-standard residues {bad}")
            ck(not s.startswith(GENSCRIPT_SIGNAL),
               f"{n}: {field} starts with the GenScript signal peptide")
            ck(s.count("C") == 2,
               f"{n}: {field} has {s.count('C')} Cys, expected exactly 2")
            ck(len(s) <= MAX_V_LEN,
               f"{n}: {field} is {len(s)} aa (>{MAX_V_LEN}) -- looks like it carries "
               f"a constant domain")
            for m in (CH1_MOTIFS if field == "VH Seq" else CL_MOTIFS):
                ck(m not in s, f"{n}: {field} contains constant-domain motif '{m}'")
    return checks, errs


def rows_from_manifest(path, selected_only=True):
    rows = list(csv.DictReader(open(path), delimiter="\t"))
    if selected_only:
        rows = [r for r in rows if str(r.get("selected", "")).lower() == "yes"]
    if not rows:
        raise ValidationError(
            f"no rows with selected=yes in {path} -- run 08_rank_select.py first. "
            f"Refusing to guess which designs to submit.")
    return [{
        "Antibody Name": r["candidate_id"],
        "VH Seq": (r.get("vh_seq") or "").strip(),
        "CH Type": r.get("ch_type") or "",
        "VL Seq": (r.get("vl_seq") or "").strip(),
        "CL Type": r.get("cl_type") or "",
        "_src": r,
    } for r in rows]


def make_name(arm, framework, generator, idx):
    fw = {"hu4D5-8": "H4D5", "germline": "GERM"}.get(framework, "UNKN")
    gn = {"rfantibody": "RFAB", "geodesic": "GEOD"}.get(generator, "UNKN")
    return f"BDIL4R-{arm}-{fw}-{gn}-{idx:03d}"


def fill_template(rows, template, out, spec):
    """Write rows into a COPY of the official template, preserving formulas."""
    import openpyxl
    wb = openpyxl.load_workbook(template, data_only=False)
    ws = wb[SHEET]

    # clear every pre-existing data row (the shipped example, and anything else)
    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        for c in range(1, len(HEADERS) + 1):
            ws.cell(row=row, column=c).value = None

    for i, r in enumerate(rows):
        row = FIRST_DATA_ROW + i
        ws.cell(row=row, column=COL["Antibody Name"]).value = r["Antibody Name"]
        ws.cell(row=row, column=COL["VH Seq"]).value = r["VH Seq"]
        ws.cell(row=row, column=COL["CH Type"]).value = r["CH Type"]
        ws.cell(row=row, column=COL["VL Seq"]).value = r["VL Seq"]
        ws.cell(row=row, column=COL["CL Type"]).value = r["CL Type"]
        # auto-fill columns stay FORMULAS, retargeted to this row
        for h in AUTOFILL_COLS:
            f = spec["formulas"].get(h)
            if f:
                ws.cell(row=row, column=COL[h]).value = retarget_formula(f, row)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def verify_written(out, rows, spec):
    """Re-open what we wrote and check it. Never trust the writer."""
    import openpyxl
    wb = openpyxl.load_workbook(out, data_only=False)
    problems = []
    if SHEET not in wb.sheetnames:
        return [f"output has no sheet {SHEET!r}"]
    ws = wb[SHEET]
    hdr = [ws.cell(row=1, column=c).value for c in range(1, len(HEADERS) + 1)]
    if hdr != spec["headers"]:
        problems.append(f"headers changed: {hdr} != {spec['headers']}")
    n = 0
    for i, r in enumerate(rows):
        row = FIRST_DATA_ROW + i
        if ws.cell(row=row, column=COL["Antibody Name"]).value != r["Antibody Name"]:
            problems.append(f"row {row}: name mismatch")
        if ws.cell(row=row, column=COL["VH Seq"]).value != r["VH Seq"]:
            problems.append(f"row {row}: VH mismatch")
        if ws.cell(row=row, column=COL["VL Seq"]).value != r["VL Seq"]:
            problems.append(f"row {row}: VL mismatch")
        for h in AUTOFILL_COLS:
            v = ws.cell(row=row, column=COL[h]).value
            if spec["formulas"].get(h) and not (isinstance(v, str) and v.startswith("=")):
                problems.append(f"row {row}: {h} is not a formula ({v!r})")
        n += 1
    # nothing below the last data row
    extra = [row for row in range(FIRST_DATA_ROW + len(rows), ws.max_row + 1)
             if ws.cell(row=row, column=COL["Antibody Name"]).value not in (None, "")]
    if extra:
        problems.append(f"rows below the data block are not empty: {extra[:5]}")
    if "Constant Region Seq" not in wb.sheetnames:
        problems.append("the 'Constant Region Seq' sheet the auto-fill depends on is missing")
    return problems


# ---------------------------------------------------------------- self-test

def self_test():
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    VH = ("EVQLVESGGGLVQPGGSLRLSCAASGFDLTNVYIHWVRQAPGKGLEWVARINPISGKTRYADSVKGRFTIS"
          "ADTSKNTAYLQMNSLRAEDTAVYYCSRSGFGVRSLHHWGQGTLVTVSS")
    VL = ("DIQMTQSPSSLSASVGDRVTITCKLSKPAEVSWYQQKPGKAPKLLIYKSTIRAPGVPSRFSGSRSGTDFTL"
          "TISSLQPEDFATYYCSAYDRLTGLTFGQGTKVEIK")

    def mk(i, vh=VH, vl=VL, name=None, ch="Human IgG1", cl="Human Ig Kappa"):
        return {"Antibody Name": name or f"BDIL4R-E1-H4D5-RFAB-{i:03d}",
                "VH Seq": vh, "VL Seq": vl, "CH Type": ch, "CL Type": cl}

    SUBS = "ADEFGHIKLMNPQRSTVWYA"
    assert "C" not in SUBS
    good = [mk(i, vh=VH[:100] + SUBS[i] + VH[101:]) for i in range(20)]
    good[19]["VH Seq"] = VH[:100] + "A" + VH[101:102] + "W" + VH[103:]

    _, errs = validate_rows(good, "Human IgG1", "Human Ig Kappa", 20)
    check("20 valid designs pass with the REAL enum values", not errs)
    if errs:
        print("     ", errs[:3])

    def fails(rows, substr, ch="Human IgG1", cl="Human Ig Kappa", expect=20):
        _, e = validate_rows(rows, ch, cl, expect)
        return any(substr in x for x in e)

    # the exact trap this file exists to prevent
    check("'Human Kappa' (the value SUBMISSION.md specifies) is REJECTED",
          fails([dict(r, **{"CL Type": "Human Kappa"}) for r in good],
                "not in the template dropdown", cl="Human Kappa"))
    check("'Human Ig Lambda' is a valid enum but is rejected as a mismatch here",
          fails([dict(r, **{"CL Type": "Human Ig Lambda"}) for r in good], "CL Type"))
    check("an invalid CH Type is rejected",
          fails(good, "not in the template dropdown", ch="Mouse IgG2a"))

    check("wrong row count is fatal", fails(good[:19], "row count"))
    check("duplicate (VH,VL) pair is fatal",
          fails(good[:19] + [mk(99, name="BDIL4R-X-1")], "pairs must be unique"))
    check("signal peptide on VH is fatal",
          fails(good[:19] + [mk(99, vh=GENSCRIPT_SIGNAL + VH)], "signal peptide"))
    check("trailing whitespace is fatal",
          fails(good[:19] + [mk(99, vh=VH[:50] + "W" + VH[51:] + " ")], "whitespace"))
    check("non-standard residue is fatal",
          fails(good[:19] + [mk(99, vh="X" + VH[1:])], "non-standard"))
    check("wrong Cys count is fatal",
          fails(good[:19] + [mk(99, vh=VH.replace("C", "A", 1))], "Cys"))
    check("CH1 constant-domain motif is fatal",
          fails(good[:19] + [mk(99, vh=VH + "ASTKGPSVFPLAP")], "constant-domain motif"))

    check("name format matches the spec",
          make_name("E1", "hu4D5-8", "rfantibody", 7) == "BDIL4R-E1-H4D5-RFAB-007")

    # formula retargeting
    check("formula retargeting moves relative refs but keeps absolute ones",
          retarget_formula('=IF(B2="","",COUNTA($B$2:B2))', 7)
          == '=IF(B7="","",COUNTA($B$2:B7))')
    check("formula retargeting handles the VLOOKUP auto-fill",
          retarget_formula(
              '=IF(D2="","",VLOOKUP(D2,\'Constant Region Seq\'!$A$3:$C$6,2,0))', 5)
          == '=IF(D5="","",VLOOKUP(D5,\'Constant Region Seq\'!$A$3:$C$6,2,0))')
    check("non-formula values pass through untouched",
          retarget_formula("Human IgG1", 9) == "Human IgG1")

    # end-to-end against the real template if present
    t = Path(DEFAULT_TEMPLATE)
    if t.exists():
        import tempfile
        spec = read_template_spec(t)
        check("template headers match what this script expects",
              spec["headers"] == HEADERS)
        check("template CL dropdown contains 'Human Ig Kappa'",
              "Human Ig Kappa" in spec["cl_types"])
        check("template CL dropdown does NOT contain 'Human Kappa'",
              "Human Kappa" not in spec["cl_types"])
        check("template CH dropdown contains 'Human IgG1'",
              "Human IgG1" in spec["ch_types"])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "filled.xlsx"
            fill_template(good, t, out, spec)
            probs = verify_written(out, good, spec)
            check("filled template re-opens and verifies clean", not probs)
            if probs:
                print("     ", probs[:3])
            import openpyxl
            wb = openpyxl.load_workbook(out)
            check("the shipped example row was removed",
                  wb[SHEET].cell(row=2, column=2).value != "IgG Example  1")
            check("template file itself was not modified",
                  hashlib.sha256(t.read_bytes()).hexdigest() == TEMPLATE_SHA256)
    else:
        print(f"  [skip] official template not at {DEFAULT_TEMPLATE}")

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--manifest", default="candidates.tsv")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--out", default="submission/round1.xlsx")
    ap.add_argument("--ch-type", default="Human IgG1")
    ap.add_argument("--cl-type", default="Human Ig Kappa")
    ap.add_argument("--expect", type=int, default=20)
    ap.add_argument("--rename", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        print("build_submission.py self-test")
        sys.exit(0 if self_test() else 1)

    t = Path(a.template)
    if not t.exists():
        print(f"REFUSING TO BUILD: no template at {t}. The official template is the "
              f"authority on columns and enum values; do not hand-build a workbook.")
        sys.exit(1)
    sha = hashlib.sha256(t.read_bytes()).hexdigest()
    print(f"[template] {t.name}  sha256 {sha[:16]}...")
    if sha != TEMPLATE_SHA256:
        print(f"[template] NOTE: sha256 differs from the one this script was written "
              f"against ({TEMPLATE_SHA256[:16]}...). Re-verify the column spec.")

    try:
        spec = read_template_spec(t)
        rows = rows_from_manifest(a.manifest)
    except (ValidationError, FileNotFoundError) as e:
        print(f"REFUSING TO BUILD: {e}")
        sys.exit(1)

    print(f"[template] CH dropdown: {spec['ch_types']}")
    print(f"[template] CL dropdown: {spec['cl_types']}")

    if a.rename:
        for i, r in enumerate(rows, 1):
            src = r["_src"]
            r["Antibody Name"] = make_name(src.get("epitope_arm", "E0"),
                                           src.get("framework", ""),
                                           src.get("generator", ""), i)
    for r in rows:
        r["CH Type"], r["CL Type"] = a.ch_type, a.cl_type

    checks, errs = validate_rows(rows, a.ch_type, a.cl_type, a.expect,
                                 spec["ch_types"], spec["cl_types"])
    n_fail = sum(1 for s, _ in checks if s == "FAIL")
    print(f"\n{'='*64}\nSUBMISSION PRE-FLIGHT  ({len(rows)} rows)\n{'='*64}")
    for status, msg in checks:
        if status == "FAIL":
            print(f"  [FAIL] {msg}")
    print(f"\n{len(checks) - n_fail}/{len(checks)} checks passed")

    if errs:
        print(f"\nREFUSING TO WRITE: {len(errs)} validation error(s).")
        sys.exit(1)

    out = fill_template(rows, t, a.out, spec)
    probs = verify_written(out, rows, spec)
    if probs:
        Path(out).unlink(missing_ok=True)
        print(f"\nREFUSING: the written file failed verification: {probs[:5]}")
        sys.exit(1)
    print(f"[write] {out}  (verified after writing)")
    print("\nNOTE: NOT submitted. Dr. G is human-in-the-loop and the user drives it.")


if __name__ == "__main__":
    main()
