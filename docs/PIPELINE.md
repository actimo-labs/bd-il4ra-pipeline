# PIPELINE.md — 66-hour sprint plan

Deadline: **Tue 24 Nov 2026, 15:59 AEDT** (Mon 23 Nov 23:59 ET).
Plan written at **Sat 21 Nov ~22:00 AEDT**, i.e. **T−66h**.

This document is the schedule and the abort logic. `TARGET_PREP.md`,
`SETUP_RFANTIBODY.md`, `GEODESIC.md` and `RANKING_AND_QC.md` are the stage detail.

---

## 1. Shape of the plan

Two independent generators feeding one shared evaluation and selection funnel:

```
                                    ┌──────────────────────────┐
  target prep ──> epitopes E1/E2/E3 │                          │
  (TARGET_PREP.md)                  v                          v
                        ┌─ A: RFantibody on the A100 ─┐  ┌─ B: Geodesic NovaDDE ─┐
                        │ RFdiffusion_Ab  CDR backbone│  │ CDR design on framework│
                        │ ProteinMPNN     CDR sequence│  │ NovaAtom fold          │
                        │ RF2_ab          filter      │  │ ipTM / refold RMSD     │
                        └──────────────┬──────────────┘  └───────────┬────────────┘
                                       └───────────┬─────────────────┘
                                                   v
                              Boltz-2 orthogonal co-fold (H+L vs T)
                                                   v
                              QC: eligibility gates + liability screen
                                                   v
                              Novelty: CDR-level vs frozen reference set
                                                   v
                              Rank + diversity-aware selection of 20
                                                   v
                              submission builder -> official Excel -> Dr. G
```

Two generators is not gold-plating. **Neither is proven on this box**, RFantibody has
never been installed here, and Geodesic's paired-VH/VL support is unconfirmed. A single
point of failure inside 66 hours is unacceptable.

---

## 2. Gates and wall clock

Each gate has an **abort/decide** action. Do not slide a gate; cut scope instead.

| Gate | By (AEDT) | T− | Must be true | If not |
|---|---|---|---|---|
| **G0** Access & viability | Sun 02:00 | 62h | GenScript login tested. Geodesic credits visible. **Paired VH/VL confirmed supported or not.** Scratch dir created. | Email `proteinchallenge@genscript.com`. Proceed with whichever generator is live. **If Geodesic is VHH-only, Arm B is dead — say so in RUNLOG and go RFantibody-only.** |
| **G1** Target + install | Sun 08:00 | 56h | Target prepped, E1 frozen, HLT inputs built. RFantibody installed and a **2-design end-to-end pilot** has produced an RF2 scorefile. | **Hard abort on RFantibody.** Do not keep debugging past this gate. Fall to Arm B / fallback ladder §5. |
| **G2** Sized & launched | Sun 20:00 | 44h | Pilot metrics reviewed. Measured s/design recorded. Production run sized against remaining GPU hours and **launched in tmux**. E2/E3 frozen. Framework arms decided. | Reduce to E1 + one framework. Launch something. |
| **G3** Pool exists | Mon 10:00 | 30h | ≥100 candidates through generation with filter metrics. Boltz-2 cross-check running. | Submit from whatever passed. Stop generating, start selecting. |
| **G4** **DESIGN FREEZE** | Mon 16:00 | 24h | **No new generation after this point.** QC, novelty and ranking run on the frozen pool. | Non-negotiable. |
| **G5** **SELECTION FREEZE** | Tue 04:00 | 12h | The 20 are locked. Excel built, self-validated, manifest complete. | Non-negotiable. |
| **SUBMIT** | Tue 10:00 | 6h | Dr. G flow complete, order confirmed, 0.00 USD, Order No. recorded. | — |

The 6-hour tail on submission is deliberate. Dr. G is an interactive agent with its own
upload validator that can reject the file and make you fix and re-upload. **Do not
discover that at T−1h.**

---

## 3. Compute budget

Measured rates on this A100 from the prior campaign (`VM_INVENTORY.md` §7) are for
**single-chain minibinders** and **do not transfer** to an Fv + target system, which is
2–3× larger. They are useful only as an order-of-magnitude floor:

| Prior-campaign stage | Measured | Relevance here |
|---|---|---|
| RFdiffusion, 65–85 aa binder + cropped target | 62–65 s/backbone | **Floor.** Fv (~230 aa) + crop will be materially slower |
| ProteinMPNN | effectively free vs GPU budget | Transfers. Near-deterministic at `sampling_temp 0.1`; 2 draws/pool already saturates |
| Boltz-2, 1 diffusion sample | 16.5 s/prediction | Transfers approximately |
| Boltz-2, 5 diffusion samples | 39.7 s/prediction | **2.41× cost for 5× samples** — trunk is shared, so multi-sample averaging is cheap |

**Measure, then size. Do not guess.** At G2, fill this table from the pilot and commit
the numbers to `RUNLOG.md`:

```
RFdiffusion_Ab   : ____ s/design   (Fv + E1 crop, N designs measured = ____)
ProteinMPNN      : ____ s/backbone (____ seqs per backbone)
RF2_ab           : ____ s/design
Boltz-2 (5 samp) : ____ s/complex
```

Then: `n_backbones = available_GPU_hours * 3600 / (t_rfdiff + n_seqs*t_mpnn + n_seqs*t_rf2)`

Realistic available GPU time across the sprint is **~20–28 h**, not 66 — target prep,
install, QC, selection and sleep consume the rest. Size for 24 h and leave headroom.

### Two budget rules carried from prior campaigns

1. **Multi-sample averaging is mandatory for any margin/differential metric.**
   Between-seed Spearman ρ was **+0.239 at 1 diffusion sample** and **+0.846 at 5**.
   Single-sample scores are noise. At 2.41× cost for 5× samples this is affordable —
   use 5 samples for anything that feeds ranking.
2. **More sequence draws on a backbone that already works beats more geometry.** The
   single most effective intervention across all prior campaigns: deep resampling of
   proven backbones gave ~27× the hit rate at a fifth of the GPU cost. **Reserve GPU time
   for a deep-resample round** on whichever CDR backbones survive the first filter pass.
   Schedule it between G2 and G3.

---

## 4. Stages

### S1 — Target preparation → `TARGET_PREP.md`
Owner: local. Blocking for both arms. Deliver E1 before G1; E2/E3 before G2.

### S2A — RFantibody generation → `SETUP_RFANTIBODY.md`
1. `RFdiffusion_Ab` designs CDR backbones against the HLT target, framework fixed.
   **Disable trajectory output** (a prior campaign leaked ~6 GB unnoticed).
2. `ProteinMPNN` interface design over the CDR positions only; framework held fixed.
3. `RF2_ab` predicts and filters.

**Chain-pair trap:** the system has three chains (H, L, T). **Global ipTM is meaningless
for an Fv** because the H↔L interface scores ~0.9 whether or not the antibody binds the
antigen. Compute and filter on **(H+L) vs T** interface metrics only, and assert the chain
selection in code.

### S2B — Geodesic generation → `GEODESIC.md`
Framework-templated de novo CDR1-3 design, NovaAtom folding, platform ipTM/refold RMSD,
OASis humanness. Credit-metered — check the quoted cost before every submit.

### S3 — Orthogonal co-folding
Boltz-2, `msa: empty` single-sequence mode (the MSA server at `10.148.0.19:8080` is dead
and the host is gone — do not try to revive it; all prior campaigns ran empty-MSA).
5 diffusion samples, averaged. This is a **second opinion**, deliberately a different
model family from both generators' own scorers. Agreement across model families is the
strongest computational evidence available to us; disagreement is informative and should
be recorded, not hidden.

### S4 — QC, novelty, ranking → `RANKING_AND_QC.md`
Hard eligibility gates first, then documented ranking, then diversity-aware selection.

### S5 — Submission → `SUBMISSION.md`
Human-in-the-loop. The user drives Dr. G. Claude prepares and validates the file.

---

## 5. Fallback ladder

Evaluate at every gate. Record which rung you are on in `RUNLOG.md`.

| Rung | Trigger | Plan |
|---|---|---|
| **F0** | Both arms live | Split slots across arms **and** epitopes. Best case. |
| **F1** | RFantibody not working by **G1** | Geodesic-only. Spend credits on breadth across E1/E2/E3 and two frameworks. Top up credits with money (§GEODESIC) rather than cutting designs. |
| **F2** | Geodesic VHH-only, or credits exhausted and top-up blocked | RFantibody-only. Reallocate all 20 slots across E1/E2/E3. |
| **F3** | Both dead by **Mon 02:00 (T−38h)** | Home-roll: fixed germline Fv framework, CDR loop sequences sampled with the installed ProteinMPNN against Boltz-2-co-folded Fv–antigen models, Boltz-2 as both scorer and filter. **Expected yield is poor and must be labelled as such** in the manifest and any methodology we send GenScript. It still produces 20 valid, novel, submittable paired sequences. |
| **F4** | Catastrophic | Submit the best 20 that exist, however weak, with honest documentation. **A submitted weak set beats an unsubmitted good one** — it yields experimental data, and any detectable binder keeps Round 2 alive. |

**Always keep a "last known good" pool of ≥20 QC-passing, eligible sequences
checkpointed on disk from G3 onward.** At any moment after G3 it must be possible to
submit within 30 minutes. Re-generate that file whenever the pool changes.

**Noted but out of scope:** BoltzGen (the generative model Geodesic's public example
uses) could in principle be a third local generator. **Do not attempt a third unverified
install during this sprint.** Record it as a post-mortem item.

---

## 6. Honest expectations

Published de novo antibody design work reports **single-digit percent** binder hit rates
by SPR, and **paired Fv is harder than VHH**. We have 20 slots, one shot, no affinity
maturation, and a heavily glycosylated target.

A realistic good outcome for Round 1 is **1–3 designs with detectable LSA signal**.

That shapes strategy, and the strategy follows from it:

- **Diversity beats depth.** Three independent epitopes × two frameworks × two generators
  is the correct use of 20 slots. Twenty variations on one hypothesis is a single bet.
- Do not let ranking collapse the submission onto one backbone family. Diversity is an
  explicit organiser preference, stated twice in the brief, and it is also the
  statistically correct play.
- Do not report a predicted score as evidence of binding, to the user or to GenScript.
