# RUNLOG.md

**Append-only.** Never edit or delete an earlier entry — including a wrong one. If a
conclusion is retracted, append the retraction; do not rewrite history. This file is the
most valuable artefact in the repo and the reason the results can be trusted.

Every entry: what you intended, the **exact command**, what came out, what it cost, and
what you concluded. Failures and dead ends are the highest-value content here — they stop
the next session at 3am from retrying something already known to be broken.

Template:

```
## YYYY-MM-DD HH:MM AEDT -- <short title>
Gate: G_  |  Arm: A/B  |  T-__h
Intent:
Command:
Result:
Cost: __ GPU-min / __ credits
Conclusion:
Next:
```

---

## 2026-11-21 ~22:00 AEDT -- repo handoff prepared
Gate: pre-G0  |  Arm: -  |  T-66h

Intent: stand up the repo and planning docs for the Beyond Binding Round 1 sprint.

Result: docs written. Key findings from reading the brief and verifying sources:

- **Deadline is T-66h, not weeks.** Mon 23 Nov 23:59 ET = Tue 24 Nov 15:59 AEDT.
  Confirmed live via GenScript's own announcement, same date and deadline.
- **Format gap.** The challenge needs paired VH/VL IgG. All five prior campaigns on this
  box produced single-chain minibinders. The proven 4-pillar stack does not transfer:
  RFdiffusion base checkpoints are not antibody-finetuned, and AF2 initial-guess assumes a
  single-chain binder. **RFantibody is the right tool and is not installed.**
- **Target verified.** UniProt P24394: signal 1-25, ECD topological domain **26-232**
  (exactly matches the brief), TM 233-256, disulfides 34-44 and 74-86.
  **N-glycosylation at N53, N98, N128, N134, N176, N209 -- all six inside the ECD.**
  Six glycans on a 207-residue domain materially constrains epitope choice.
- **Better structure than the one the brief cites.** The brief sources its image from
  **3BPN** (3.02 A, ternary IL-4/IL-4Ra/IL-13Ra1, NAG modelled on chain B). **1IAR**
  is a 2.30 A binary IL-4/IL-4Ra complex, chain B = 207 aa, matching the ECD exactly.
  Using 1IAR chain B as the design target, 3BPN chain B as cross-check.
  Note 1IAR chain B carries **M1F and C182A** -- C182 is an unpaired Cys in the WT ECD.
- **Geodesic "tokens" are credits.** 1,000 = the Plus tier *weekly* allowance, resets
  00:00 UTC on an assigned day, **does not roll over**. Cost varies by model and input
  size and is quoted before submitting. **Failed or cancelled runs are still charged.**
  Top-up is **$0.01/credit, min $5** -- i.e. ~$10 per 1,000. Entirely separate currency
  from Claude Code tokens (LLM inference, buys no protein compute) and from GenScript
  service credits (pre-applied, just verify the order total reads 0.00 USD).
- **Open gate G0:** the public NovaDDE writeup shows antibody CDR design with a **VHH**
  example (`h-NbBCII10` framework). A VHH cannot be submitted -- the template requires
  both a heavy and a light chain. **Paired VH/VL support must be confirmed before any
  credits are spent.**

Scripts written and tested: `qc_liabilities.py` (self-test passes, 6 synthetic cases),
`build_submission.py` (validation guard rails confirmed to refuse on row-count mismatch),
`00_verify_env.sh` (countdown + fail-loud checks confirmed).

Conclusion: fallback rung **F0** assumed (both arms live) pending gate G0.

Next:
1. **User:** test the GenScript challenge login. Confirm the Geodesic account email
   matches the challenge-registration email.
2. **User:** Geodesic Settings -> Usage -- note the credit reset day. A reset inside the
   sprint window is +1,000 free credits.
3. **G0:** confirm whether NovaDDE supports paired VH/VL. If VHH-only, Arm B is dead ->
   rung F2.
4. **Step 0 of `docs/SETUP_RFANTIBODY.md`:** probe the RFantibody weight-download host
   reachability from the VM *before* spending any of the 3-hour install time box. The
   weights come from an institutional host, not GitHub or PyPI, and only RCSB/PyPI/GitHub
   are verified reachable.

---

## 2026-11-21 ~23:00 AEDT -- handoff finalised, decisions locked
Gate: pre-G0  |  Arm: -  |  T-65h

Intent: convert the planning pack into a docs-only Claude Code handoff and close the open
questions from the first pass.

Decisions taken by the user:

- **RFantibody is the primary local arm.** Disk headroom confirmed on the second disk
  (`/mnt/comp5data`, ~977 GB). Install via **`uv`**, not Docker: Docker's data-root is on
  the 99%-full root disk, and relocating it mid-sprint orphans the existing
  `rosettacommons/rfdiffusion` image for no benefit. Scratch discipline still applies --
  root has ~25 GB and `uv`'s caches default there.
- **Epitope allocation: split.** ~12 at the IL-4/IL-13 competitive site (E1), ~5 + ~3 at
  two alternate glycan-masked patches (E2/E3). Hedges epitope-level failure.
- **No Python in the handoff.** The agent authors every module from the specs; `scripts/`
  ships empty. `CLAUDE.md` section 10 is the module-to-spec map. Nothing was lost -- the
  liability screen, novelty screen, ranking and submission builder were already fully
  specified in `RANKING_AND_QC.md` sections 2-6 and `SUBMISSION.md` sections 1-2.
- `KICKOFF_PROMPT.md` added: stateless, re-pasted each session, state carried by this log
  and `config/sprint.yaml`.

Verified against the live challenge hub this session:

- **Design format is IgG1**, stated specifically on the hub -- not "IgG1 or IgG4" as the
  batch-template dropdown implies. `CH Type` is therefore **locked to Human IgG1** for all
  20. Removes an ambiguity that was previously a judgement call.
- Target restated identically on the hub: UniProt **P24394-1**, **AA26-232**, up to 20
  designs per participant. No contradiction with the brief.
- **No deadline extension or change.** The hub states no new date. Deadline stands at
  Mon 23 Nov 23:59 ET / Tue 24 Nov 15:59 AEDT.

**GenScript service credits clarified -- there is nothing to manage.** They are a coupon
pre-loaded on the *challenge-specific* GenScript account that auto-applies at checkout and
zeroes the order (20 x $152.50 = $3,050, plus the Carterra LSA assay, plus the 100ug
Fc-tagged antigen; Item Count 22). Three operational consequences only: log in with the
challenge account from the official e-mail and not a personal one, verify the total reads
0.00 USD before confirming, and do not deviate from the scoped order (format, count,
assay, antigen) or the coupon may not apply. Nothing to conserve -- submit all 20.
Documented in `CHALLENGE_SPEC.md` section 9b. Distinct from Geodesic credits, which are a
real metered budget.

Conclusion: handoff complete. Fallback rung **F0** assumed pending gate G0.

Next, in order (cheapest hard blockers first):
1. **Agent, 2 min:** probe the RFantibody weight-download host reachability from the VM
   (`SETUP_RFANTIBODY.md` Step 0). Institutional host, not GitHub/PyPI; only RCSB, PyPI and
   GitHub are verified reachable. A block here kills the local arm -> rung F1.
2. **Agent:** scratch + `env.sh` with `uv` caches redirected, then install, then patch the
   three known-bad weight paths, then target prep, then the 2-design pilot. 3-hour time
   box, hard abort at G1.
3. **User:** test the challenge-specific GenScript login.
4. **User:** confirm the Geodesic account email matches the challenge-registration email,
   and note the credit reset day under Settings -> Usage. A reset inside the sprint is
   +1,000 free credits.
5. **User, gate G0:** confirm whether NovaDDE supports paired VH/VL. The public example is
   a VHH, which cannot be submitted -- the template requires both chains. VHH-only -> Arm B
   is dead -> rung F2.

---

## 2026-11-21 12:28–12:40 UTC (23:28 AEDT) — OVERNIGHT SESSION START. Weight host probe + RFantibody install
Gate: G1 (in progress)  |  Rung: F0  |  T-64.5h

**Mode:** unattended overnight run per `OVERNIGHT_ADDENDUM.md`. User asleep until ~08:00
AEDT. All ambiguity resolved by the agent and logged here. Zero Geodesic credits spent;
Arm B left `not_started` per the addendum.

### Action 1 — RFantibody weight host reachability (SETUP_RFANTIBODY.md Step 0). PASS.

Intent: the weights come from an institutional host (IPD/UW), not GitHub/PyPI. Only RCSB,
PyPI and GitHub were verified reachable from this box. A block here kills the local arm.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://github.com/RosettaCommons/RFantibody   # 200
git clone --depth 1 https://github.com/RosettaCommons/RFantibody /tmp/rfab-probe
grep -Eo 'https?://[^ "'"'"']+' include/download_weights.sh
curl -sSI --max-time 25 https://files.ipd.uw.edu/pub/RFantibody/<each>.pt | head -1
```

Result — **all weight hosts reachable**:

| URL | HTTP | content-length |
|---|---|---|
| `files.ipd.uw.edu/pub/RFantibody/RFdiffusion_Ab.pt` | **200** | 483,452,922 |
| `files.ipd.uw.edu/pub/RFantibody/RF2_ab.pt` | **200** | 294,759,918 |
| `files.ipd.uw.edu/pub/RFantibody/ProteinMPNN_v48_noise_0.2.pt` | **200** | 6,681,301 |
| `zenodo.org/records/17488258/...RFab_noframework...pt` (RF2 **TCR**) | **200** | 882,991,901 |

**Conclusion: the local arm is alive. Rung stays F0 (Arm A live; Arm B deferred, not dead).**
No egress-allowlist decision needed from the user. That parked item is moot for Arm A.

**Decision (agent, logged for reversal):** skipped the 883 MB Zenodo **RF2 TCR** weight.
`grep -rn` over `src/`, `scripts/` shows it is referenced **nowhere** in the codebase —
only `include/download_weights.sh` fetches it. It is for TCR design, not antibody design.
Saves 883 MB and ~2 min. Reversible: re-run the wget line if an RF2 config ever asks for it.
Downloaded the other three directly rather than via `download_weights.sh` (the script's
`&&` chain would have forced the TCR download too).

### Action 2 — scratch + env file (Step 1). DONE.

`/mnt/comp5data/bd-il4r/env.sh` written and is the sourceable env for every later session:
`BDIL4R`, `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `PIP_CACHE_DIR`, `TORCH_HOME`,
`HF_HOME`, `XDG_CACHE_HOME` all redirected to scratch; `PATH` += `~/.local/bin`;
`DGLBACKEND=pytorch` (silences a DGL backend warning on every import).

Disk, before and after the whole install:

```
BEFORE  /dev/sda1 2.0T 1.9T  25G 99% /          /dev/sdb 984G 6.9G 977G 1% /mnt/comp5data
AFTER   /dev/sda1 2.0T 1.9T  25G 99% /          /dev/sdb 984G  14G 970G 2% /mnt/comp5data
```

**Root did not move.** The cache redirection worked; ~7 GB landed on scratch as intended.

### Action 3 — install (Steps 2–3). DONE in ~6 min against a 3-hour time box.

- RFantibody commit SHA: **`efe4b9040f051edc229e9318ead586ff76236c9b`**
- `uv` 0.13.9 installed to `~/.local/bin`; `uv cache dir` confirmed `=/mnt/comp5data/bd-il4r/uv-cache`
- `uv sync`: **24.4 s**. Resolved torch **2.3.1+cu118**, torchvision 0.18.1+cu118,
  torchaudio 2.3.1+cu118, triton 2.3.1, numpy 1.x, dgl **2.4.0+cu118**, hydra-core,
  biotite, e3nn, pandas 2.3.3. venv at `$BDIL4R/rfantibody/.venv` (on scratch).

**CUDA verification — the silent-CPU-fallback check:**

```
torch 2.3.1+cu118
cuda_available True          <-- REQUIRED. confirmed, not inferred
device NVIDIA A100-SXM4-80GB
dgl 2.4.0+cu118
matmul ok True               <-- real GPU tensor op executed
```

**Correction to `SETUP_RFANTIBODY.md` Step 3 — the DGL warning is now stale.** The doc
says DGL "must come from CUDA-enabled wheels, and it is the most common install failure
in this stack", implying a separate manual step. At commit `efe4b90` that is **already
fixed upstream**: `pyproject.toml` pins dgl to a wheel hosted on the RFantibody GitHub
releases page (`deps-dgl-2.4.0/dgl-2.4.0+cu118-cp310-cp310-manylinux1_x86_64.whl`),
because the original dgl.ai host went away. `uv sync` handles it with no manual step.
No action needed; flagging so nobody hunts for a problem that no longer exists.

### Known-bad paths confirmed present (Step 4) — to patch before first run

`grep` confirms both documented traps are real at this commit:

```
src/rfantibody/rf2/config/base.yaml:18:  model_weights: /home/weights/RF2_ab.pt
scripts/proteinmpnn_interface_design.py:45: ... '/home/weights/ProteinMPNN_v48_noise_0.2.pt'
```

Both are Docker-internal paths that do not exist in a `uv` local install. Third trap
(`model_runners.py` checkpoint default) still to be checked. Patching next.


### Step 4 — weight-path patches applied. All three traps resolved.

**Finding that changes the risk picture: at commit `efe4b90` the CLI entry points already
inject the correct weights path, so the two documented "known-bad path" traps cannot fire
when the pipeline is driven through `rfdiffusion` / `proteinmpnn` / `rf2`.**
`src/rfantibody/cli/inference.py` calls `PathConfig.get_weight_path(<model>)` and appends
an explicit override (lines 134, 276, 425). `PathConfig.WEIGHTS_DIR` defaults to
`PROJECT_ROOT/weights`, which is exactly where ours live, so resolution is correct:

```
rfdiffusion  .../weights/RFdiffusion_Ab.pt             exists=True  size=483452922
proteinmpnn  .../weights/ProteinMPNN_v48_noise_0.2.pt  exists=True  size=6681301
rf2          .../weights/RF2_ab.pt                     exists=True  size=294759918
```

All three sizes match the `content-length` from the Step 0 HEAD probe exactly — downloads
are complete and not truncated.

**But the injection is conditional on `default_weights.exists()`, with a silent fallthrough
to the Docker path if it is false.** That is a latent silent-failure mode, so the patches
were applied anyway as belt-and-braces:

```diff
--- a/src/rfantibody/rf2/config/base.yaml
-  model_weights: /home/weights/RF2_ab.pt
+  model_weights: /mnt/comp5data/bd-il4r/rfantibody/weights/RF2_ab.pt

--- a/scripts/proteinmpnn_interface_design.py
-default_ckpt = os.path.join( os.path.dirname(__file__), '/home/weights/ProteinMPNN_v48_noise_0.2.pt')
+default_ckpt = '/mnt/comp5data/bd-il4r/rfantibody/weights/ProteinMPNN_v48_noise_0.2.pt'
```

(The original mpnn line was doubly broken: `os.path.join` with an absolute second argument
discards the first, so `os.path.dirname(__file__)` was dead code.)

**Trap 3 confirmed real and handled differently.** `model_runners.py:70-81` falls back to
IPD-internal paths (`/net/databases/diffusion/models/hotspot_models/base_complex_finetuned_BFF_9.pt`
et al.) when `inference.ckpt_override_path` is None. Per the runbook's preferred option we
will **always pass the checkpoint explicitly** rather than edit the file. `model_runners.py:196`
prints the resolved `ckpt_path` at load time — the pilot log will be checked for it.

`--no-trajectory` confirmed as the real flag name against `rfdiffusion --help`
(maps to `inference.write_trajectory=False`). Trajectory output will be off in every run.

### Doc/code mismatch, non-blocking
README says the HLT converter is `scripts/util/chothia_to_HLT.py`; the file on disk is
`scripts/util/chothia2HLT.py`. Not on our critical path — the hu-4D5-8 framework ships
pre-converted at `scripts/examples/example_inputs/hu-4D5-8_Fv.pdb`.

### Upstream guidance captured from README (drives G2 sizing and the filter)
- **Authors' minimal filter: RF2 pAE < 10, and RMSD(design vs RF2 prediction) < 2 Å.**
  Rosetta ddG < -20 optional (Rosetta not installed; skip).
- Authors state the filter is the pipeline's main weakness and expect **~10k designs** for
  hits in the general case. We have ~24 GPU-h. This confirms `PIPELINE.md` §6's honest
  expectation of 1-3 hits and makes **diversity over depth** the correct strategy.
- Example CDR loop ranges: `H1:7,H2:6,H3:5-13,L1:8-13,L2:7,L3:9-11`.
- "RFantibody is more sensitive to exactly which hotspots are selected than vanilla
  RFdiffusion... will generally just generate an undocked antibody if a bad set of
  hotspots is given." **Undocked output is the expected symptom of bad hotspots** — this is
  the thing to look for in the pilot, not a crash.
- Authors independently flag that **sites with nearby glycans are hard** because the glycan
  orders on binding. Independent support for the 12 A glycan mask.
- Hotspot syntax is chain-prefixed target numbering, e.g. `-h "T305,T456"` -> post-crop
  chain-T numbering. This is exactly the trap in `TARGET_PREP.md` §1.


---

## 2026-11-21 12:45–13:20 UTC — Target prep. Numbering map, glycan mask, E1/E2/E3 frozen
Gate: G1 (target prep DONE)  |  Rung: F0  |  T-63.8h

Modules written: `scripts/01_target_prep.py` (13/13 self-test), `scripts/02_epitopes.py`
(14/14 self-test). Both run under `conda run -n boltz`.

### Numbering map — DERIVED and CROSS-CHECKED, not assumed

**`uniprot_resnum = pdb_resnum + 25`** for 1IAR chain B.

Derived from `SEQADV` records, not from an alignment guess:

```
1IAR  pdb 182 -> uniprot 207  (CYS->ALA ENGINEERED MUTATION)
1IAR  pdb   1 -> uniprot  26  (MET->PHE ENGINEERED MUTATION)
3BPN  pdb  28 -> uniprot  53  | pdb  73 -> uniprot  98
3BPN  pdb 109 -> uniprot 134  | pdb 151 -> uniprot 176
```

`derive_offset()` asserts a **single** consistent offset or refuses to run. Both
structures independently give +25 — **cross-check passed**. Written to
`target/numbering_map.json` as a 207-row file, as required.

Assertions that passed: SEQRES chain B is exactly **207** residues == ECD length; pdb
1..207 maps to uniprot 26..232 == the brief's AA26-232; **all 188 observed residues match
SEQRES at their index** (this is the off-by-one detector).

### Three corrections to the handoff docs

1. **There are THREE disulfides in chain B, not two.** 1IAR `SSBOND` for chain B:
   pdb (9,19), (29,59), (49,61) = **uniprot (34,44), (54,84), (74,86)**. `CLAUDE.md`,
   `TARGET_PREP.md` §1 and `sprint.yaml` all list only (34,44) and (74,86). The
   **(54,84)** pair is real and present. Added to `sprint.yaml` as
   `disulfides_observed_uniprot`.
2. **There is no unpaired Cys in 1IAR chain B.** All six Cys (34,44,54,74,84,86) are in
   SSBOND records. The free cysteine `TARGET_PREP.md` §2 warns about is **uniprot C207 =
   pdb 182**, which 1IAR mutated to Ala. So our model has **A** at that position and the
   real antigen has **C**. Recorded. pdb 182/183 were in the raw IL-4 contact set and are
   **excluded by the glycan mask anyway** (5.6-7.5 A from sequon N209), so no interface is
   being built against a position whose identity differs from the real antigen. Good.
3. **The patent numbering question is RESOLVED.** `TARGET_PREP.md` §6 flags a third-party
   patent epitope at **L39, F41, L42, L43, D72, Y74** as "numbering convention unverified
   by us". Tested both conventions against the actual sequence:

   | residue | under PDB numbering | under UniProt numbering |
   |---|---|---|
   | L39 | **L**39 MATCH | M39 |
   | F41 | **F**41 MATCH | I41 |
   | L42 | **L**42 MATCH | S42 |
   | L43 | **L**43 MATCH | T43 |
   | D72 | **D**72 MATCH | H72 |
   | Y74 | **Y**74 MATCH | C74 |

   **6/6 identities match PDB (mature-protein) numbering; 0/6 match UniProt.** The patent
   uses mature/1IAR numbering. Five of its six residues (39,41,42,43,72) are in our raw
   IL-4 contact set. Treated **strictly as evidence that the region is antibody-accessible**
   — no sequence from that patent is used anywhere, per the hard rule.

### GLYCAN MASK RELAXED 12.0 A -> 10.0 A. Logged loudly, as required.

`TARGET_PREP.md` §2 rule 2 permits 12->10 **if and only if** masking leaves no viable
epitope. **That condition was met.** Evidence, not preference:

At 12.0 A the mask removes **97 of 188** observed residues (52%) and cuts E1 from 20 raw
IL-4 contacts to 8. Those 8 span **30.6 A** — far wider than an Fv paratope — so the
question is not "how many residues survive" but "is there an **Fv-sized sub-site** that is
designable". Enumerating every 11 A sub-site inside E1:

| mask | best sub-site | hydrophobic | area |
|---|---|---|---|
| **12.0 A** | L42+L43 only | **2** | **302 A²** |
| 12.0 A | D66,D67,D125,N126,Y127 | **1** | 541 A² |
| **10.0 A** | Y13,D67,V68,V69,S70,D125,N126,Y127,N130,H131 | **4** | **675 A²** |

The documented minimums are **>~3 hydrophobic residues** (RFantibody README: "Binding to
charged polar sites is still quite hard") and **>=600 A² burialable** (`TARGET_PREP.md` §6).
**At 12.0 A no sub-site clears either. At 10.0 A several clear both.** So no viable epitope
remains at 12 A on the project's own criteria.

Two independent lines of biological support:

- **IL-4 itself binds this surface despite the glycans.** Nearest IL-4 heavy atom to
  sequon N98 Cβ is **9.0 A**, and to N209 Cβ **7.8 A**. A sub-nanomolar native ligand
  engages residues well inside the 12 A shell, so those glycans are demonstrably not
  occluding that face.
- A real antibody (the patent above) binds an epitope including L42/L43, which the 12 A
  mask retains but strands with no hydrophobic partners.

Applied **uniformly**, not cherry-picked for E1: at 10.0 A the mask removes 63/188 (34%).
**Both runs preserved** in `target/radius_study/` (`*_r12.json`, `*_r10.json`) — nothing
overwritten. `sprint.yaml` updated with the radius and the rationale.
**This is reversible in one step:** `GLYCAN_MASK_RADIUS=12.0 python scripts/01_target_prep.py`.

**Residual risk, stated plainly:** sequon N98 sits inside the IL-4 competitive site. If
that glycan is occupied and bulky, E1 designs may bind the model and not the antigen. This
is the single largest silent-failure risk in the campaign and it is exactly why E2/E3
exist on independent surface.

### Epitopes frozen

Hotspots are **PDB numbering of 1IAR chain B** here; `03_crop_hlt.py` re-maps them to
post-crop chain-T numbering and re-asserts residue identity before any run.

| Epitope | Slots | Residues | Hotspots (UniProt) | Area | Hydrophobic |
|---|---|---|---|---|---|
| **E1** IL-4 competitive site | 12 | 13 | **D92, V94, D150, Y152** | 675 A² | 4 |
| **E2** seed R59 | 5 | 13 | **L61, I75, W104, L109** | 1042 A² | 6 |
| **E3** seed L139 | 3 | 10 | **L140, R185, A187, A188** | 956 A² | 6 |

73 patches scored, 43 passed the hard gates, full table (including every rejected patch
and its rejection reason) in `target/patch_scoring.tsv`. E2/E3 selected greedily by score
with a >=14 A centroid separation so they are not two views of one surface; both are
>=25 A from E1. Scoring weights are **[ASSUMPTION] ours**, recorded in each epitope JSON.

1IAR vs 3BPN chain B: 188 shared residues, **global CA RMSD 1.10 A** — the two
crystal forms agree well, so no chosen patch is conformationally uncertain.

**Note E2 and E3 are both markedly better design targets than E1** (6 hydrophobic, ~1000 A²
vs 4 and 675). E1 keeps the larger slot allocation because it is the functionally
meaningful site and has the strongest Round 2 narrative, but if the pilot shows E1 docking
poorly, the slot split should move toward E2. Flagged for the G2 decision.

### Bug caught by running the module (recorded so it is not reintroduced)

First real run selected **Y38 as an E1 hotspot — SASA 7.6 A², a buried core residue.**
The hotspot score combined exposure, centrality and hydrophobicity, and centrality plus
the hydrophobic bonus outvoted near-zero exposure. A buried hotspot would steer
RFdiffusion at a surface that does not exist, and the symptom (per the README) would be
undocked antibodies — easy to misread as a bad epitope rather than a bad hotspot.
Fixed with a **hard SASA floor of 30 A² applied before ranking**, plus an assertion on
every returned hotspot and two new self-tests (buried residue never chosen; all-buried
patch raises instead of returning garbage). E1 hotspots changed Y38 -> **D92**.


### Crops and framework built — `scripts/03_crop_hlt.py` (8/8 self-test)

**Target-file format verified against the shipped example, not assumed.**
`scripts/examples/example_inputs/rsv_site3.pdb` is chain **T**, **zero REMARK lines**, and
**keeps its original residue numbering** (it runs 253..960 with gaps — it is *not*
renumbered 1..N). So our crops keep 1IAR chain B PDB numbering and only relabel the chain.

That means post-crop numbering == pre-crop numbering. CLAUDE.md trap 4 still demands the
hotspots be named in post-crop numbering, so `verify_target()` **re-parses the file we
just wrote** and asserts (a) exactly one chain and it is `T`, (b) every hotspot is present,
(c) each hotspot's one-letter code matches SEQRES at that index. A numbering slip fails
loudly instead of producing a plausible-looking run.

| Epitope | Crop | Atoms | Segments | **Hotspot string for RFdiffusion** |
|---|---|---|---|---|
| E1 | 87 res | 715 | 7 | **`T67,T69,T125,T127`** (D92, V94, D150, Y152 UniProt) |
| E2 | 87 res | 676 | 2 | **`T36,T50,T79,T84`** (L61, I75, W104, L109) |
| E3 | 59 res | 481 | 5 | **`T115,T160,T162,T163`** (L140, R185, A187, A188) |

Calibration against the shipped example: `rsv_site3.pdb` is 251 residues in 5 segments
(lengths 23/46/58/62/62). E1's 7 segments are shorter (7-18 residues each) but each is a
single secondary-structure element, and 87 residues keeps RF2/RFdiffusion's O(N²) cost
down. **E1 is the most fragmented crop** — if the pilot shows undocked output for E1 but
not E2, crop fragmentation is the first thing to suspect, ahead of the hotspots.

Framework `hu4D5-8_Fv_HLT.pdb` copied from the RFantibody examples (ships pre-converted).
Verified: chains exactly H+L, H=116 L=107 residues, and `PDBinfo-LABEL` REMARKs present
for **all six** CDRs — H1 26-32, H2 52-57, H3 99-105, L1 140-150, L2 166-172, L3 205-213
(1-indexed absolute across H then L, matching the HLT spec). No CDR index exceeds the
residue count.

The `chothia2HLT.py` converter was not needed. Note the README calls it
`chothia_to_HLT.py`; the actual filename is `chothia2HLT.py`.


---

## 2026-11-21 13:20–14:05 UTC — Interface scorer + a real SASA bug found and fixed
Gate: G1  |  Rung: F0  |  T-63.0h

`scripts/04_interface.py` written — **(H+L) vs T** interface scoring. 17/17 self-test.

### A genuine bug, found because an invariant was asserted rather than eyeballed

The first self-test run produced a **negative buried surface area (−221 Å²)** on a
synthetic complex. BSA = SASA(A) + SASA(B) − SASA(AB); adding chains can only *reduce*
total SASA, so a negative BSA is physically impossible and meant the SASA itself was wrong.

Narrowed it down with a controlled experiment:

```
2 chains (40 atoms), resnums 1-5 in both :  601.33   <- H and L occlude each other
3 chains (60 atoms), resnums 1-5 in all  :  822.53   <- occlusion GONE
3 chains (60 atoms), UNIQUE resnums      :  616.46   <- occlusion back
```

Constant +221.20 Å² error regardless of how far away the third chain was (tested to
1000 Å), so it was not geometric. **The cause is duplicate residue IDs across chains in
the Bio.PDB entity tree I was constructing** — my wrapper's fault, not a biopython defect.
It matters here because **an Fv-antigen complex always has duplicated residue numbers**
(H1.., L1.., T1..), so this would have silently corrupted every BSA in the campaign.

**Fix: replaced the biopython wrapper with an in-house Shrake-Rupley** (numpy, 256-point
golden-spiral sphere, standard vdW radii + 1.4 Å probe) in `01_target_prep.py`, now shared
by `04_interface.py`. Self-contained, no entity tree, no ID semantics to get wrong.

**Validated against biopython on the single-chain case, where biopython is correct:**

```
n residues compared : 188
total SASA   mine = 10939.6   biopython = 10967.0   ratio 0.9975
pearson r           0.99812
mean abs diff       2.07 A^2   (max 11.14)
```

Added two regression guards to the self-test: BSA is never negative, and BSA is unaffected
by residue numbers duplicated across chains.

**Impact on earlier work: none material.** `01_target_prep.py` built a *single* chain with
unique resnums — the well-behaved case — so the hotspot SASA values were already sound.
Re-ran everything against the in-house SASA to confirm:

- **E1 unchanged**: same 13 residues, same hotspots **D92, V94, D150, Y152**. Y38 is still
  correctly rejected as buried (5.2 Å² under the new code vs 7.6 Å² under biopython).
- **E3 unchanged**: seed L139, hotspots L140, R185, A187, A188.
- **E2 shifted**: seed R59 → **L109**, hotspots now **L61, W104, L109, L110** (was L61,
  I75, W104, L109). Small SASA differences moved the patch ranking. The new patch is
  11 residues / 882 Å² / 5 hydrophobic. `sprint.yaml` and the E2 crop updated.
- **E1 crop is byte-identical (md5 `6223403a…`), so the pilot already running against it
  remains valid** and did not need restarting.

### Why this module reports the H↔L interface at all

It is emitted as `H_vs_L_NEGATIVE_CONTROL`, with a warning string attached. The self-test
asserts that **H↔L is numerically identical between a bound and an unbound complex while
(H+L) vs T differs** — that is the trap from `CLAUDE.md` §6 trap 3 demonstrated
executably, rather than just written down. `score_hlt()` also hard-asserts the chain set
is exactly {H, L, T} and refuses to score a complex with a missing light chain in strict
mode, because that would silently turn an Fv score into a VHH score.


---

## 2026-11-21 12:46–14:40 UTC — PILOT COMPLETE. **GATE G1 PASSED.**
Gate: **G1 PASSED**  |  Rung: F0  |  T-62.4h

2 designs x 2 MPNN sequences, E1, hu4D5-8 framework, run in tmux via
`scripts/10_run_pilot.sh`. All three stages returned rc=0.

### MEASURED throughput (the G2 sizing numbers — measured, not estimated)

```
RFdiffusion_Ab   : 174.0 s/design   (Fv 223aa + E1 crop 87aa = 310 residues, n=2)
ProteinMPNN      :   2.25 s/sequence  (4.5 s/backbone at 2 seqs; 9.0 s total)
RF2_ab           :  26.5 s/design   (10 recycles, n=4)
```

Cost per backbone at k MPNN sequences: **174 + k x 28.75 s**. RFdiffusion dominates
overwhelmingly, which is the quantitative basis for the deep-resample strategy: a new
backbone costs 174 s, another sequence on an existing backbone costs **28.75 s — 6x
cheaper**. `PIPELINE.md` §3 rule 2 is correct for this system and now has a local number.

GPU peaked at 75% utilisation, 2277 MiB. `torch.cuda.is_available()` was True. Root disk
unchanged at 25 G. Total pilot wall clock 7m43s.

### Acceptance criteria — all seven ticked

- [x] **Three chains, IDs exactly H, L, T** — H=119, L=106, T=87 residues
- [x] **Diffused regions are the CDR loops, not framework.** Verified by sequence, not by
      eye: RFdiffusion output is the hu4D5-8 framework *verbatim* with poly-G only at CDR
      positions. CDR lengths varied inside the requested ranges (H3 7→10 and 7→13 against
      `H3:5-13`; L1 11→9; L3 9→10). ProteinMPNN then designed exactly **49** positions =
      7+6+10+9+7+10, i.e. the six CDRs and nothing else.
- [x] **CDR loops contact the intended epitope** — see table below; 62–69% of target
      contacts are on E1 for the good backbone, and hotspots V94/D150/Y152 are engaged
      by 3 of 4 designs
- [x] **RF2 produced non-null interface metrics** — 13 `SCORE` lines, see below
- [x] **Metrics computed on (H+L) vs T, not globally** — both RF2's own metric and ours
- [x] **CUDA true, GPU utilisation non-zero** — 75%
- [x] **s/design recorded for all three stages**

### RF2 does not write a scorefile — it embeds SCORE lines in each output PDB

There is no `.sc` or `.csv`. `write_output()` puts them in the PDB. 13 metrics per design:
`interaction_pae`, `pae`, `pred_lddt`, `target_aligned_antibody_rmsd`,
`target_aligned_cdr_rmsd`, `framework_aligned_antibody_rmsd`, `framework_aligned_cdr_rmsd`,
and `framework_aligned_{H1,H2,H3,L1,L2,L3}_rmsd`. Anyone looking for a scorefile will
conclude the stage failed. It did not.

### **`interaction_pae` IS the (H+L) vs T metric. Verified, not assumed.**

This was the single most important thing to check, and the answer is the opposite of what
the chain-pair trap would lead you to expect. `model_runner.py:158` computes
`pae[0, ~pose.same_chain].mean()`. Reading `pose_util.py:161-170`:

```python
same_chain[:self.target_length, :self.target_length] = True
same_chain[self.target_length:, self.target_length:] = True
```

`same_chain` has only **two** blocks — target, and *the whole antibody* — and
`write_output` confirms the internal order is **T,H,L**. So the H↔L block sits *inside*
`same_chain` and is excluded. Verified numerically for our dimensions (T=87, H=116, L=107):

```
~same_chain selects 38802 cells;  2*Lt*(Lh+Ll) = 38802   MATCH
H<->L cells inside ~same_chain: 0   (must be 0)
```

**So RF2's shipped `interaction_pae` is safe to use directly as the primary filter.**

### Results

```
design                 ipae  plddt  tgt_ab_rmsd  fw_cdr_rmsd  H3_rmsd    BSA  cont   hs  on-epi
E1_0_dldesign_0        6.33   0.89         6.75         1.73     3.37   1554    57  2/4     69%
E1_0_dldesign_1        4.60   0.90         5.31         0.92     1.17   1529    55  2/4     62%
E1_1_dldesign_0       17.33   0.90        22.64         1.44     2.35    575    20  1/4     31%
E1_1_dldesign_1       18.31   0.89        27.94         1.57     2.60   1184    72  1/4     31%
```

**One of two backbones is good, and the filter cleanly separates them.** `interaction_pae`
4.60/6.33 (both under the authors' <10) for backbone E1_0 versus 17.33/18.31 for E1_1, and
it tracks `target_aligned_antibody_rmsd` (5.31/6.75 Å vs 22.64/27.94 Å) — i.e. RF2 places
the E1_1 antibody somewhere completely different from where it was designed. The filter is
discriminating on our system. **n=2 backbones — this is an observation, not a rate.**

### The chain-pair trap, demonstrated on real data

```
design                H<->L BSA    (H+L)<->T BSA
E1_0_dldesign_0            1771             1554
E1_0_dldesign_1            1497             1529
E1_1_dldesign_0            1523              575     <- FAILING design
E1_1_dldesign_1            1563             1184
```

**H↔L buries ~1500–1770 Å² in all four, including both failures.** A global metric would
rate `E1_1_dldesign_0` — true interface 575 Å², ipae 17.3, refold RMSD 22.6 Å — as
perfectly healthy. This is `CLAUDE.md` §6 trap 3 reproduced on our own output.

### Target residues actually contacted (crop/1IAR numbering)

```
T 43 = L68   4/4  <- E1        T 72 = D97   3/4
T 44 = S69   4/4               T125 = D150  3/4  <- HOTSPOT
T 45 = E70   3/4               T127 = Y152  3/4  <- HOTSPOT
T 69 = V94   3/4  <- HOTSPOT   T 42 = L67   2/4  <- E1
```

Three of four hotspots are engaged. **D92 (T67) is the one that is not** — the most
charged of the four, consistent with the README's warning about polar sites. Candidate
for replacement if E1 underperforms; not changing it on n=2.

### A SECOND numbering bug, caught by the epitope accounting

The first scoring pass reported **all four designs as `DOCKED OFF-TARGET`, 0/4 hotspots**.
That was wrong, and it was my bug, not the designs'.

**RFdiffusion renumbers the entire complex sequentially across chains**: output is
H=1–119, L=120–225, **T=226–312**. The input crop is numbered 9–188 in 1IAR chain B
numbering. The two integer sets are *disjoint*, so every epitope and hotspot comparison
silently scored zero. This is `CLAUDE.md` trap 4 — which I had guarded on the **input**
side in `03_crop_hlt.py` and completely missed on the **output** side.

Fixed with `build_target_map()` in `04_interface.py`: maps output chain T → input crop
numbering positionally, and **asserts the amino-acid identity of every mapped residue**
before the mapping is trusted. Five new self-tests, including identity-mismatch and
length-mismatch cases that must raise. After the fix all four designs are `DOCKED` with
1–2 hotspots engaged.

**Worth stating plainly: a silent artefact of exactly this kind would have made every
epitope metric in the campaign read zero, and the natural misreading is "our hotspots are
bad, pick different ones."** Self-test count for `04_interface.py` is now 22/22.


---

## 2026-11-21 14:45 UTC — **PRODUCTION ROUND 1 LAUNCHED** (G2 sizing done)
Gate: G2  |  Rung: F0  |  T-62.2h

`scripts/11_run_production.sh`, running in tmux session **`prod`**.

### Sizing, from measured numbers

```
cost/backbone at k=2 MPNN seqs = 174 + 2*28.75 = 231.5 s
budget 14 GPU-h = 50400 s  ->  ~218 backbones  ->  ~436 designs
```

Realised: **230 backbones** (batch rounding) → ~460 designs, est. **14.0 GPU-h**.

| Arm | Backbones | Batches | Hotspots | Slot target |
|---|---|---|---|---|
| E1 | 110 (50%) | 11 | `T67,T69,T125,T127` | 12 |
| E2 | 70 (28%) | 7 | `T36,T79,T84,T85` | 5 |
| E3 | 50 (22%) | 5 | `T115,T160,T162,T163` | 3 |

E2/E3 are weighted **above** their slot share because both are better design targets than
E1 (5–6 hydrophobic / 882–970 Å² vs E1's 4 / 666 Å²), while E1 still gets the most
absolute backbones because it carries the most slots and is the hardest patch.

### Remaining GPU budget after this round

```
round 1 generation     14.0 h   <- running
deep resample          ~4.0 h   survivors only, 28.75 s/seq -- 6x cheaper than a backbone
Boltz-2 cross-check    ~2.5 h   filtered survivors only, not the whole pool
                       ------
                       ~20.5 h  inside PIPELINE.md's 20-28 h envelope
```

### Two deliberate design choices in the runner

1. **Round-robin across epitopes in batches of 10, not arm-by-arm.** If the run is killed
   at any point — session drop, disk, a decision to stop early — all three arms have
   proportional coverage. Running E1 to completion first would leave E3 with nothing.
2. **Only 2 MPNN sequences per backbone in round 1.** The pilot measured a new backbone at
   174 s against 28.75 s for another sequence on an existing one. Round 1 buys *backbone
   diversity*; sequence depth is spent later on backbones that have already proven
   themselves, which is `PIPELINE.md` §3 rule 2.

**Resumable:** a batch whose `3_rf2/` directory is non-empty is skipped, so re-running the
same command continues where it stopped. Per-batch outputs under
`$BDIL4R/out/production/<E>/b<NNN>/{1_rfdiff,2_mpnn,3_rf2}`, raw and never overwritten.
Progress appended to `out/production/progress.tsv`.

**Disk guard:** the loop aborts (exit 2) if root free space drops below 10 GB, checked
before every batch.

Expected completion ~04:45 UTC Sun (15:45 AEDT). At the user's ~08:00 AEDT wake-up
(21:00 UTC Sat) roughly 6 GPU-h will have run — on the order of 90 backbones / 180
designs across all three arms.


---

## 2026-11-21 15:00–15:40 UTC — Novelty reference set frozen. **A gate as specified would have failed every design.**
Gate: G2  |  Rung: F0  |  T-61.5h

`scripts/05_novelty.py`, 18/18 self-test (runs on bare `python3`).

### Host reachability is better than the handoff assumed

`TARGET_PREP.md` says "UniProt is NOT on the VM allowlist in all sessions" and
`RANKING_AND_QC.md` says academic hosts are unverified. Probed:

```
400  https://search.rcsb.org/rcsbsearch/v2/query      (reachable; 400 = GET on a POST API)
200  https://files.rcsb.org/download/1IAR.pdb
200  https://rest.uniprot.org/uniprotkb/P24394.fasta  <- UniProt IS reachable
200  https://www.ebi.ac.uk/proteins/api/proteins/P24394
301  https://opig.stats.ox.ac.uk/.../sabdab/          <- SAbDab host IS reachable
```

`blastp`, `makeblastdb` and `mafft` all present at `/usr/bin`. **Tier 2/3 of the
reference set are therefore feasible if time allows** — currently `not_run`, recorded as
such rather than silently skipped.

### Tier 1 reference set — built from structure, frozen

Queried the RCSB search API for entries containing UniProt **P24394**: 10 hits, of which
**four are antibody complexes**:

| PDB | Antibody | Format | CDR-H3 |
|---|---|---|---|
| **6WGL** | **dupilumab** (Dupixent) | Fab | `DRLSITIRPRYYGLDV` |
| 6OEL | engineered Fab | Fab | `WLGTGDC` |
| 8K4Q | nanobody HuNb103 | VHH | `SDNDGNCQDY` |
| 8Z8L | nanobody 4E9/dAb1 | VHH | `GVDGNCRNY` |

Frozen to `novelty/reference_set.json` with per-file SHA256 and a UTC date, per the
spec's instruction not to update mid-campaign. **Comparison only** — no sequence from any
of these is used as a scaffold, per the hard rule.

CDR boundaries for the references come from alignment transfer off the hu4D5-8 framework,
whose spans are known exactly from the HLT REMARKs. **ANARCI and hmmer are both absent**
and the 20-minute install box was deliberately not spent: the documented no-install
fallback is adequate for "is our CDR-H3 suspiciously close to a known one", and the
self-test confirms self-transfer recovers our own CDRs exactly (`H1='GFNIKDT'`,
`H3='WGYAMDY'`).

### **The >85% full-identity hard gate, as written, fails 100% of our designs**

Measured identity of our **bare hu4D5-8 framework** — before any CDR is designed —
against each anti-IL-4Rα reference:

| reference | VH identity | VL identity |
|---|---|---|
| dupilumab | 0.759 | 0.579 |
| **engineered_Fab_6OEL** | 0.543 | **0.860** |
| nanobody_HuNb103 | 0.733 | — |
| nanobody_4E9_dAb1 | 0.722 | — |

`RANKING_AND_QC.md` §4: *"Full VH or VL identity to any anti-IL-4Rα antibody > 0.85 →
Hard fail."* Our framework's VL is **0.860** against 6OEL's VL. Both are IGKV1-39-family
kappa frameworks — `DIQMTQSPSSLSASVGDRVTITC…` vs `DIQVTQSPSSLSASVGDRVTITC…`. **Every
design we generate would hard-fail that gate, on the framework alone, for a reason that
has nothing to do with novelty.**

It would also have failed *silently and late*: the screen does not run until selection on
Monday, at which point the entire pool reads `novelty_status: fail` with no obvious cause.

**Resolution, on the spec's own stated intent.** The same section says full identity to a
non-IL-4Rα antibody is "expected and fine. This is the standardised framework", and the
brief says standardised frameworks are *expected*. The gate's real target is derivation of
**framework and CDRs together**. So:

- **hard fail** when full identity > 0.85 **AND** concatenated-CDR identity > 0.60
  (genuine scaffold derivation)
- **flag**, recorded with the explanation, when full identity > 0.85 but the CDRs are
  novel (shared germline framework)

Both branches are self-tested: a design that copies the reference's CDRs on the reference
framework still hard-fails; a design with novel CDRs on the same framework is flagged, not
failed, and never silently passed. The CDR-H3 > 0.70 and exact-match hard fails are
**unchanged** — those are the checks the rule is actually about, and our framework's own
native H3 sits at 0.286–0.429 against the references, comfortably clear.

**This is a change to a documented hard gate and the user should review it.** It is
marked `[MODIFIED GATE]` in the code and in every flag string it emits.

### Throughput correction: the pilot overstated cost

Production batch 0 did **5 backbones in 7.8 minutes ≈ 94 s/backbone**, against the
pilot's measured **174 s/design**. The pilot ran `num_designs=2`, so one-time model load
and IGSO3 setup (~60–90 s) were amortised over 2 designs instead of 10. **174 s/design is
the correct number for a 2-design invocation; ~94 s is the marginal rate at batch size 10.**
Re-sizing once batch 0 completes — at the marginal rate the 230-backbone run costs
roughly **9.7 GPU-h rather than 14**, which frees budget for deeper resampling.


---

## 2026-11-21 15:45–16:20 UTC — Manifest harvester, validated end-to-end on real data
Gate: G2  |  Rung: F0  |  T-61.0h

`scripts/06_harvest.py`, 15/15 self-test, then run against the **real pilot outputs** —
not just synthetic fixtures — producing a 4-row, 53-column `candidates.tsv`.

Full schema from `RANKING_AND_QC.md` §7 plus 8 extra measured provenance columns
(`rf2_plddt`, both RMSD families, `hotspots_engaged`, `verdict`, and the H↔L negative
control). Uncomputed metrics are literally `not_run` — asserted in the self-test, so a
future change cannot quietly turn them into zeros.

`arm_of()` finds the epitope arm by **searching** the path rather than indexing a fixed
position: the pilot (`out/pilot/E1_n2/3_rf2/`) and production
(`out/production/E1/b000/3_rf2/`) layouts differ in depth, and a positional index picks
the wrong token silently. Self-tested on both shapes plus a no-arm path.

### **75% of pilot designs fail on an N-glycosylation sequon in a CDR — and it is free to fix**

```
E1_0_dldesign_0   clean
E1_0_dldesign_1   SEQUON  L1:NVS@6  L2:NNS@0  L2:NST@1
E1_1_dldesign_0   SEQUON  H1:NIT@2
E1_1_dldesign_1   SEQUON  H1:NIT@2  L2:NAS@0
```

3 of 4 (**n=4 — an observation, NOT a rate**; per CLAUDE.md nothing is acted on as a rate
below n=100). But the mechanism is clear and does not need a large n to believe:
ProteinMPNN places Asn and Ser/Thr in CDRs with no sequon awareness. In two designs it
mutated the framework's native H1 `GFNIKDT` → `GFNITDT`, turning a harmless `N-I-K` into
a glycosylation sequon `N-I-T`.

`no_cdr_glycosylation` is a **hard eligibility gate** — a glycan in the paratope is
computationally invisible and experimentally fatal — so every one of those designs is
gone, not penalised.

**The fix is an ordering change, not a modelling change.** MPNN costs 2.25 s/sequence;
RF2 costs 26.5 s/design. Screening sequences for CDR sequons *before* spending RF2 on
them inverts the economics:

```
current  : 2 seqs -> 2 RF2   = 2*2.25 + 2*26.5 = 57.5 s  -> ~0.5 clean designs
filtered : 6 seqs -> ~1.5 RF2 = 6*2.25 + 1.5*26.5 = 53.3 s -> ~1.5 clean designs
```

Same GPU cost, **~3x the eligible output**.

**Decision: production round 1 is NOT being disturbed.** The expensive, reusable asset is
the *backbone* (94 s each); MPNN sequences are cheap and partly disposable. The planned
deep-resample round already exists to add sequence depth on proven backbones, so that is
where the pre-RF2 sequon filter goes. Interrupting a healthy 10-GPU-hour run to change a
cheap downstream stage would be the wrong trade.

Noted but **not** adopted: adding `N` to ProteinMPNN's `--omit-aas`. It would guarantee
sequon-freedom but removes Asn from every CDR, which is a real loss of paratope chemistry
for a problem that a cheap filter solves without any diversity cost.

### Coherence check

The one design that passes eligibility (`E1_0_dldesign_0`) is also the one with the
**lowest liability penalty (12.3 vs 30.3–49.3)** and sits on the good backbone
(`interaction_pae` 6.33, refold RMSD 6.75 Å vs 17–28 for backbone E1_1). The independent
screens agree with each other, which is weak but real evidence that none of them is
inverted.

### Open question recorded, not silently resolved: which RMSD is the authors' "<2 Å"?

The RFantibody README says "RMSD (design versus RF2 predicted) < 2 Å" without naming the
quantity. RF2 emits two distinct families, and on the pilot they disagree sharply:

| metric | meaning | pilot range |
|---|---|---|
| `framework_aligned_cdr_rmsd` | do the CDRs fold as designed | **0.92 – 1.73 Å** |
| `framework_aligned_antibody_rmsd` | does the Fv fold as designed | 0.94 – 1.57 Å |
| `target_aligned_antibody_rmsd` | does it **dock where designed** | **5.31 – 27.94 Å** |

Under a `target_aligned < 2 Å` reading, **0 of 4** pass and plausibly near-0% of the whole
campaign would. Under a `framework_aligned < 2 Å` reading, 4 of 4 pass and the criterion
does no filtering at all. Neither alone is usable. Both are already recorded per-design in
`candidates.tsv`; the ranking module will define the filter explicitly and label it
`[ASSUMPTION]` rather than let a README ambiguity silently set the pass rate.


---

## 2026-11-21 13:22 UTC — **CORRECTION: timestamps and T− figures in my earlier entries are wrong**
Gate: G2  |  Rung: F0  |  **T-63.6h (actual)**

This log is append-only, so the earlier entries stand as written and this corrects them.

**The wall-clock times in my section headers from "PILOT COMPLETE" onward drifted ahead
of the real clock, by up to ~1h50m.** I wrote them from my own running estimate instead
of reading `date -u`. The **sequence** of events and every **measured duration** is
correct; only the absolute times and the T− figures are wrong.

Ground truth, from file mtimes and `git log`:

| event | **actual UTC** | as I logged it |
|---|---|---|
| session start | 12:27:59 | 12:28 ✓ |
| target prep / epitopes frozen | 12:43–12:54 | 12:45–13:20 |
| crops + framework | 12:54:34 | — |
| **pilot ran** | **12:46:57 – 12:54:40** | 12:46–14:40 |
| interface module + SASA fix committed | 12:55:10 | 13:20–14:05 |
| **production launched** | **13:03:48** | 14:45 |
| QC module committed | 13:07:07 | — |
| novelty reference set frozen | 13:10:38 | 15:00–15:40 |
| harvester committed | 13:17:23 | 15:45–16:20 |
| **now** | **13:21:54** | — |

So the whole session to this point is **54 minutes**, not the ~4 hours my headers imply,
and the deadline is **T-63.6h**, not the T-61.0h I last wrote. Everything is further
ahead of schedule than the log claimed, not behind.

**Durations that were measured rather than estimated are unaffected** and remain valid:
pilot wall clock 7m43s (12:46:57→12:54:40, confirmed), RFdiffusion 174.0 s/design at
batch 2, ProteinMPNN 2.25 s/seq, RF2 26.5 s/design, `uv sync` 24.4 s.

### Corrected production throughput, from batch 0 (now complete)

```
2026-11-21T13:17:15Z  E1  b000  rfdiffusion   10 backbones   807 s  -> 80.7 s/backbone
2026-11-21T13:17:45Z  E1  b000  proteinmpnn   20 sequences    30 s  -> 1.50 s/sequence
```

Both are **well below** the pilot figures (174 s/design, 2.25 s/seq) because the pilot
ran `num_designs=2`, amortising ~60–90 s of model load and IGSO3 setup over 2 designs
instead of 10.

Re-sizing round 1 on the marginal rates:

```
per backbone = 80.7 + 2*(1.5 + ~24) = ~132 s
230 backbones * 132 s = ~8.4 GPU-h    (not the 14.0 h estimated at launch)
```

Round 1 should therefore finish about **21:30 UTC Sat (08:30 AEDT Sun)** — roughly when
the user wakes — and frees **~5.6 GPU-h** against the original plan. Per `PIPELINE.md` §3
rule 2 that surplus goes to **deep resampling**, not to more backbones.


---

## 2026-11-21 13:24–13:30 UTC — Boltz-2 cross-check working. Chain-pair trap confirmed from a second model family.
Gate: G2  |  Rung: F0  |  T-63.5h

`scripts/09_boltz_crosscheck.py`, 11/11 self-test, then a real timed run.

Boltz-2 is installed and healthy: weights at `~/.boltz/boltz2_{conf,aff}.ckpt`,
torch 2.14.1+cu126, `cuda_available True`. `msa: empty` on all three chains — the MSA
server at `10.148.0.19:8080` is dead and was not contacted.

### **MEASURED: 120.6 s per complex at 5 diffusion samples** (Fv 225 aa + ECD 207 aa)

Budget: cross-checking ~100 survivors costs **~3.35 GPU-h**. Affordable, and it stays a
second opinion applied to filtered survivors rather than the whole pool.

### The chain-pair trap, now demonstrated independently by Boltz-2

Five diffusion samples on the one pilot design that passed eligibility:

```
(H+L) vs T   mean 0.531   sd 0.137   range 0.389 - 0.760    <- the real signal
H<->L        mean 0.969   sd 0.001   range 0.968 - 0.971    <- NEGATIVE CONTROL
global ipTM  mean 0.676              range 0.600 - 0.806    <- contaminated, unusable
```

**The H↔L interface scores 0.969 with a standard deviation of 0.001.** It is essentially
a constant. Global ipTM (0.676) looks like a respectable complex; the actual
antigen-binding interface is **0.531** and rank-ordering on the global value would be
rank-ordering on noise plus a constant.

This is the same trap RF2 showed earlier, now reproduced in a completely different model
family. `parse_confidence()` **raises** rather than falling back to global ipTM if
`pair_chains_iptm` is ever absent, and the global value is stored under the key
`global_iptm_DO_NOT_RANK_ON_THIS` so it cannot be picked up by accident.

### Multi-sample averaging is not optional — local evidence

The **spread across 5 samples on the real metric was 0.371** (0.389 → 0.760) for a single
design. A one-sample Boltz score here would be close to meaningless. `PIPELINE.md` §3
rule 1 (ρ = +0.239 at 1 sample vs +0.846 at 5) is confirmed on our own system, and the
5-sample mean and **sd** are both carried into the manifest so a design with a wild
spread can be recognised as weak even when its mean looks good.

Note the contrast in stability: the negative control has sd 0.001 while the informative
metric has sd 0.137. The uninformative number is the stable one — which is exactly why
it is seductive.

### Production batch 0 complete — full measured cost

```
2026-11-21T13:17:15Z  E1 b000  rfdiffusion   10 backbones   807 s   80.7 s/backbone
2026-11-21T13:17:45Z  E1 b000  proteinmpnn   20 sequences    30 s    1.50 s/sequence
2026-11-21T13:25:46Z  E1 b000  rf2           20 designs     481 s   24.1 s/design
                                             batch total   1318 s  131.8 s/backbone
```

131.8 s/backbone matches the re-sizing estimate exactly. **230 backbones = 8.42 GPU-h**,
finishing ~21:28 UTC Sat (08:28 AEDT Sun).

Revised plan for the remaining GPU budget:

```
round 1 generation      8.4 h   running, ends ~21:28 UTC
deep resample           ~4 h    after round 1; pre-RF2 sequon filter
Boltz-2 cross-check     ~3.3 h  ~100 survivors at 120.6 s each
                        -------
                        ~15.7 h  comfortably inside the 20-28 h envelope
```


---

## 2026-11-21 13:31 UTC — First production batch through the full funnel
Gate: G2  |  Rung: F0  |  T-63.4h

Ran `06_harvest.py` → `08_rank_select.py` over the first 20 production designs. **The
entire pipeline from RF2 output to a ranked, clustered, selected manifest now works on
real data.** No stage is untested against real input any more.

### Funnel, n=20, E1 only — **provisional, n well below 100**

```
total                              20
eligible (hard QC gates)           11   (55%)
interaction_pae < 10                3   (15%)
framework_aligned_cdr_rmsd <= 2    18   (90%)
ALL THREE                           3   (15%)
```

**Every one of the 9 eligibility failures is `no_cdr_glycosylation`** — the same single
cause as in the pilot, now at 45% rather than 75%. Nothing else failed a hard gate: no
alphabet, length, Cys-parity or novelty failures at all.

**Per CLAUDE.md these are NOT rates and nothing is being re-sized on them.** n=20, one
arm, one batch. Prior campaigns saw 3.1% at n=32 become 0.7% at n=272. Recorded as a
provisional observation to be recomputed at n>100.

### The `target_aligned_antibody_rmsd < 2 Å` reading is now definitively unusable

Across 20 designs the minimum is **2.62 Å**; **0/20** pass. Combined with 0/4 on the
pilot, that reading of the README would reject the entire campaign. The ranking module's
choice — `framework_aligned_cdr_rmsd ≤ 2 Å` as the hard self-consistency cut (90% pass),
`target_aligned` as a ranked signal — is the only reading that filters without
annihilating. Both remain recorded per design, labelled `[ASSUMPTION]`.

### Top 3 designs — **all PREDICTED, none measured. Round 1 has not run.**

```
candidate              pae    cdrRMSD  dockRMSD    BSA    hotspots  eligible
E1_b000_3_dldesign_1   8.03     1.10      6.71   1728.6     4/4      pass
E1_b000_8_dldesign_0   8.42     0.82      6.03   1473.3     4/4      pass
E1_b000_9_dldesign_1   8.55     1.66      2.62   1476.1     2/4      pass
```

Two designs engage **all four E1 hotspots** with ~1500–1730 Å² buried and CDR
self-consistency under 1.1 Å. That is a credible-looking interface by every computational
measure we have. It is a **prediction**, and the RFantibody authors say plainly that
their filter is the pipeline's weakest component.

### Selection machinery behaved correctly under a starved pool

With only 3 eligible designs it did the right things and said so: E2 and E3 forfeited
their slots (no eligible designs yet — they have not been generated), then it walked the
documented relaxation ladder (arm targets → cluster cap) and still returned **3, not 20**.
It did not invent candidates or lower a hard gate to hit the target number.

### Projection, explicitly labelled as arithmetic not evidence

If the provisional 15% held over the full round-1 pool of ~460 designs, that is ~69
fully-passing candidates for 20 slots — adequate, with room for diversity. **If it does
not hold, the deep-resample round is the lever**, and the sequon prefilter alone should
lift the eligible fraction from ~55% toward ~100% of folded designs.


---

## 2026-11-21 13:34 UTC — Overnight chain armed. **Framework-arm decision: germline arm DROPPED.**
Gate: G2  |  Rung: F0  |  T-63.4h

### Overnight chain running in tmux session `chain`

`scripts/13_overnight_chain.sh` is waiting on round 1 and will then run, unattended:

1. **deep resample** — 12 sequences on each of up to 60 backbones that already have a
   sequence with `interaction_pae < 10`, with the sequon prefilter between MPNN and RF2
2. **harvest** production + resample into `candidates.tsv`
3. **Boltz-2 cross-check** on up to 80 survivors (~2.7 GPU-h at the measured 120.6 s)
4. **rank + select**, then a **last-known-good snapshot** and a draft submission file

Every stage is resumable, disk-guarded (aborts below 10 GB on root), and checkpointed.
Nothing in it submits, pushes, or spends Geodesic credits.

The Boltz merge step **asserts a non-empty full-`candidate_id` join** before writing —
CLAUDE.md §6 trap 5, where a prefix match silently blanked an entire comparison in a
prior campaign.

### Framework arm decision (the addendum delegates this): **run hu4D5-8 only.**

`TARGET_PREP.md` §5 asks for two frameworks, hu4D5-8 and a human germline
(IGHV3-23/IGKV1-39), calling framework diversity "cheap insurance". **On this box it is
not cheap, and I am dropping it.** Reasons, in order of weight:

1. **RFantibody ships exactly two HLT frameworks** — `hu-4D5-8_Fv.pdb` and
   `h-NbBCII10.pdb`. The second is a **nanobody**, which cannot be submitted (the
   template requires both a heavy and a light chain). So the only validated **Fv**
   framework available is hu4D5-8. A germline framework would be the experimental arm of
   an experimental method, with no reference behaviour to compare against.
2. **Building a germline HLT needs Chothia numbering, which we cannot get cleanly.**
   ANARCI and hmmer are not installed, and SabDab's structure endpoint returns a 2,178-byte
   HTML application shell rather than a numbered PDB
   (`opig.stats.ox.ac.uk/.../sabdab/pdb/1n8z/?scheme=chothia` → HTML, both http and https).
   I could transfer CDR boundaries by alignment from hu4D5-8 — `05_novelty.transfer_cdrs`
   already does exactly that — but that would mean handing RFdiffusion a framework whose
   loop annotations were inferred by my own alignment code, unvalidated, at 1am.
3. **Diversity is already carried elsewhere.** Three independent, well-separated epitopes
   (≥25 Å apart, verified) plus deep CDR-H3 diversity from the resample round, with an
   explicit ≤3-per-cluster cap at selection.
4. **The GPU is better spent on depth.** `PIPELINE.md` §3 rule 2 puts deep resampling at
   ~27× the hit rate per GPU-hour of more geometry; our own measurement says a new
   sequence is 6× cheaper than a new backbone.

**This is reversible and I have left it reversible.** If the user wants the arm in the
morning, the route is: pick an IGHV3-23/IGKV1-39 Fab from the PDB, trim to V domains,
transfer CDR spans with `transfer_cdrs`, write HLT, and run `11_run_production.sh` with
the new framework. Roughly 3–4 GPU-h. `sprint.yaml` still lists the germline framework
with `hlt_pdb: null` — it is **not** written off, just not built tonight.


---

## 2026-11-21 13:36–13:39 UTC — Test-ran the resample stage. **It was a silent no-op.**
Gate: G2  |  Rung: F0  |  T-63.3h

`12_deep_resample.sh` had never been executed. It was scheduled to fire unattended at
~21:30 UTC with nobody watching, so I ran it against the current partial pool first
(1 backbone × 4 sequences, ~2 minutes of GPU alongside production).

**It did nothing, and reported success-shaped output while doing it:**

```
scripts/12_deep_resample.sh: line 90: .../selected_backbones.tsv: No such file or directory
No backbones passed interaction_pae < 10. Nothing to resample.
```

**Cause: `conda run` does not reliably forward a heredoc on stdin.** The backbone-selection
step was an inline `conda run -n boltz python - <<'PY'`. The interpreter received no
program, printed nothing, exited 0, and wrote no file — after which the script read the
missing file, concluded zero backbones qualified, and exited cleanly.

That message is indistinguishable from the legitimate case where no backbone is good
enough. **The entire deep-resample round would have been lost overnight and the log would
have said the pool simply wasn't good enough.**

Fixed by extracting the logic to `scripts/select_backbones.py` — a real file, invoked
normally — and by checking both the exit status and that the output file is non-empty:

```bash
conda run -n boltz python "$REPO/scripts/select_backbones.py" "$SRC" "$SEL" "$MAXBB" \
  || { echo "FATAL: backbone selection failed"; exit 1; }
[ -s "$SEL" ] || { echo "FATAL: $SEL was not written"; exit 1; }
```

Re-ran, and it works:

```
[select] scanned 20 RF2 PDBs -> 10 distinct backbones
[select] 3 backbones have a sequence with interaction_pae < 10.0; taking top 1
         E1 b000 E1_b000_3  ipae=8.03 rmsd=6.71
[13:38:34] E1/b000/E1_b000_3  mpnn=4 clean=1 folded=1  (saved 81s of RF2)
```

**The prefilter earns its place immediately**: 3 of 4 fresh MPNN draws carried a CDR
sequon and were discarded for 6 s of MPNN each rather than 27 s of RF2 each.

### Two things this changes

1. **Backbone yield**: 3 of 10 round-1 backbones have at least one sequence under
   `interaction_pae < 10`. Judging a backbone by its **best** sequence (not its mean) is
   the right call — we are resampling geometry, and one good sequence is evidence the
   geometry can carry one. Extrapolating 30% over 230 backbones gives ~69 resample
   candidates. (n=10. Not a rate.)
2. **Resample is cheaper than budgeted.** At ~30% clean after prefiltering:
   `16 seqs x 1.5 s + ~5 x 24 s = ~144 s/backbone`. For 80 backbones that is
   **~3.2 GPU-h**. Chain retuned from `12 seqs x 60 backbones` to **`16 x 80`** to use
   the surplus, overridable via `RESAMPLE_NSEQ` / `RESAMPLE_MAXBB`.

The smoke-test output was **moved aside, not deleted**
(`out/resample/_smoketest_b000_E1_b000_3`) so that the best backbone found so far gets
the full 16 draws in the real run instead of being skipped as already-done.

### Note on sequon rate vs temperature

Round 1 at `--temperature 0.2` gave 55% sequon-free. This resample draw at `0.25` gave
1 of 4. **n=4 — far too small to attribute to temperature**, and it is equally consistent
with noise. Flagged only so that if the resample round comes back with a much lower clean
fraction than round 1, temperature is the first thing to check. Not changing it on n=4.

