# bd-il4r--pipeline

De novo IgG antibody design against **human IL-4Rα ECD** for the
**GenScript LSRG × Geodesic "Beyond Binding" Challenge, Round 1**.

> **Deadline: Tue 24 Nov 2026, 15:59 AEDT** (Mon 23 Nov 23:59 ET).
> This is a ~66-hour sprint. Read `CLAUDE.md` before doing anything.

## Orientation

| Read this | For |
|---|---|
| **`KICKOFF_PROMPT.md`** | **Paste this into a fresh Claude Code session to start.** Re-paste every session |
| **`CLAUDE.md`** | Operating contract, hard constraints, environment, guardrails |
| `docs/CHALLENGE_SPEC.md` | Verified official rules + sources. **Ground truth.** |
| `docs/PIPELINE.md` | Sprint schedule, gates G0–G5, compute budget, fallback ladder |
| `docs/TARGET_PREP.md` | IL-4Rα prep, glycan masking, epitope allocation |
| `docs/SETUP_RFANTIBODY.md` | Install runbook — the critical path |
| `docs/GEODESIC.md` | Credit model, budget, the paired-VH/VL gate |
| `docs/RANKING_AND_QC.md` | Eligibility gates, liabilities, novelty, ranking |
| `docs/SUBMISSION.md` | Dr. G procedure, Excel spec, pre-flight checklist |
| `RUNLOG.md` | **Append-only.** Every session writes here |

## Quick start

```bash
# hours left
python3 -c "import datetime as d;x=d.datetime(2026,11,24,4,59)-d.datetime.utcnow();print(f'T-{x.total_seconds()/3600:.1f}h')"
tail -40 RUNLOG.md                # what was the last session doing?
cat config/sprint.yaml            # current gate state + budgets
```

Then paste `KICKOFF_PROMPT.md` into Claude Code. Session preflight is in `CLAUDE.md` §8.

## The pipeline in one picture

```
IL-4Rα ECD ──> epitopes E1/E2/E3 ──┬─> RFantibody (local A100)  ──┐
   (1IAR)       glycan-masked      └─> Geodesic NovaDDE          ──┤
                                                                   v
                      Boltz-2 orthogonal co-fold (H+L vs T, 5 samples)
                                                                   v
                      QC ──> novelty ──> rank ──> diversity-pick 20 ──> Dr. G
```

Two independent generators because neither is proven on this box and there is no time to
recover from a single point of failure.

## Two currencies, and only one of them needs managing

| Currency | What it is | What you do |
|---|---|---|
| **GenScript service credits** | A coupon pre-loaded on the challenge GenScript account. Absorbs 20 × $152.50 + Carterra LSA + the antigen | **Nothing.** Log in with the challenge account and verify the order total reads `0.00 USD`. `CHALLENGE_SPEC.md` §9b |
| **Geodesic credits** | ~1,000 = the Plus tier *weekly* allowance. Doesn't roll over. Failed runs still charged. Top-up ≈ $10/1,000 | **Budget actively.** `GEODESIC.md` |

Claude Code tokens are a third thing entirely and buy zero protein compute.

## Three things that will silently ruin this

1. **Global ipTM on an Fv is meaningless.** The H↔L interface scores ~0.9 whether or not
   the antibody binds the antigen. Score **(H+L) vs T** only.
2. **All six IL-4Rα N-glycosylation sequons are inside the ECD.** An epitope overlapping an
   occupied glycan gives a perfect model and zero assay signal.
3. **GenScript prepends the signal peptide `MGWSCIILFLVATATGVHS`.** Including your own
   kills the construct.

## Tooling status on this VM

| Tool | Status |
|---|---|
| Boltz-2, ProteinMPNN, RFdiffusion (base), PyMOL, blastp, mafft | installed |
| **RFantibody** (`RFdiffusion_Ab`, `RF2_ab`) | **NOT installed — gate G1** |
| **ANARCI** / antibody numbering | **NOT installed** — fallback in `RANKING_AND_QC.md` §1 |
| PyRosetta, PRODIGY, ThermoMPNN, FoldX, APBS | not installed, no licence. Energetics columns are `not_run` |

The prior campaigns' AF2 initial-guess filter **does not transfer** — it assumes a
single-chain binder. `RF2_ab` is the antibody filter.

## Code

**No Python ships with this repo — the agent writes it from the specs.** `CLAUDE.md` §10
maps every module to the doc that specifies it: target prep, glycan masking, epitope
scoring, HLT conversion, interface scoring, the liability screen, the novelty screen,
ranking and selection, and the submission builder.

Each one gets a self-test on synthetic input before it touches real data. A screen that
silently passes everything is worse than no screen, because you will trust it.

## Honesty rules (non-negotiable)

- A metric that was not computed is **`not_run`**. Never a zero, never an estimate.
- Everything is labelled `measured`, `predicted`, `hypothesis` or `not_run`.
- **No design is called a validated binder.** Round 1 has not run yet.
- Keep every rejected candidate and its rejection reason.