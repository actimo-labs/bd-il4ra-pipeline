# CLAUDE.md — bd-il4r--pipeline

Operating contract for Claude Code sessions in this repo. Read this file end to end
before your first tool call in a new session. Then read `docs/CHALLENGE_SPEC.md`.

---

## 0. The one-paragraph brief

Design **de novo IgG-format antibodies against the human IL-4Rα extracellular domain**
and submit **up to 20 paired heavy/light chain sequences** to the GenScript x Geodesic
*Beyond Binding* Challenge, Round 1. Round 1 is scored by experimental binding only
(Carterra LSA, single concentration). Round 2 is developability, so Round 1 choices must
not create liabilities we cannot defend later.

**This is a ~66-hour sprint, not a campaign.** Behave accordingly.

---

## 1. Hard constraints — never relax these without the user saying so

| Constraint | Value | Consequence if broken |
|---|---|---|
| **Submission deadline** | **Mon 23 Nov 2026, 23:59 ET** = **Tue 24 Nov 2026, 15:59 AEDT** = **Tue 24 Nov 04:59 UTC** | Total loss. No partial credit. |
| Designs submitted | **≤ 20**, each a unique paired HC + LC | Submission rejected |
| Format | **IgG** — VH + VL variable domains; CH from `CH Type` (Human IgG1 or IgG4), CL from `CL Type` | Invalid entry |
| Signal peptide | **Do NOT include one.** GenScript prepends `MGWSCIILFLVATATGVHS` automatically | Duplicated signal peptide, dead construct |
| Novelty | De novo. **No existing IL-4Rα binder as a starting scaffold.** Novelty judged at **CDR level** | Disqualification |
| Target | Human IL-4Rα ECD, UniProt **P24394-1**, **AA 26–232** | Off-target design |

**Schedule discipline.** Work backwards from the deadline, not forwards from now:

- **T-24h (Mon 23 Nov ~16:00 AEDT): DESIGN FREEZE.** No new generation after this. Whatever has passed QC is the pool.
- **T-12h (Tue 24 Nov ~04:00 AEDT): SELECTION FREEZE.** The 20 are locked, Excel is built and validated.
- **T-6h (Tue 24 Nov ~10:00 AEDT): SUBMIT.** Dr. G is an interactive agent with upload validation that can bounce you. Do not meet the deadline with the submission unstarted.

If you are behind, **cut scope, never cut the freeze points.** A submission of 20
mediocre-but-valid designs scores infinitely better than 20 excellent designs submitted
at 00:05 ET.

---

## 2. Read this before you reuse anything from the previous campaigns

`VM_INVENTORY.md` (in the project) documents a proven 4-pillar stack:

```
RFdiffusion -> ProteinMPNN -> AF2 initial-guess -> Boltz-2
```

**That stack produces single-chain minibinders. It does not produce antibodies.**
Every one of the five prior campaigns on this box submitted a single-chain minibinder.
This challenge requires a paired VH/VL Fv. Do not try to force this target through the
old pipeline because the old pipeline is familiar and documented.

Specifically:

- **RFdiffusion base checkpoints are not antibody-finetuned.** The 9 checkpoints in the
  Docker image cannot design CDR loops on a framework. You need `RFdiffusion_Ab.pt`,
  which ships with **RFantibody**, which is **not installed**.
- **AF2 initial-guess does not drop in as the filter.** `dl_binder_design`'s
  initial-guess protocol and the `af2_util_nopyro.py` reimplementation assume a
  **single-chain** binder plus target. An Fv is two chains. Do not spend sprint hours
  retrofitting it. **RF2_ab (shipped with RFantibody) is the antibody filter.**
- **ProteinMPNN is still useful** but in RFantibody's interface-design mode with the
  framework held fixed, not vanilla full-chain redesign.
- **Boltz-2 transfers as-is** and is valuable as an *orthogonal* co-folding check on
  Fv+antigen. It is a second opinion, not the primary filter.
- **ANARCI is not installed.** You need CDR boundaries for novelty and liability
  checks. See `docs/RANKING_AND_QC.md` §2 for the install and the no-install fallback.

The recurring failure mode on this box, per `VM_INVENTORY.md` §6, is a plan that lists
tools as "proven, zero setup risk" that were never installed. **Assume nothing is
installed until you have run it.**

---

## 3. Environment — verified facts, and what to re-verify

Host: `actimo-run-pipepi-80gb-jj-20260903-014509`, Debian 11. 1x **A100-SXM4-80GB**,
driver 550.90.07, CUDA 12.4. 12 vCPU, 167 GB RAM, **no swap**. Passwordless sudo.

**Disk policy — this is not optional.**

| Mount | Size | Free | Use for |
|---|---|---|---|
| `/` (`/dev/sda1`) | 2.0 TB | **~25 GB (99% full)** | code, configs, manifests, final package **only** |
| `/mnt/comp5data` | 984 GB | **~977 GB** | **everything else** |

Root is full because of another tenant's home directory, not us. 25 GB will not survive
this sprint.

- All weights, venvs, model outputs, PDB pools, scorefiles → **`/mnt/comp5data/bd-il4r/`**
- **Docker's data-root lives on `/`.** A fresh RFantibody Docker image build will
  exhaust root. **Use the `uv` local install with the venv on `/mnt/comp5data`.**
  See `docs/SETUP_RFANTIBODY.md`.
  Docker *is* viable if you first relocate data-root to the scratch disk
  (`/etc/docker/daemon.json` -> `{"data-root": "/mnt/comp5data/docker"}`, restart the
  daemon) — but that is a daemon reconfiguration on a shared box mid-sprint, and it
  orphans the existing `rosettacommons/rfdiffusion` image. **Not worth the hours. Use uv.**
- RFdiffusion trajectory dumps leaked ~6 GB unnoticed in a prior campaign. **Disable
  trajectory output.**

**Conda is miniforge3 at `~/miniforge3` and is NOT on PATH in a fresh shell.** Use
absolute paths or `conda run -n <env>`. There is **no system biopython** — anything
importing `Bio` must run inside an env.

| env | Role | Notes |
|---|---|---|
| `boltz` | Boltz-2 + most analysis | torch 2.14.1+cu126, biopython, pandas, rdkit, ProDy |
| `mpnn` | ProteinMPNN | torch 2.5.1+cu121 |
| `af2ig` | AF2 initial-guess | **DO NOT TOUCH.** jax 0.4.20 pins are load-bearing and fragile. Not used this campaign. |
| `viz` | PyMOL 3.1.0 | figures, interface inspection |
| `venv-phscan` | propka, tmtools | `~/tnf-track3/venv-phscan` |

Run the preflight in §8 at the start of every session. If a check fails, fix the check
before doing science. Worth wrapping in `scripts/00_verify_env.sh` once you have run it
twice by hand — but hand-run it the first time, so you see what the box actually says.

---

## 4. The stack for this campaign

```
                    ┌─ PRIMARY A: RFantibody (local, A100) ──────────────┐
  IL-4Rα ECD        │  RFdiffusion_Ab  ->  ProteinMPNN  ->  RF2_ab       │
  target prep  ──>  │  (CDR backbones)    (CDR seqs)      (filter)       ├──> pooled
  + epitopes        └───────────────────────────────────────────────────-─┘    candidates
                    ┌─ PRIMARY B: Geodesic NovaDDE (platform, credits) ──┐         │
                    │  CDR design on framework -> NovaAtom -> ipTM/RMSD  ├─────────┘
                    └────────────────────────────────────────────────────┘         │
                                                                                   v
            Boltz-2 orthogonal co-fold  ->  QC/liabilities  ->  novelty  ->  rank  ->  pick 20
```

Two independent generators, because either one can fail inside 66 hours and neither is
proven on this box. Details and go/no-go gates in `docs/PIPELINE.md`.

---

## 5. Rules of engagement

**Do:**

- Inspect before you build. Check git status, existing files, installed packages, GPU
  state, and disk before proposing anything.
- Run long GPU jobs in **tmux**, checkpointed and resumable. Assume the session drops.
- Pilot before scaling. Run 2–5 designs end to end and inspect the output before
  launching hundreds. A prior campaign budgeted 16 GPU-h for a stage that measured 60.
- Append to `RUNLOG.md` as you go: what ran, the exact command, what came out, what
  failed, what you retracted. Append-only. This is the most valuable artefact in the repo.
- Keep raw model outputs, processed metrics, rejected candidates and final candidates in
  **separate** directories. Never overwrite a raw result.
- State GPU-hour estimates before any run longer than ~15 minutes.

**Never:**

- **Never fabricate a number.** No invented affinities, ipTM values, pass rates, novelty
  scores or success probabilities. If a metric was not computed, the manifest says
  `not_run`. Prior campaigns wrote `not_run` into four columns honestly rather than
  estimating. Keep that discipline — it is the reason the results are trustworthy.
- **Never call a predicted candidate a validated binder.** Label everything as
  `measured` / `predicted` / `hypothesis` / `not_run`.
- Never act on a rate computed from n < 100. Small-sample conclusions reversed three
  separate times in comp5 (3.1% at n=32 became 0.7% at n=272).
- Never upgrade, downgrade or `pip install` into the `af2ig` env.
- Never commit, push, upload or submit anything externally without explicit permission
  from the user. **Submission to Dr. G is a human-in-the-loop step — the user drives it.**
- Never start from a known IL-4Rα binder (dupilumab, patent antibodies) and mutate it.
  Those sequences may be used for **benchmarking, controls and novelty comparison only.**
- Never write bulk output to `/`.

---

## 6. Traps carried forward

1. **RFantibody RF2 stage fails on a bad default weight path.** Fix `model_weights` in
   `src/rfantibody/rf2/config/base.yaml` to the real `RF2_ab.pt` path *before* the first
   run, not after it wastes an hour. Same class of fix for the MPNN weights path in
   `scripts/proteinmpnn_interface_design.py`.
2. **RFantibody needs HLT-format PDBs.** Framework and target must be remarked into HLT
   (H/L/T chain convention) or the run fails or silently mis-assigns chains. See
   `docs/TARGET_PREP.md` §4.
3. **Score the binder↔target chain pair only.** With an Fv there are *three* chains
   (H, L, T). Global ipTM includes the H↔L interface, which is ~0.9 regardless of whether
   the antibody binds the antigen. **A high global ipTM on an Fv is meaningless.** Compute
   H+L vs T interface metrics explicitly and assert the chain selection in code.
4. **Hotspots must name the target chain's residue numbers *after* cropping/renumbering.**
   Assert this in code. Eyeballing missed this exact bug in a prior campaign.
5. **Silent column-matching bugs.** A prefix match on design IDs blanked an entire
   comparison. Match on full names, longest first, assert non-empty.
6. **Verify the submission column spec from the live template**, never from memory or a
   paraphrase of this doc. A prior campaign nearly shipped an invalid enum value.
7. **The MSA server at `10.148.0.19:8080` is dead and the host is gone.** Boltz-2 runs in
   `msa: empty` single-sequence mode. Remove it from any config; do not try to revive it.
8. **`gsutil` currently fails with "Reauthentication required."** Re-auth before relying
   on bucket access. Not needed for this campaign.

---

## 7. Layout

```
bd-il4r--pipeline/
  CLAUDE.md                  <- you are here
  README.md
  RUNLOG.md                  <- append-only, every session
  docs/
    CHALLENGE_SPEC.md        <- verified official rules + source links. GROUND TRUTH.
    PIPELINE.md              <- sprint plan, stages, go/no-go gates, compute budget
    SETUP_RFANTIBODY.md      <- install runbook (critical path)
    TARGET_PREP.md           <- IL-4Rα prep, glycan masking, epitope allocation
    GEODESIC.md              <- credit model, budget, what to verify before spending
    RANKING_AND_QC.md        <- eligibility gates, liabilities, novelty, ranking
    SUBMISSION.md            <- Dr. G procedure + Excel spec + pre-flight checklist
  KICKOFF_PROMPT.md          <- the prompt that starts the campaign session
  config/
    sprint.yaml              <- single source of truth for paths, epitopes, budgets
  scripts/                   <- EMPTY. You write these. Specs are in the docs; see section 10
  candidates.tsv             <- the manifest. Schema in RANKING_AND_QC.md section 7

/mnt/comp5data/bd-il4r/      <- ALL bulk artefacts (weights, venvs, PDBs, outputs)
```

---

## 8. Session start checklist

```bash
# hours remaining
python3 -c "import datetime as d;x=(d.datetime(2026,11,24,4,59)-d.datetime.utcnow());print(f'T-{x.total_seconds()/3600:.1f}h')"

nvidia-smi                                  # GPU free? expect ~1 MiB used, no other tenant
df -h / /mnt/comp5data                      # root is TIGHT. scratch is where work goes
~/miniforge3/bin/conda env list
ls ~/.boltz/*.ckpt                          # Boltz-2 weights
~/miniforge3/envs/boltz/bin/python -c "import torch;print(torch.cuda.is_available())"
ls /mnt/comp5data/bd-il4r/rfantibody/weights/ 2>/dev/null || echo "RFantibody NOT installed -> gate G1"

git status --short                           # uncommitted work from a dropped session?
tail -40 RUNLOG.md                           # what was the last session doing?
cat config/sprint.yaml                       # gate state + budgets
```

**`torch.cuda.is_available()` must print `True`.** A CUDA mismatch makes a model fall back
to CPU **silently** — that is what turned a 10 s/design screen into something unusable in
a prior campaign. Check it; never infer it from a run "looking like it started".

Then state, in one line: hours remaining to deadline, current stage, the single
highest-value next action. Then do it.

---

## 9. Known unknowns — do not paper over these

- **Does Geodesic NovaDDE support paired VH/VL, or only VHH/nanobody?** The public
  workbench writeup shows a VHH example with an `h-NbBCII10` framework. A VHH cannot be
  submitted — the template requires both a heavy and a light chain. **This is gate G0 in
  `docs/PIPELINE.md` and must be resolved before any credits are spent.**
- **RFantibody has never been installed on this box.** Treat the install as a timed,
  abortable task with a hard fallback, not an assumption.
- **De novo antibody design hit rates are low.** Published work reports single-digit
  percent binders by SPR, and paired Fv is harder than VHH. With 20 slots and no
  iteration, **diversity across epitopes and frameworks beats depth on one epitope.**
  Do not let the pipeline converge on 20 near-identical designs.

---

## 10. Code you must write

**No Python ships with this repo. You write it, from the specs below.** Write it as you
need it — do not build the whole toolchain up front, and do not write a module whose
inputs do not exist yet.

| Module | Spec lives in | Notes |
|---|---|---|
| Target prep + numbering map + glycan mask | `TARGET_PREP.md` §1–2, §7 | First thing you need. Assert, do not eyeball |
| Epitope definition (E1 from contacts; E2/E3 patch scoring) | `TARGET_PREP.md` §6 | Writes `epitopes/E*.json` with provenance |
| HLT conversion + target cropping | `TARGET_PREP.md` §4 | Use RFantibody's shipped converter; assert 3 chains, IDs exactly H/L/T |
| Interface scoring, **(H+L) vs T only** | `PIPELINE.md` §4, `RANKING_AND_QC.md` §5 | Global ipTM on an Fv is meaningless. Assert the chain selection |
| Eligibility gates + liability screen | `RANKING_AND_QC.md` §2–3 | Full motif table, weights, thresholds and limits are given. **Stdlib-only** — there is no system biopython |
| Novelty screen (CDR-level, frozen reference set) | `RANKING_AND_QC.md` §4 | `blastp`/`makeblastdb` are present at `/usr/bin` |
| Ranking + diversity-aware selection of 20 | `RANKING_AND_QC.md` §5–6 | Rank *within* model family, then combine ranks |
| Submission table builder + validator | `SUBMISSION.md` §1–2 | Five columns. Must refuse to write on any validation error |

Every one of these gets a `--self-test` or equivalent that runs on synthetic input before
you point it at real data. A screen that silently passes everything is worse than no
screen, because you will trust it.

Standing requirements for all of it: stdlib or the `boltz` env; checkpointed and
resumable; `not_run` for anything uncomputed; full-name joins asserted non-empty; raw
outputs never overwritten.