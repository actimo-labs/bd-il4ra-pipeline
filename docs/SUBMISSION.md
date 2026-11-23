# SUBMISSION.md — Dr. G procedure and pre-flight

**This stage is human-in-the-loop. The user drives Dr. G. Claude prepares and validates
the file and never submits anything externally.**

Start at **T−6h (Tue 24 Nov ~10:00 AEDT) at the latest.** Dr. G runs its own upload
validator and a bioinformatics check that can reject the file and send you back to fix
and re-upload. Do not discover that at T−1h.

---

## 1. What actually gets submitted

> **CORRECTED 2026-11-22 against the real template.** The section below originally
> described a five-column sheet with `CL Type` = "human kappa". **That was wrong in four
> ways and would have been rejected.** The authoritative file is
> `docs/TurboCHO_IgG_AA_Seperate_Region.xlsx`
> (sha256 `b6f59ebc00728dbb20173fd7737da800b0e05465ed65fdaab22eb1e1b209f751`),
> archived in this repo. Per §2 of this document, **the template wins.**

The template is `TurboCHO_IgG_AA_Seperate_Region.xlsx`. It has **two sheets**:

- **`IgG Seperate Region`** — the data sheet (note GenScript's spelling of "Seperate";
  match it exactly). Rows 2–961 are available.
- **`Constant Region Seq`** — the lookup table the auto-fill formulas and the dropdowns
  both point at. **It must survive into the submitted file.**

### The eight columns, in order

| # | Column header (exact) | What goes in it |
|---|---|---|
| A | `Antibody #` | **FORMULA — do not type.** `=IF(B2="","",COUNTA($B$2:B2))` |
| B | `Antibody Name` | Our candidate ID. **Capital N** |
| C | `VH Seq` | **VH variable domain only** |
| D | `CH Type` | Dropdown, see below |
| E | `CH Seq (Auto-fill)` | **FORMULA — do not type.** `VLOOKUP` on `CH Type` |
| F | `VL Seq` | **VL variable domain only** |
| G | `CL Type` | Dropdown, see below |
| H | `CL Seq (Auto-fill)` | **FORMULA — do not type.** `VLOOKUP` on `CL Type` |

### The dropdown values — these are the exact strings

Read from the data-validation ranges in the template, not from prose:

- **`CH Type`** (validation `D2:D961` → `'Constant Region Seq'!$A$3:$A$5`):
  `Human IgG1` · `Human IgG4` · `Rabbit IgG`
- **`CL Type`** (validation `G2:G961` → `'Constant Region Seq'!$D$3:$D$6`):
  **`Human Ig Kappa`** · `Human Ig Lambda` · `Rabbit Ig Kappa` · `Rabbit Ig Lambda`

> **`Human Kappa` IS NOT A VALID VALUE.** The correct string is **`Human Ig Kappa`**.
> This document specified the wrong one and `build_submission.py` hardcoded it; all 20
> rows would have carried an invalid enum. `build_submission.py` now reads these lists
> out of the template at runtime and has a regression test asserting `Human Kappa` is
> rejected.

> **Please enter ONLY your protein sequences – we will automatically add a signal peptide
> `MGWSCIILFLVATATGVHS` for you.**

### Fill the template; never generate your own workbook

Building a fresh `.xlsx` with the right headers **loses the dropdowns, the auto-fill
formulas, and the `Constant Region Seq` sheet those formulas depend on.** The result
looks correct and is inert. `build_submission.py` opens the supplied template read-only,
writes into a copy, retargets the row-2 formulas to each row (`B2`→`B7`, `$B$2` left
absolute), clears the shipped `IgG Example  1` row, then **re-opens the output and
verifies it** — deleting the file and exiting non-zero on any failure.

### Five ways to get this wrong, all fatal, all silent

1. **Wrong `CL Type` string.** `Human Kappa` ≠ `Human Ig Kappa`. See above.
2. **Including a signal peptide.** GenScript prepends theirs. Two leaders = dead
   construct. Hard-gated by the eligibility screen (`RANKING_AND_QC.md` §2).
3. **Including constant domains in `VH Seq` / `VL Seq`.** `CH Type` supplies CH. A VH
   field containing VH+CH1 produces a duplicated constant region. `build_submission.py`
   detects the CH1/CL N-terminal motifs and applies a length ceiling.
4. **Typing values into the auto-fill columns** instead of leaving the formulas.
5. **Dropping the `Constant Region Seq` sheet**, which silently breaks every auto-fill.

### Recommended constant regions

- **`CH Type` = `Human IgG1`** for all 20. Not a judgement call: the live challenge hub
  states the design format as **IgG1**, and the brief's own opening prompt says "human
  IgG1 format". The dropdown offers IgG4 — that exists for reduced effector function,
  irrelevant to Carterra LSA. **Do not use it.** Keep all 20 identical so the assay
  compares paratopes, not isotypes.
- **`CL Type` = `Human Ig Kappa`**, matched to the VL framework. hu-4D5-8 is kappa.
  A kappa VL fused to a lambda CL is a mismatched chimera. Verified per row, not once.

### Candidate naming

Encode traceability, but stay inside whatever GenScript's validator tolerates:
**alphanumerics and hyphens only, no spaces, ≤30 characters.**

```
BDIL4R-E1-H4D5-RFAB-007
       │   │    │     └─ index
       │   │    └─ generator: RFAB | GEOD
       │   └─ framework: H4D5 | GERM
       └─ epitope arm: E1 | E2 | E3
```

The same ID must appear in `candidates.tsv`, the submitted Excel, and the model files we
keep. The brief says methodology and structural models **may be requested by e-mail** —
in January, this ID is the only thing linking a lab result back to a design.

---

## 2. Pre-flight — all of this before opening Dr. G

```bash
# the two modules you author; see CLAUDE.md section 10
# build_submission.py needs openpyxl -> run it in the boltz env, not bare python3
bash scripts/00_run_all_selftests.sh          # expect "20/20 modules clean"

~/miniforge3/bin/conda run -n boltz python scripts/build_submission.py \
    --manifest candidates.tsv \
    --template docs/TurboCHO_IgG_AA_Seperate_Region.xlsx \
    --out submission/round1.xlsx \
    --ch-type "Human IgG1" --cl-type "Human Ig Kappa" --expect 20 --rename

# build_submission.py MUST exit non-zero and write nothing if any check below fails.
# A builder that writes a file "with warnings" will get a bad file submitted at 3am.
```

- [ ] Exactly **20** rows, no blanks, no 21st row hiding below
- [ ] All 20 `(VH, VL)` pairs **unique**
- [ ] All 20 `Antibody name` values unique, ≤30 chars, alphanumeric+hyphen only
- [ ] **No signal peptide** on any sequence; none starts with `MGWSCIILFLVATATGVHS`
- [ ] No constant-domain residues in `VH Seq` / `VL Seq`
- [ ] Alphabet: 20 standard amino acids only. No `X B Z J U O *`, no digits, no spaces, no lowercase, **no trailing whitespace** (a trailing space is the classic silent validator failure)
- [ ] **Exactly 2 Cys per variable domain** on every design
- [ ] `CH Type` = `Human IgG1` on all rows; `CL Type` = `Human Ig Kappa` on all rows
- [ ] Columns A / E / H still contain FORMULAS, not pasted values
- [ ] The `Constant Region Seq` sheet is still present in the submitted file
- [ ] The shipped `IgG Example  1` row is gone
- [ ] Every row passes the novelty screen (`RANKING_AND_QC.md` §4)
- [ ] Final 20 are diversity-spread across arms / frameworks / generators as selected
- [ ] `candidates.tsv` complete, every uncomputed metric literally `not_run`
- [ ] Structural models for all 20 archived on scratch and **indexed by candidate ID**
- [ ] `RUNLOG.md` current
- [ ] GenScript login **tested** (do not test it for the first time now), using the
      **challenge-specific account** from the official e-mail — the credit coupon is
      attached to that account and no other

**Build the file into the template downloaded from the Dr. G flow.** Do not hand-roll an
Excel and assume the columns match. Verify the live column spec against the downloaded
template — a prior campaign nearly shipped an invalid enum value by trusting a
paraphrase. If the live template disagrees with this document, **the template wins** and
this document gets corrected.

---

## 3. The Dr. G flow

Entry point: the AIDD Solutions page on genscript.com. Click the **AIDD Agent** widget
bottom-right, use the **expand icon** (top-right of the chat box) for full screen, click
**Log-in**, enter the credentials from the official challenge e-mail, then
**New Conversation**.

### Step 1 — opening request

```
Looking to express 20 AI-designed antibody sequences in a human IgG1 format and evaluate binding to Human IL-4R alpha (CD124) using LSA 1-concentration.
```

### Step 2 — antigen selection

The Antigen Selection dialog appears. Click **Search** and find **exactly**:

```
Human IL-4 R alpha / CD124 Protein, Fc Tag, low endotoxin (MALS verified)
```

Select **100µg/EA** in the size column, then **Submit**.

> Multiple antigens appear with different tags (His, Fc, …). **Check the full name and the
> size before submitting.** Picking a His-tagged variant or the wrong size is not
> something you can quietly undo.

### Step 3 — verify the Proposal Summary

| Field | Expected |
|---|---|
| Format | **IgG** |
| Sequence Count | **20** |
| Cost per Sequence | **152.5 USD** |
| Assay Service | **Carterra LSA** |

**If any field differs, stop and resolve it before continuing.**

### Step 4 — skip the quote

```
No quote needed, create an order directly.
```

### Step 5 — upload

Download the batch template from the flow. Fill `Antibody name`, `VH Seq`, `CH Type`,
`VL Seq`, `CL Type` — leave `CH Seq` to autofill. Upload with the **paperclip** icon.

### Step 6 — validation. **The real gate.**

The Data Validation dialog must show:

- **20 records**
- **"Validation successful, no error data"**

Dr. G then parses the sequences and runs a bioinformatics check.

> **If any sequence Fails: fix the Excel as prompted and upload again. Do NOT go on to
> confirm the order.**

Record what failed and why in `RUNLOG.md` before fixing it — it is real information about
their validator, and you may need it again on the re-upload.

### Step 7 — project details

```
Please use PO BB20261112. Project Name: AIDD-test. No Comments. Please show me the order preview before creating the order.
```

> PO and project name are quoted verbatim from the brief. **If your challenge e-mail gives
> a different PO or project name, the e-mail wins.**

### Step 8 — verify the order preview. **ABORT CONDITION.**

| Field | Expected |
|---|---|
| Item Count | **22** (20 sequences + assay service + antigen) |
| Coupon | **Beyond Binding Challenge Credit, applied automatically** |
| **Estimated total** | **0.00 USD** |

> **If the estimated total is anything other than 0.00 USD, do NOT continue.** Submission
> requires no fee or payment. A non-zero total means something is wrong with the account
> or the coupon — e-mail `proteinchallenge@genscript.com` rather than proceeding.

### Step 9 — confirm

**Do not close the conversation before confirming.**

```
Yes, please create the order.
```

### Step 10 — record

When the Order Summary appears, the sequences are submitted.

- [ ] **Order No. recorded in `RUNLOG.md`**
- [ ] Screenshot the Order Summary into `submission/`
- [ ] The exact submitted `.xlsx` committed to `submission/` — the file as uploaded, byte for byte
- [ ] Confirm progress with `Check my Order` in the chat

---

## 4. After submission

The designs are frozen. Round 1 results land **13–18 Jan 2027** and Round 2 is
developability, so spend the remaining time while the context is still in your head:

- [ ] Write `submission/METHODS.md` — generators, versions, commit SHAs, parameters,
      seeds, epitope definitions, filters, thresholds, ranking scheme. The brief says
      methodology **may be requested by e-mail**; have it ready rather than reconstructing
      it in January.
- [ ] Export and commit all Geodesic outputs for the submitted 20, including **OASis
      humanness** — directly reusable as Round 2 developability evidence
      (`GEODESIC.md` §6)
- [ ] Archive structural models for all 20, indexed by candidate ID
- [ ] Commit `candidates.tsv` including every **rejected** candidate and its rejection
      reason
- [ ] Note in `METHODS.md` which claims are `measured`, `predicted` and `not_run`. **No
      design is described as a validated binder** — Round 1 has not run yet
- [ ] Post-mortem in `RUNLOG.md`: what the 66 hours actually cost, measured throughput,
      what to install **before** the next campaign. Append RFantibody and ANARCI to the
      §6 "not installed" list in `VM_INVENTORY.md` with their real install cost, so the
      next campaign budgets it instead of assuming it
