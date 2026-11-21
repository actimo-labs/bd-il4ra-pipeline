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

