# CHALLENGE_SPEC.md — verified official requirements

**GROUND TRUTH DOCUMENT.** Everything here is transcribed from the official Round 1
Challenge Brief (GenScript, dated 16 Nov 2026) or verified against a cited source.
Anything that is our own inference is explicitly marked **[ASSUMPTION]**.

Do not add a requirement to this file without a source. Do not act on a requirement
that is not in this file.

---

## 1. Identity

| Field | Value |
|---|---|
| Competition | GenScript LSRG x Geodesic **"Beyond Binding"** Challenge |
| Round | **Round 1 — Target Binding** |
| Brief date | 16 Nov 2026 |
| Official hub | https://www.genscript.com/genscript-lsrg-x-geodesic-beyond-binding-challenge-live.html |
| Challenge support | `proteinchallenge@genscript.com` |
| Geodesic support | `contact@geodesiclab.com` |

Two-round structure:

- **Round 1 — Target Binding.** Identify and rank antibody candidates binding IL-4Rα ECD
  using GenScript's **LSA 1-concentration** binding assay.
- **Round 2 — Developability Characterization.** Additional biophysical/developability
  assays on selected candidates.

Round 1 results expected **13–18 Jan 2027**. Round 2 details communicated around then.

---

## 2. Deadline

> **Round 1 Submission Deadline: November 23rd, 2026, 11:59 PM Eastern Time (EST)**

Eastern Standard Time = UTC−5 (US DST ended 1 Nov 2026).

| Zone | Deadline |
|---|---|
| ET | Mon 23 Nov 2026, 23:59 |
| UTC | Tue 24 Nov 2026, 04:59 |
| **AEDT (Melbourne)** | **Tue 24 Nov 2026, 15:59** |

Confirmed live as of 21 Nov 2026 via GenScript's own announcement
(same date, same deadline).

---

## 3. Target

| Field | Official value |
|---|---|
| Target | Interleukin-4 Receptor Alpha (**IL-4Rα / CD124**) |
| Species | **Human** |
| UniProt | **P24394-1** |
| Target domain | **AA 26–232**, IL-4Rα **extracellular domain (ECD)** |
| Reference structure cited in brief | **PDB 3BPN** |
| Target construct specification | IgG |
| **Design format** | **IgG1** — the live challenge hub states the design format as IgG1 specifically, not "IgG1 or IgG4" |

Biological context given by the brief: IL-4Rα is a clinically validated therapeutic
target and a central regulator of type 2 inflammation; it is the shared receptor
component for IL-4 and IL-13 signalling, implicated in atopic dermatitis, asthma,
chronic rhinosinusitis with nasal polyps, and eosinophilic esophagitis.

**Verified target annotations** (UniProt P24394, retrieved 21 Nov 2026):

| Feature | Positions |
|---|---|
| Signal peptide | 1–25 |
| Mature chain | 26–825 |
| **Topological domain, extracellular** | **26–232** — exactly matches the brief |
| Transmembrane | 233–256 |
| **N-linked glycosylation (CARBOHYD)** | **N53, N98, N128, N134, N176, N209** |
| Disulfide bonds | 34–44, 74–86 |
| Full length | 825 aa |

→ **All six N-glycosylation sequons lie inside the 207-residue ECD.** This is a heavily
glycosylated domain and it materially constrains epitope selection. See
`TARGET_PREP.md` §2.

---

## 4. The design task

> Participants are tasked with using AI-driven protein design approaches to generate
> novel IgG-format antibody candidates against human IL-4Rα ECD.

- **Maximum 20 antibody designs** per team, submitted for experimental evaluation.
- Each submission must include:
  - Antibody **heavy-chain** amino acid sequence
  - Antibody **light-chain** amino acid sequence
- Additional information **may** be requested by e-mail later:
  - Computational design methodology and supporting predictions
  - Predicted binding interface or structural model

→ **[IMPLICATION, acted on]** Because methodology and structural models may be requested,
the manifest, RUNLOG and per-design structural models must be retained and presentable.
Do not delete raw outputs for the designs we submit.

---

## 5. Novelty requirements — read literally

> All submitted antibody designs must be **de novo**, meaning they must be generated from
> scratch rather than derived from or modified from an existing antibody binder. Designs
> should demonstrate sufficient sequence diversity from known antibodies, with particular
> emphasis on the **complementarity-determining regions (CDRs)**, which are primarily
> responsible for antigen recognition. Participants may use publicly available protein
> data and known binders for **model training, benchmarking, or design evaluation**, but
> **must not use an existing IL-4Rα binder as the starting scaffold for sequence
> modification.**

GenScript may run similarity/novelty assessment against reference databases to identify
duplicate, highly similar or previously reported designs. Novelty assessment is for
challenge evaluation only and is not a determination of patentability.

The brief's own recommendations for how novelty will be implemented:

- **CDR-level comparisons**, not full-IgG comparisons, "since standardized framework and
  constant regions are expected."
- A **frozen reference database** fixed at the start of the challenge.
- Participants get an opportunity to clarify or contest a similarity finding before
  disqualification.

### What this does and does not permit

| Action | Status | Reasoning |
|---|---|---|
| Using a standard/validated **framework** (e.g. a humanized or germline Fv scaffold) with fully de novo CDRs | **Permitted** | Brief explicitly expects "standardized framework and constant regions" |
| Using human **IgG1/IgG4 constant regions** | **Required** | `CH Type` is a dropdown of exactly these |
| Targeting the **same epitope as dupilumab** or any known binder | **Permitted** | The rule restricts the *starting scaffold*, not the epitope. Nothing in the brief restricts epitope choice. |
| Using dupilumab / patent anti-IL-4Rα sequences for **benchmarking, controls, novelty comparison** | **Explicitly permitted** | "benchmarking, or design evaluation" |
| Taking an existing anti-IL-4Rα antibody and **mutating its CDRs** | **PROHIBITED** | Named prohibition |
| Submitting CDRs with high identity to a known antibody, even if independently generated | **Disqualification risk** | Novelty is assessed on the output, not on our intent. **We must screen our own CDRs before submitting.** |

→ **Actioned in `RANKING_AND_QC.md` §3**: every candidate is screened at CDR level against
a frozen reference set before it can enter the final 20.

---

## 6. Design considerations named by the brief

The brief lists these as useful when selecting final designs. They are not stated as hard
scoring criteria for Round 1, but they map directly onto Round 2 and onto our ranking:

- Predicted target recognition and binding interactions
- **Sequence diversity across submitted candidates**
- Structural plausibility of the antibody–target interaction
- Sequence liabilities that may affect expression or stability
- Potential self-association and nonspecific binding risks
- Overall developability characteristics

> Participants are encouraged to prioritize a **diverse set of promising designs rather
> than submitting highly similar sequences.**

→ Diversity is an explicit organiser preference, stated twice. It is a first-class
ranking objective, not a tiebreak.

---

## 7. Round 1 evaluation

| Assay | Description |
|---|---|
| **LSA – Single Concentration (1-con)** | Ranking multiple antibody affinity to human IL-4Rα under identical conditions |

Evaluation criteria:

- **Detectable binding signal** against human IL-4Rα
- **Relative binding response** compared with other participants' sequences

Round 1 outcome determines who advances to Round 2 developability. Final binding
thresholds and advancement criteria will be communicated by the organisers via
`proteinchallenge@genscript.com`.

→ **[IMPLICATION]** The bar is *detectable binding*, then relative ranking. This is a
shots-on-goal problem. 20 diverse credible designs beats 20 variations on one hypothesis.

→ **[ASSUMPTION, flagged]** The antigen used in the assay is ordered through Dr. G as
"Human IL-4 R alpha / CD124 Protein, **Fc Tag**, low endotoxin (MALS verified)". We assume
it is a mammalian-expressed, **glycosylated** Fc fusion of the ECD. Not stated in the
brief. Consequences for epitope choice are handled in `TARGET_PREP.md` §2. Do not
upgrade this from assumption to fact without confirmation.

---

## 8. Submission mechanics

Full operational detail in `SUBMISSION.md`. Spec-level facts only here.

- Submission is via GenScript's AI agent **"Dr. G"**, using a **challenge-specific
  GenScript account** issued by e-mail. Interactive chat; **not scriptable.**
- **No payment required.** Service credits are pre-applied; estimated total must read
  **0.00 USD**. If it does not, stop and do not proceed.
- A **batch Excel template** is downloaded from the Dr. G flow. Columns to fill:
  - `Antibody name`
  - `VH Seq`
  - `CH Type` — the dropdown offers **Human IgG1** or Human IgG4. **Use Human IgG1**: the
    live challenge hub specifies the design format as IgG1, and the brief's own opening
    prompt says "human IgG1 format"
  - `VL Seq`
  - `CL Type`
  - (`CH Seq` autofills from `CH Type` — do not hand-fill it)
- > "Please enter **ONLY** your protein sequences – we will automatically add a signal
  > peptide `MGWSCIILFLVATATGVHS` for you."
- Upload validation must report **20 records** and **"Validation successful, no error
  data"**. If any sequence fails, fix the Excel and re-upload. **Do NOT proceed to
  confirm the order with failed sequences.**
- Expected order preview: **Item Count 22** (20 sequences + assay service + antigen),
  challenge credit coupon applied, total **0.00 USD**.

Official submission checklist from the brief:

- [ ] Access to the GenScript Beyond Binding Challenge account confirmed working
- [ ] No more than 20 candidates
- [ ] All candidates target human IL-4Rα ECD
- [ ] Each candidate has a paired heavy- and light-chain sequence
- [ ] All sequences follow standard IgG construct requirements, complete and correctly formatted
- [ ] Submitted before the deadline

> Note: by submitting, you agree to the Beyond Binding Official Terms and Conditions.

---

## 9. Geodesic platform

- Platform: **Geodesic NovaDDE**, https://www.geodesiclab.com/
- Workbench intro: https://www.geodesiclab.com/news/novadde-ai-workbench
- Docs/help: https://agent.geodesiclab.com/help
- **Register the Geodesic account on the same e-mail used for challenge registration**,
  or access tokens will not be delivered correctly.

Participants "will have access to the Geodesic NovaDDE Platform to help develop their
sequences." Use of Geodesic is **encouraged, not mandatory** — the brief says
"Participants may use their preferred computational approaches **and** Geodesic design
workflows."

→ Credit model, budget and the VH/VL support question: `GEODESIC.md`.

---

## 9b. GenScript service credits — nothing to manage

> Please note that submission related to this Challenge does **NOT** require any fees or
> payment. **Service credits have been added to each Challenge account** that will negate
> the estimated proposal cost.

> A **Beyond Binding Challenge Credit coupon** should be automatically applied so your
> estimated total should be **0.00 USD**. Please do **NOT** continue if the estimated total
> states otherwise.

These are **not a budget you spend or allocate.** They are a coupon pre-loaded on the
challenge-specific GenScript account that auto-applies at checkout and zeroes the order.

What the coupon absorbs: 20 sequences @ **$152.50** each (**$3,050**), plus the **Carterra
LSA** assay service, plus the antigen (100µg of the Fc-tagged IL-4Rα) — Item Count **22**.

Operational consequences, and this is the whole of it:

1. **Log in with the challenge-specific account** from the official e-mail, not a personal
   or lab GenScript account. The coupon is attached to that account; any other login
   produces a real, non-zero bill.
2. **Verify the total reads `0.00 USD` before confirming.** That single check is the only
   credit-related action in the entire campaign.
3. **Do not deviate from the scoped order.** The coupon covers IgG / 20 sequences /
   Carterra LSA / that specific antigen at that specific size. More than 20 sequences, a
   different antigen (His-tagged instead of Fc-tagged), or a different assay may fall
   outside it and surface a non-zero total.
4. **There is nothing to conserve.** Submitting fewer than 20 saves nothing and carries
   nothing over. Submit the full 20.
5. If the total is **not** 0.00, **stop** and e-mail `proteinchallenge@genscript.com`.
   Do not proceed and do not pay.

Do not confuse these with Geodesic credits, which *are* a metered budget — see
`GEODESIC.md` §1.

---

## 10. Open items requiring a human

| Item | Owner | Status |
|---|---|---|
| GenScript challenge account credentials received and login tested | User | **VERIFY NOW** |
| Geodesic account registered on the challenge-registration e-mail | User | **VERIFY NOW** |
| Does NovaDDE support paired VH/VL, not just VHH? | User (behind login) | **BLOCKS gate G0** |
| Confirm `CL Type` options available in the template dropdown | User, at template download | Unknown until template is in hand |

If credentials are missing, e-mail `proteinchallenge@genscript.com` immediately —
turnaround is outside our control and the deadline is not negotiable.
