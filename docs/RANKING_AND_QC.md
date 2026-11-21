# RANKING_AND_QC.md — eligibility, liabilities, novelty, ranking

Four stages, in this order. **Hard gates first** — never rank a sequence that is
ineligible, and never let a good predicted score rescue a construct that will not express.

```
pool -> [1] eligibility gates (binary) -> [2] liability screen (penalty)
     -> [3] novelty screen (binary + margin) -> [4] rank -> [5] diversity-aware pick 20
```

---

## 1. CDR definition — needed by stages 2, 3 and 5

### Preferred: take CDRs from the design definition, not from numbering software

We **fix the framework and diffuse only the CDR loops**. The designed positions are
therefore known exactly, by construction, from the RFantibody HLT REMARK lines and the
diffusion mask. **This is more reliable than any numbering tool** and needs no install.

Emit, per design, an explicit record: `{chain, cdr_name, start_idx, end_idx, sequence}`
using 0-based indices into the submitted VH/VL string. Assert that slicing the submitted
sequence at those indices reproduces the recorded CDR string. If it does not, the design
is quarantined, not fixed by hand.

### Still needed: numbering for the *reference* antibodies

Novelty comparison needs CDRs of known antibodies too.

**Install path** (ANARCI is not on this box; it needs HMMER's `hmmscan`):

```bash
sudo apt-get update && sudo apt-get install -y hmmer   # passwordless sudo is available
~/miniforge3/bin/conda run -n boltz pip install anarci
~/miniforge3/bin/conda run -n boltz ANARCI --sequence EVQLVESGGG... --scheme imgt
```

Time box this to **20 minutes**. Do not install into `af2ig`. If it fails, fall back:

**No-install fallback.** Use `mafft` (present) to align each reference VH/VL to our own
framework, whose CDR boundaries we already know, and transfer the boundaries through the
alignment. Lower precision, entirely adequate for "is our CDR-H3 suspiciously close to a
known one", and it uses only tools already on the box.

---

## 2. Stage 1 — hard eligibility gates (binary, no exceptions)

Implement as `scripts/qc_liabilities.py`. A design failing **any** of these is removed
from the pool. It does not get a penalty; it is gone.

| Gate | Rule | Why |
|---|---|---|
| Alphabet | Only the 20 standard amino acids. No `X B Z J U O *`, no whitespace, no digits | Upload validator will reject it |
| Completeness | Both VH and VL present and non-empty | Required field |
| Length | VH **105–135**, VL **100–125** | Outside this is not a variable domain. Widen only with a logged reason |
| **No signal peptide** | Sequence must **not** begin with a signal-peptide-like hydrophobic leader, and must not start with `MGWSCIILFLVATATGVHS` | **GenScript prepends `MGWSCIILFLVATATGVHS` automatically.** A second leader kills the construct |
| **Cysteine parity** | **Exactly 2 Cys per variable domain** (the canonical intradomain disulfide). An **odd** Cys count is a hard fail | A free thiol causes misfolding, dimerisation and expression failure |
| CDR glycosylation | No `N-[^P]-[ST]` sequon inside any CDR | A glycan in the paratope blocks binding. Computationally invisible, experimentally fatal |
| Uniqueness | No duplicate (VH, VL) pair in the submission | Wastes a slot; "duplicate" is explicitly screened by GenScript |
| Provenance | Must trace to a recorded generator run with model, parameters and seed | Methodology may be requested by e-mail |

> Cysteine note: >2 Cys with **even** parity could be an intentional designed disulfide.
> It is still a flag, not an auto-pass — we have no capacity to validate a non-canonical
> disulfide experimentally in this timeframe. Default to rejecting it.

---

## 3. Stage 2 — developability liability screen (penalty score)

Round 2 is developability. Liabilities created now cannot be engineered out later.
Weight **CDR occurrences far more heavily than framework occurrences** — the framework is
a standard, well-behaved scaffold and its motifs are tolerated in approved therapeutics;
the CDRs are ours and are where the risk is.

| Liability | Motif / metric | Severity | Notes |
|---|---|---|---|
| **N-glycosylation** | `N-[^P]-[ST]` | **Critical in CDR** / high in framework | Heterogeneity, blocked paratope |
| **Deamidation** | `NG` ≫ `NS` > `NN`, `NT`, `NA`, `NH` | High (`NG` in CDR = critical) | Charge heterogeneity, potency loss on storage |
| **Asp isomerisation** | `DG` ≫ `DS`, `DD`, `DT`, `DH` | High (`DG` in CDR = critical) | Isoaspartate, potency loss |
| **Acid-labile cleavage** | `DP` | Medium–high | Fragmentation at low pH |
| **Oxidation** | `Met` anywhere; `Trp` in CDR | Medium (high if CDR) | Potency loss, forced-degradation failures |
| **Free thiol** | unpaired `Cys` | Critical | Already a hard gate |
| **CDR net charge** | sum of (K+R+H/2) − (D+E) across all CDRs ≥ **+2** | High | Strong literature link between positively charged CDRs and polyreactivity / fast clearance |
| **CDR hydrophobicity** | GRAVY over concatenated CDRs, high | Medium–high | Self-association, HIC retention, viscosity |
| **Theoretical pI** | outside **6.0–9.0** | Medium | Low pI → viscosity; high pI → polyreactivity, faster clearance |
| **CDR-H3 length** | > 20 residues | Medium | Expression and stability risk, more conformational entropy |
| **Low-complexity runs** | ≥ 4 identical consecutive residues | Medium | Aggregation and expression risk |
| **Basic patches** | `RR`, `KK`, `RK`, `KR` in CDR | Medium | Polyreactivity, heparin binding |

Report a per-design table with each hit, its position, whether it is in a CDR, and the
total weighted penalty. **Report, do not silently filter.** A design with one borderline
flag and outstanding structural evidence may still deserve a slot — but that must be a
visible, logged decision, not an accident.

This section is the complete spec for `scripts/qc_liabilities.py`. Write it **stdlib-only**
— there is no system biopython, so a stdlib implementation runs in any env or none. It needs
its own `--self-test` on synthetic sequences covering each hard gate, run before it ever
touches real designs.

The pI estimate can be a plain Henderson–Hasselbalch bisection on net charge; note in the
code that treating Cys as titratable slightly underestimates pI for a domain with an intact
disulfide, which is acceptable for a comparative screen and must not be reported as an
analytical measurement.

---

## 4. Stage 3 — novelty screen

The rule, restated from `CHALLENGE_SPEC.md` §5: de novo, **no existing IL-4Rα binder as a
starting scaffold**, novelty judged at **CDR level**, standardised framework and constant
regions **expected**. GenScript will run their own similarity assessment.

We satisfy this by construction — RFantibody and NovaDDE generate CDRs de novo and we
never load a known binder as a scaffold. **But novelty is assessed on the output, not on
our intent**, so we screen our own output before submitting.

### Frozen reference set

Build it once, early, and freeze it. Record a file list, per-file SHA256 and the date, and
never update it mid-campaign — the brief itself recommends a frozen reference database.

| Tier | Content | Priority |
|---|---|---|
| **1 — mandatory** | Every anti-IL-4Rα antibody sequence we can find: dupilumab, antibodies disclosed in IL-4Rα patents, any antibody in a PDB complex with IL-4Rα | **This is the tier the rule is actually about.** Must be complete |
| **2 — strongly desired** | Therapeutic / clinical-stage antibody CDRs (Thera-SAbDab or equivalent) | Covers "sufficient diversity from known antibodies" |
| **3 — if reachable** | Broad structural antibody CDR set (SAbDab). **Verify host reachability from the VM before planning on it** — RCSB, PyPI and GitHub are confirmed, academic hosts are not | Nice to have |

Use `blastp` / `makeblastdb` (both present in `/usr/bin`) over the reference set.

### Checks and thresholds

| Check | Threshold | Action |
|---|---|---|
| Exact CDR-H3 match to any reference | any | **Hard fail** |
| CDR-H3 identity to nearest reference | **> 70%** | **Hard fail** |
| Concatenated-CDR identity to nearest reference | **> 60%** | Flag, manual review |
| Full VH or VL identity to any **anti-IL-4Rα** antibody | **> 85%** | **Hard fail** — looks like scaffold derivation regardless of how it was made |
| Full VH/VL identity to a non-IL-4Rα antibody | high is **expected and fine** | No action. This is the standardised framework |

> **These thresholds are ours, not GenScript's.** The brief publishes no numeric
> threshold. Label them `[ASSUMPTION]` in the manifest and in any methodology we send.
> They are deliberately conservative: the cost of a false flag is dropping one design; the
> cost of a miss is disqualification.

Record, per design, the nearest reference hit and its identity — including for designs
that pass. The brief says participants get a chance to **contest** a similarity finding;
having our own pre-computed table is how we win that conversation in January.

---

## 5. Stage 4 — ranking

### Rule: never compare scores across model families on one scale

RF2 interface scores, Boltz-2 ipTM and NovaAtom ipTM are **not** on a common scale.
Rank-normalise (or z-score) **within each family**, then combine ranks. Do not average
raw values from different models.

### Evidence, in descending weight

1. **Cross-family agreement.** A design that ranks well under RF2 **and** Boltz-2
   **and** (if available) NovaAtom is the strongest signal we can produce. Agreement
   across independent model families is worth more than a high score from any one.
2. **(H+L) vs T interface quality** — the designed-chain-pair-versus-target interface.
   **Never global ipTM**, which on an Fv is dominated by the ~0.9 H↔L interface and is
   meaningless as a binding signal. Assert the chain selection in code.
3. **Multi-sample stability.** Any margin or differential metric must be a **5-sample
   average**. Between-seed Spearman ρ was **+0.239 at 1 sample** vs **+0.846 at 5** in a
   prior campaign — single-sample values are noise, and 5 samples cost only 2.41×.
   Report the between-sample spread; a design whose score swings wildly is a weak design
   even if its mean is good.
4. **Self-consistency / refold RMSD.** Does the sequence refold to the designed backbone?
5. **Interface geometry** — buried surface area, contact count, shape complementarity,
   no clashes, few unsatisfied buried polars, epitope residues actually contacted.
6. **Liability penalty** from §3, inverted.
7. **Novelty margin** from §4 — distance from the nearest known antibody, as a mild
   positive, not a primary driver.

### Not evidence

- **Composition.** Hits had better composition than non-hits in a prior campaign
  (0.372 vs 0.341 hydrophobic at n=7,200), but *intervening* on composition moved
  composition a lot and the hit rate not at all (z = +0.76). **Select on it; do not
  engineer it.** Use it as a weak tiebreak only.
- Any rate computed from **n < 100**. Small-sample conclusions reversed three separate
  times in comp5 (3.1% at n=32 became 0.7% at n=272).

---

## 6. Stage 5 — diversity-aware selection of the 20

Ranking alone will hand you 20 near-identical designs from the single best backbone
family. That is the wrong answer both scientifically and per the brief, which says twice
to prefer a diverse set.

**Algorithm:**

1. Cluster eligible designs by **CDR-H3 identity** (single-linkage, cut at **70%**).
   Secondary clustering on concatenated-CDR identity.
2. Honour the epitope-arm targets from `TARGET_PREP.md` §6 (~12 E1 / ~5 E2 / ~3 E3). An
   arm that produced nothing credible **forfeits** its slots to arms that did — targets,
   not quotas.
3. Greedy fill: take the top-ranked design from the strongest cluster in each arm, then
   iterate, **never taking a second design from a cluster until every cluster in that arm
   has one**.
4. Cap any single CDR-H3 cluster at **3 of 20**.
5. Spread across **frameworks** (hu-4D5-8 vs germline) and across **generators**
   (RFantibody vs NovaDDE) where both produced credible designs. Record the realised
   split.
6. If slots remain unfilled, relax in this documented order, logging each step:
   cluster cap → arm targets → the weakest liability flags. **Never relax a hard
   eligibility gate or a novelty hard fail.**

Also record the **rejected** candidates and why. That is a required deliverable and it is
what makes the methodology defensible.

---

## 7. Manifest schema

One row per candidate, every candidate ever generated — not just the 20.
`candidates.tsv`, append-only, written to the repo (small) with bulk artefacts on scratch.

```
candidate_id            epitope_arm           framework
generator               generator_version     parameters_json
random_seed             run_id                vh_seq
vl_seq                  ch_type               cl_type
vh_len                  vl_len                cdr_definitions_json
rf2_iface_hl_vs_t       rf2_rank              boltz2_iface_mean5
boltz2_iface_sd5        boltz2_rank           novaatom_iptm
novaatom_refold_rmsd    cross_family_agree    bsa_a2
contact_count           epitope_contact_frac  liability_penalty
liability_hits_json     cys_count_vh          cys_count_vl
cdr_net_charge          cdr_gravy             theoretical_pi
cdrh3_len               nearest_ref_id        nearest_ref_cdrh3_identity
nearest_il4ra_identity  novelty_status        eligibility_status
cluster_id              rank_final            selected
rejection_reason        artifact_paths        notes
```

**Rules for this file:**

- A metric that was not computed is **`not_run`**. Never a zero, never a guess, never an
  estimate. Prior campaigns wrote `not_run` into four columns honestly rather than
  estimating, and that is precisely why their results could be trusted.
- Every value is `measured` (ran it), `predicted` (a model said so), or `not_run`. A
  predicted score is **never** described as binding.
- Match on **full** candidate IDs, longest first, and assert the join is non-empty. A
  prefix match on design IDs silently blanked an entire comparison in a prior campaign.
