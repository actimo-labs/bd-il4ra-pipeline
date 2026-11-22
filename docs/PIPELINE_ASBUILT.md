# PIPELINE_ASBUILT.md — the end-to-end pipeline, as actually built and run

Status at 2026-11-22 06:40 UTC, T-46.3h. Gates G1 and G2 **passed**, G3 in progress.
This describes what **exists and has run**, not a plan. Every number is measured.

`docs/PIPELINE.md` is the original sprint plan. This file is the realised version,
including the places where reality diverged from it.

---

## Overview

```
 [1] target prep ──┐
 [2] epitopes      ├──> [4] crops + framework ──> [5] RFdiffusion_Ab ──> [6] ProteinMPNN
 [3] glycan mask ──┘                                   (backbones)          (CDR seqs)
                                                                                │
                           ┌────────────────────────────────────────────────────┘
                           v
                    [7] sequon prefilter ──> [8] RF2_ab ──> [9] interface scoring
                        (CPU, pre-GPU)          (filter)       ((H+L) vs T)
                                                                     │
         ┌───────────────────────────────────────────────────────────┘
         v
 [10] deep resample ──(loop back to 6)      [11] harvest -> candidates.tsv
                                                   │
         ┌─────────────────────────────────────────┤
         v                                         v
 [12] QC + liabilities                      [13] novelty screen
      (8 hard gates)                        (1076 frozen refs)
         └─────────────────┬───────────────────────┘
                           v
                [14] Boltz-2 orthogonal co-fold
                           v
                [15] rank within family, combine ranks
                           v
                [16] CDR-H3 cluster + diversity-aware pick of 20
                           v
                [17] submission builder + 406-check pre-flight
                           v
                [18] Dr. G  ← HUMAN IN THE LOOP, the user drives this
```

---

## Stage by stage

### [1] Target preparation — `scripts/01_target_prep.py` (13/13 self-test)

**In:** `1IAR.pdb`, `3BPN.pdb` from RCSB. **Out:** `il4ra_ecd.pdb`, `numbering_map.json`.

- Numbering map **derived** from `SEQADV`, not assumed: `uniprot = pdb + 25`, and the
  derivation **refuses to run** unless the records imply a single consistent offset.
  Cross-checked independently in both structures.
- Asserts: SEQRES chain B is exactly 207 == ECD length; pdb 1..207 maps to uniprot
  26..232 == the brief's AA26-232; **all 188 observed residues match SEQRES at their
  index** (the off-by-one detector).
- In-house Shrake–Rupley SASA (numpy, 256-point golden spiral). Written because the
  biopython wrapper mis-handled residue numbers duplicated across chains — which an
  Fv+target complex *always* has — and produced a **negative** buried surface area.
  Validated against biopython on a clean single chain: r = 0.998, ratio 0.9975.

### [2] Glycan mask — same script

All six sequons (N53, N98, N128, N134, N176, N209) verified as real `N-X-[ST]`, X≠P.
Mask = any residue whose Cβ is within **10.0 Å** of a sequon Asn Cβ.

**Relaxed from the 12.0 Å default**, which the spec permits only if no viable epitope
survives — and none did: at 12 Å the best Fv-sized sub-site in E1 had **2 hydrophobic
residues / 302 Å²** against documented minimums of >3 and ≥600 Å². At 10 Å several reach
4 / 666 Å². Both runs preserved in `target/radius_study/`.

### [3] Epitope definition — `scripts/02_epitopes.py` (14/14)

- **E1** computed, not hardcoded: 1IAR chain B residues within 5.0 Å heavy-atom of IL-4
  (chain A), minus both masks.
- **E2/E3** from scoring every surface patch after masking — 73 scored, 43 passed hard
  gates, **full table including every rejected patch and its reason** in
  `patch_scoring.tsv`. Weights are `[ASSUMPTION]` ours.
- Hotspots: `0.40·exposure + 0.35·centrality + 0.25·hydrophobic`, with a **hard 30 Å²
  exposure floor applied before ranking** — added after the first run selected a buried
  core residue (Y38, SASA 7.6 Å²) as a hotspot.

### [4] Crops + framework — `scripts/03_crop_hlt.py` (8/8)

Target format verified against the shipped `rsv_site3.pdb` rather than assumed: chain
**T**, **no REMARK lines**, **original numbering preserved**. `verify_target()` re-parses
each file it writes and asserts chain ID, hotspot presence, and **per-residue amino-acid
identity** against SEQRES.

| | crop | segments | hotspot string |
|---|---|---|---|
| E1 | 87 res | 7 | `T67,T69,T125,T127` |
| E2 | 82 res | 3 | `T36,T79,T84,T85` |
| E3 | 59 res | 5 | `T115,T160,T162,T163` |

Framework: `hu4D5-8_Fv_HLT.pdb`, H=116 L=107, all six CDR REMARKs verified.

### [5] RFdiffusion_Ab — `scripts/11_run_production.sh`

`--no-trajectory` always (a prior campaign leaked ~6 GB). Checkpoint passed explicitly
so the IPD-internal fallback paths in `model_runners.py` can never fire. Loops
`H1:7,H2:6,H3:5-13,L1:8-13,L2:7,L3:9-11`.

**Round-robin across E1/E2/E3 in batches of 10** so a kill at any point leaves all arms
proportionally covered. Resumable: a batch with a non-empty `3_rf2/` is skipped.
Disk-guarded: aborts below 10 GB on root.

**Measured 80.7 s/backbone** (marginal, batch 10).

### [6] ProteinMPNN — interface mode, framework fixed

Designs exactly the 49 CDR positions and nothing else — verified by sequence: the output
is the hu4D5-8 framework *verbatim* with poly-G only at CDR positions.
**Measured 1.50 s/sequence.**

### [7] Sequon prefilter — `scripts/07_prefilter.py` (10/10)  ← **not in the original plan**

Added after the pilot showed 3 of 4 designs failing the hard `no_cdr_glycosylation` gate.
MPNN has no sequon awareness; it turned the framework's own `GFNIKDT` into `GFNITDT`.

Screens MPNN output on **sequence alone** (CDR sequons, Cys parity, alphabet, length)
**before** spending RF2 on it — 1.5 s/seq versus 24 s/design. **Raw MPNN output is never
modified**; clean designs are copied to a separate directory.

Measured over 704 resample draws: **28% clean, and strongly bimodal — 34% of backbones
produced a sequon in every one of 16 draws.** Sequon-proneness is a property of the
backbone, not sampling luck.

### [8] RF2_ab — the filter

10 recycles. **Writes no scorefile** — 13 metrics are embedded as `SCORE` lines in each
output PDB. Anyone looking for a `.sc` will wrongly conclude the stage failed.

**`interaction_pae` is the (H+L) vs T metric, verified by code reading**, not assumed:
`pose_util.py` builds `same_chain` with only two blocks (target | whole antibody) in
internal order T,H,L, so `~same_chain` is exactly the T↔(H+L) off-diagonal and contains
**zero H↔L cells** (verified numerically: 38,802 cells = 2·Lt·(Lh+Ll)).

**Measured 24.1 s/design.**

### [9] Interface scoring — `scripts/04_interface.py` (25/25)

Everything on **(H+L) vs T**. The chain set is **hard-asserted** to be exactly {H,L,T};
a missing light chain is refused in strict mode because it would silently turn an Fv
score into a VHH score.

- H↔L is reported **only** as `H_vs_L_NEGATIVE_CONTROL`. The self-test asserts it is
  numerically identical between a bound and an unbound complex while (H+L) vs T differs.
- `build_target_map()` maps RFdiffusion's **renumbered output** (H 1–119, L 120–225,
  **T 226–312**) back to crop numbering (9–188) and asserts per-residue identity. Without
  this every epitope metric silently reads zero.
- `masked_contact_frac`: fraction of the interface on glycan-masked surface. Added after
  discovering the mask filtered epitope *selection* but masked residues remain in the
  crop (33–43% of each), so designs drift onto presumed glycan.
- Verdict ladder: `UNDOCKED / WEAK / DOCKED ON MASKED SURFACE / DOCKED ON HOTSPOTS /
  DOCKED ON EPITOPE (off-hotspot) / DOCKED OFF-EPITOPE`.

### [10] Deep resample — `scripts/12_deep_resample.sh` + `select_backbones.py`

Backbones with **any** round-1 sequence at `interaction_pae < 10` get 16 fresh MPNN draws
at temp 0.25, prefiltered, then RF2. Judged by **best** sequence, not mean — we are
resampling geometry, and one good sequence proves the geometry can carry one.

**Result: 44 backbones → 200 designs, 1.68 GPU-h, and `pae<10` rate of 26% versus round
1's 11%.** 45 of the 58 final survivors came from here.

### [11] Harvest — `scripts/06_harvest.py` (15/15)

Walks raw output into `candidates.tsv`, **55 columns, one row per candidate ever
generated**. CDRs come from the HLT REMARK lines (known by construction) and slicing the
submitted sequence at the recorded indices must reproduce the CDR string or the design is
**quarantined**. Uncomputed metrics are literally `not_run`, asserted in the self-test.

### [12] QC + liabilities — `scripts/qc_liabilities.py` (29/29, stdlib only)

**8 hard binary gates** — alphabet, completeness, VH/VL length, no signal peptide
(GenScript prepends `MGWSCIILFLVATATGVHS`), Cys parity, no CDR sequon, uniqueness,
provenance. Then a **penalty score** over the full motif table, with framework hits
down-weighted to 0.15×. Reports, does not filter.

The known-good hu4D5-8 Fv passes every gate, and every gate has a targeted mutant that
must fail it — so the screen cannot be silently vacuous.

### [13] Novelty — `scripts/05_novelty.py` (26/26)

**1076 frozen references**: 4 anti-IL-4Rα structures found by querying RCSB for UniProt
P24394 (6WGL dupilumab, 6OEL, 8K4Q, 8Z8L) + **1072 clinical-stage therapeutics** from
Thera-SAbDab. Frozen with per-file SHA256 and date. Comparison only — no sequence is ever
used as a scaffold.

Two corrections were required here:

1. The spec's ">0.85 full identity to an anti-IL-4Rα antibody = hard fail" **fails 100%
   of our designs**: bare hu4D5-8 VL is 0.860 identical to 6OEL's VL, both IGKV1-39
   frameworks. Now hard-fails only when accompanied by CDR-concat identity > 0.60.
   `[MODIFIED GATE]`.
2. `identity()` divided by the **shorter** sequence, so a 2-residue reference CDR-H3
   scored **1.0** against our 10-residue loop and was hard-failing 5 of 20 novel designs.
   Now divides by the longer sequence for CDR comparison.

### [14] Boltz-2 orthogonal co-fold — `scripts/09_boltz_crosscheck.py` (11/11)

`msa: empty` (the MSA server is dead), 5 diffusion samples, mean **and sd** both recorded.
Reads `pair_chains_iptm` and **raises rather than falling back to global ipTM**; the
global value is stored under the key `global_iptm_DO_NOT_RANK_ON_THIS`.

On a real design: (H+L) vs T = 0.531, **H↔L = 0.969 with sd 0.001** — the uninformative
number is the stable one. **Measured 120.6 s/complex.**

### [15–16] Rank and select — `scripts/08_rank_select.py` (32/32)

Hard filter first, then **rank-normalise within each model family and combine ranks** —
never average raw scores across families. `not_run` is never treated as 0.

Hard gates: eligibility, novelty, `interaction_pae < 10`, `framework_aligned_cdr_rmsd ≤ 2`,
BSA ≥ 400 Å², `masked_contact_frac ≤ 0.40`.

Selection: CDR-H3 single-linkage clusters at 70%, one per cluster per arm first, cap 3
per cluster, arms with nothing eligible forfeit their slots, then a documented relaxation
ladder that **never** touches a hard gate or a novelty hard fail.

### [17] Submission builder — `scripts/build_submission.py` (19/19)

Five columns: `Antibody name | VH Seq | CH Type | VL Seq | CL Type`. Variable domains
only. **Refuses to write on any validation error and exits non-zero** — no "with
warnings" path. Detects constant-domain motifs (`ASTKGPSVFPLAP`, `RTVAAPSVFIFPPS`) and a
length ceiling, because VH+CH1 in the VH field is silent and fatal.

### [18] Dr. G — **human in the loop. The user drives this. Claude never submits.**

---

## Realised results

```
round 1        230 backbones -> 460 designs      8.13 GPU-h
deep resample   44 backbones -> 200 designs      1.68 GPU-h
                                 ---
pool                              660 designs    9.81 GPU-h
hard-filter survivors              58
CDR-H3 clusters                    36
SELECTED                           20   (E1 12, E2 5, E3 3; 19 distinct clusters)
submission pre-flight             406/406 checks passed
```

**45 of 58 survivors came from the resample round** — 78% of the usable pool from 30% of
the designs.

---

## Where reality diverged from `PIPELINE.md`

| Planned | Actual |
|---|---|
| Two frameworks (hu4D5-8 + germline) | **One.** RFantibody ships one submittable Fv framework; the other is a nanobody. Germline HLT needs Chothia numbering we cannot obtain. |
| Geodesic Arm B | **Not started.** Gate G0 unresolved, zero credits spent. |
| E2/E3 better targets than E1 | **Wrong.** E1 engages hotspots best (2.25/4 vs E2's 0.25/4) despite the weakest static patch score. |
| `RMSD(design vs predicted) < 2 Å` | **Unusable as `target_aligned`** — 0/55 pass, min 2.49 Å. Using `framework_aligned_cdr_rmsd ≤ 2` instead. `[ASSUMPTION]` |
| No sequon prefilter | **Added.** 60% of all rejections were CDR sequons. |
| No masked-contact gate | **Added.** The glycan mask never reached the crop. |

---

## Known weaknesses in the current 20

1. **RF2 is single-sample.** We rank primarily on one `interaction_pae` per design, while
   `PIPELINE.md` §3 rule 1 says margin metrics need multi-sample averaging. Boltz-2 is
   5-sample; RF2 is not.
2. **Cross-family disagreement on 8 of 20.** RF2 and Boltz-2 rank these differently.
3. **8 of 20 have CDR-H3 ≤ 7 residues** (median 9). Legal under `H3:5-13` but short for a
   real paratope.
4. **E2 is the weak arm** — Boltz 0.205–0.711, masked fractions 0.24–0.37, 0–2 of 4
   hotspots. It holds 5 slots on an arm-target quota, not on merit.
5. **E3 is nearly exhausted** — only 4 survivors for 3 slots, so no selection margin.
6. **Boltz-2 sd is high** — median 0.110, max 0.262 across 5 samples.
