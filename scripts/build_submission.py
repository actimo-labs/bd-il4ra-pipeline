#!/usr/bin/env python
"""
build_submission.py -- build and validate the GenScript batch submission table.

Spec: docs/SUBMISSION.md sections 1 and 2.

THIS SCRIPT MUST REFUSE TO WRITE ON ANY VALIDATION ERROR.
docs/SUBMISSION.md: "A builder that writes a file 'with warnings' will get a bad file
submitted at 3am." Every check is fatal. Exit code is non-zero and no file appears.

It does NOT submit anything. Submission to Dr. G is human-in-the-loop and the user
drives it.

Columns the template takes (variable domains only -- GenScript assembles the rest, and
prepends the signal peptide MGWSCIILFLVATATGVHS itself):

    Antibody name | VH Seq | CH Type | VL Seq | CL Type

Run:  python3 scripts/build_submission.py --manifest candidates.tsv \
          --out submission/round1.xlsx --ch-type "Human IgG1" --cl-type "Human Kappa"
Test: python3 scripts/build_submission.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

AA = set("ACDEFGHIKLMNPQRSTVWY")
GENSCRIPT_SIGNAL = "MGWSCIILFLVATATGVHS"
NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,30}$")
COLUMNS = ["Antibody name", "VH Seq", "CH Type", "VL Seq", "CL Type"]
NOT_RUN = "not_run"

# hallmarks of a constant domain accidentally left on a variable domain
CH1_MOTIFS = ["ASTKGPSVFPLAP", "SSASTKGPSV"]          # human IgG1 CH1 N-terminus
CL_MOTIFS = ["RTVAAPSVFIFPPS", "TVAAPSVFIFPP"]        # human kappa CL N-terminus
MAX_V_LEN = 140   # a variable domain longer than this almost certainly carries constant


class ValidationError(Exception):
    pass


def validate_rows(rows, ch_type, cl_type, expect=20):
    """Every check is fatal. Returns a list of human-readable check results."""
    errs, checks = [], []

    def ck(ok, msg):
        checks.append(("PASS" if ok else "FAIL", msg))
        if not ok:
            errs.append(msg)

    ck(len(rows) == expect, f"row count is {len(rows)}, expected exactly {expect}")

    names = [r["Antibody name"] for r in rows]
    ck(len(set(names)) == len(names),
       f"antibody names must be unique ({len(names) - len(set(names))} duplicates)")
    bad_names = [n for n in names if not NAME_RE.match(n)]
    ck(not bad_names,
       f"names must be alphanumeric+hyphen, <=30 chars: {bad_names[:3]}")

    pairs = [(r["VH Seq"], r["VL Seq"]) for r in rows]
    ck(len(set(pairs)) == len(pairs),
       f"(VH,VL) pairs must be unique ({len(pairs) - len(set(pairs))} duplicates)")

    ck(all(r["CH Type"] == ch_type for r in rows),
       f"every CH Type must be '{ch_type}'")
    ck(all(r["CL Type"] == cl_type for r in rows),
       f"every CL Type must be '{cl_type}'")

    for r in rows:
        n = r["Antibody name"]
        for field in ("VH Seq", "VL Seq"):
            s = r[field]
            ck(bool(s), f"{n}: {field} is empty")
            if not s:
                continue
            # trailing/leading whitespace -- the classic silent validator failure
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
            motifs = CH1_MOTIFS if field == "VH Seq" else CL_MOTIFS
            for m in motifs:
                ck(m not in s,
                   f"{n}: {field} contains constant-domain motif '{m}'")
    return checks, errs


def rows_from_manifest(path, selected_only=True):
    rows = list(csv.DictReader(open(path), delimiter="\t"))
    if selected_only:
        rows = [r for r in rows if str(r.get("selected", "")).lower() == "yes"]
    if not rows:
        raise ValidationError(
            f"no rows with selected=yes in {path} -- run 08_rank_select.py first. "
            f"Refusing to guess which designs to submit.")
    out = []
    for r in rows:
        out.append({
            "Antibody name": r["candidate_id"],
            "VH Seq": (r.get("vh_seq") or "").strip(),
            "CH Type": r.get("ch_type") or "",
            "VL Seq": (r.get("vl_seq") or "").strip(),
            "CL Type": r.get("cl_type") or "",
            "_src": r,
        })
    return out


def make_name(arm, framework, generator, idx):
    """BDIL4R-E1-H4D5-RFAB-007, per SUBMISSION.md section 1."""
    fw = {"hu4D5-8": "H4D5", "germline": "GERM"}.get(framework, "UNKN")
    gn = {"rfantibody": "RFAB", "geodesic": "GEOD"}.get(generator, "UNKN")
    return f"BDIL4R-{arm}-{fw}-{gn}-{idx:03d}"


def write_xlsx(rows, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        import openpyxl
    except ImportError:
        tsv = out.with_suffix(".tsv")
        with open(tsv, "w") as w:
            w.write("\t".join(COLUMNS) + "\n")
            for r in rows:
                w.write("\t".join(r[c] for c in COLUMNS) + "\n")
        print(f"[write] openpyxl unavailable -> wrote TSV instead: {tsv}")
        print("        Paste into the official template; do NOT hand-build the workbook.")
        return tsv
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(COLUMNS)
    for r in rows:
        ws.append([r[c] for c in COLUMNS])
    wb.save(out)
    print(f"[write] {out}")
    return out


def self_test():
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    VH = ("EVQLVESGGGLVQPGGSLRLSCAASGFDLTNVYIHWVRQAPGKGLEWVARINPISGKTRYADSVKGRFTIS"
          "ADTSKNTAYLQMNSLRAEDTAVYYCSRSGFGVRSLHHWGQGTLVTVSS")
    VL = ("DIQMTQSPSSLSASVGDRVTITCKLSKPAEVSWYQQKPGKAPKLLIYKSTIRAPGVPSRFSGSRSGTDFTL"
          "TISSLQPEDFATYYCSAYDRLTGLTFGQGTKVEIK")

    def mk(i, vh=VH, vl=VL, name=None, ch="Human IgG1", cl="Human Kappa"):
        return {"Antibody name": name or f"BDIL4R-E1-H4D5-RFAB-{i:03d}",
                "VH Seq": vh, "VL Seq": vl, "CH Type": ch, "CL Type": cl}

    # 20 unique designs (vary one CDR residue so pairs differ).
    # The substitution alphabet must EXCLUDE Cys, or the fixture itself creates a third
    # cysteine and trips the Cys-parity check it is meant to be a control for.
    SUBS = "ADEFGHIKLMNPQRSTVWYA"
    assert "C" not in SUBS
    good = []
    for i in range(20):
        v = VH[:100] + SUBS[i] + VH[101:]
        good.append(mk(i, vh=v))
    good[19]["VH Seq"] = VH[:100] + "A" + VH[101:102] + "W" + VH[103:]
    _, errs = validate_rows(good, "Human IgG1", "Human Kappa", 20)
    check("20 valid unique designs pass with no errors", not errs)
    if errs:
        print("     ", errs[:3])

    def fails(rows, substr, expect=20):
        _, e = validate_rows(rows, "Human IgG1", "Human Kappa", expect)
        return any(substr in x for x in e)

    check("wrong row count is fatal", fails(good[:19], "row count"))
    check("duplicate (VH,VL) pair is fatal",
          fails(good[:19] + [mk(99, vh=good[0]["VH Seq"], name="BDIL4R-X-1")],
                "pairs must be unique"))
    check("duplicate name is fatal",
          fails(good[:19] + [mk(0, vh=VH[:50] + "W" + VH[51:])], "names must be unique"))
    check("name with a space is fatal",
          fails(good[:19] + [mk(99, vh=VH[:50] + "W" + VH[51:], name="bad name")],
                "alphanumeric+hyphen"))
    check("name over 30 chars is fatal",
          fails(good[:19] + [mk(99, vh=VH[:50] + "W" + VH[51:], name="B" * 31)],
                "alphanumeric+hyphen"))
    check("signal peptide on VH is fatal",
          fails(good[:19] + [mk(99, vh=GENSCRIPT_SIGNAL + VH)], "signal peptide"))
    check("trailing whitespace is fatal",
          fails(good[:19] + [mk(99, vh=VH[:50] + "W" + VH[51:] + " ")], "whitespace"))
    check("lowercase is fatal",
          fails(good[:19] + [mk(99, vh=(VH[:50] + "W" + VH[51:]).lower())], "lowercase"))
    check("non-standard residue X is fatal",
          fails(good[:19] + [mk(99, vh="X" + VH[1:])], "non-standard"))
    check("wrong Cys count is fatal",
          fails(good[:19] + [mk(99, vh=VH.replace("C", "A", 1))], "Cys"))
    check("CH1 constant-domain motif on VH is fatal",
          fails(good[:19] + [mk(99, vh=VH + "ASTKGPSVFPLAP")], "constant-domain motif"))
    check("over-long variable domain is fatal",
          fails(good[:19] + [mk(99, vh=VH + "A" * 40)], "constant domain"))
    check("mismatched CL Type is fatal",
          fails(good[:19] + [mk(99, vh=VH[:50] + "W" + VH[51:], cl="Human Lambda")],
                "CL Type"))
    check("IgG4 instead of IgG1 is fatal",
          fails(good[:19] + [mk(99, vh=VH[:50] + "W" + VH[51:], ch="Human IgG4")],
                "CH Type"))
    check("empty VL is fatal",
          fails(good[:19] + [mk(99, vh=VH[:50] + "W" + VH[51:], vl="")], "empty"))

    check("name format matches the spec",
          make_name("E1", "hu4D5-8", "rfantibody", 7) == "BDIL4R-E1-H4D5-RFAB-007")
    check("generated names satisfy the validator",
          NAME_RE.match(make_name("E1", "hu4D5-8", "rfantibody", 7)) is not None)

    # the builder must refuse to write
    import tempfile
    d = Path(tempfile.mkdtemp())
    man = d / "c.tsv"
    man.write_text("candidate_id\tselected\tvh_seq\tvl_seq\tch_type\tcl_type\n")
    try:
        rows_from_manifest(man)
        refused = False
    except ValidationError:
        refused = True
    check("manifest with no selected=yes rows raises instead of guessing", refused)

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--manifest", default="candidates.tsv")
    ap.add_argument("--out", default="submission/round1.xlsx")
    ap.add_argument("--ch-type", default="Human IgG1")
    ap.add_argument("--cl-type", default="Human Kappa")
    ap.add_argument("--expect", type=int, default=20)
    ap.add_argument("--rename", action="store_true",
                    help="rewrite Antibody name to the BDIL4R-... scheme")
    a = ap.parse_args()

    if a.self_test:
        print("build_submission.py self-test (synthetic rows)")
        sys.exit(0 if self_test() else 1)

    try:
        rows = rows_from_manifest(a.manifest)
    except (ValidationError, FileNotFoundError) as e:
        print(f"REFUSING TO BUILD: {e}")
        sys.exit(1)

    if a.rename:
        for i, r in enumerate(rows, 1):
            src = r["_src"]
            r["Antibody name"] = make_name(src.get("epitope_arm", "E0"),
                                           src.get("framework", ""),
                                           src.get("generator", ""), i)

    checks, errs = validate_rows(rows, a.ch_type, a.cl_type, a.expect)
    print(f"\n{'='*64}\nSUBMISSION PRE-FLIGHT  ({len(rows)} rows)\n{'='*64}")
    shown = set()
    for status, msg in checks:
        if status == "FAIL" or msg not in shown:
            shown.add(msg)
            if status == "FAIL":
                print(f"  [FAIL] {msg}")
    n_fail = sum(1 for s, _ in checks if s == "FAIL")
    print(f"\n{len(checks) - n_fail}/{len(checks)} checks passed")

    if errs:
        print(f"\nREFUSING TO WRITE: {len(errs)} validation error(s).")
        print("docs/SUBMISSION.md: a builder that writes 'with warnings' gets a bad "
              "file submitted at 3am.")
        sys.exit(1)

    write_xlsx(rows, a.out)
    print("\nNOTE: this file is NOT submitted. Submission to Dr. G is human-in-the-loop "
          "and the user drives it.")


if __name__ == "__main__":
    main()
